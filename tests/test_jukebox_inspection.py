"""Publisher evidence inspection is inert metadata, never mutation eligibility."""
import contextlib
import fcntl
import copy
import io
import json
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jukebox_playback as p
import jukebox_cli as cli
from test_jukebox_playback import Fixture


def snapshot(root):
    result = {}
    for path in root.rglob('*'):
        stat = path.lstat(); value = (stat.st_mode, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if path.is_symlink(): result[str(path.relative_to(root))] = (value, os.readlink(path))
        elif path.is_file(): result[str(path.relative_to(root))] = (value, path.read_bytes())
        else: result[str(path.relative_to(root))] = value
    return result


def arguments(**overrides):
    values = dict(mode='inspect-state', approve=True, expected_publisher_sha256=cli.code_identity(),
                  manifest=None, expected_manifest_sha256=None, expected_source_revision=None,
                  activation_plan=None, expected_plan_sha256=None, api_token_fd=None, review_id=None)
    return SimpleNamespace(**{**values, **overrides})


class InspectionTests(unittest.TestCase):
    def test_absent_report_never_creates_state_or_lock(self):
        f = Fixture()
        try:
            before = sorted(str(x.relative_to(f.home)) for x in f.home.rglob('*'))
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'absent')
            self.assertFalse(report['writes']); self.assertFalse(report['actionable'])
            self.assertEqual(sorted(str(x.relative_to(f.home)) for x in f.home.rglob('*')), before)
        finally: f.close()

    def test_blocked_journal_is_reported_without_enabling_normal_mutation(self):
        f = Fixture()
        try:
            review = f.publisher.review(f.a, approve=True)
            root = f.home / p.STATE
            row = json.loads((root / 'reviews' / (review['id'] + '.json')).read_text())
            row['status'] = 'blocked'; (root / 'reviews' / (review['id'] + '.json')).write_bytes(p.canonical(row))
            before = {str(x.relative_to(root)): x.read_bytes() for x in root.rglob('*') if x.is_file() and not x.is_symlink()}
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'incomplete')
            self.assertEqual(report['reviews']['counts']['blocked'], 1)
            self.assertFalse(report['recoveryAuthorized'])
            with self.assertRaises(p.Refusal): f.publisher.discard(review['id'], approve=True)
            self.assertEqual({str(x.relative_to(root)): x.read_bytes() for x in root.rglob('*') if x.is_file() and not x.is_symlink()}, before)
        finally: f.close()

    def test_pending_and_terminal_reports_are_structural_only_without_helpers_or_mutations(self):
        f = Fixture()
        try:
            f.install(); review = f.publisher.review(f.a, approve=True)
            before = snapshot(f.home); calls = (list(f.fake.commands), f.fake.root_calls, len(f.fake.backups))
            with patch.object(f.fs, 'write', side_effect=AssertionError('No write')), \
                 patch.object(f.fs, 'mkdir', side_effect=AssertionError('No mkdir')), \
                 patch.object(f.fake, 'verify_root', side_effect=AssertionError('No root query')):
                report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'pending'); self.assertTrue(report['snapshotStable'])
            self.assertEqual(report['transactions']['counts']['verified'], 1)
            self.assertEqual(report['reviews']['counts']['pending'], 1)
            self.assertEqual(report['roots']['count'], 1)
            self.assertFalse(report['actionable']); self.assertIn('ownership', report['notChecked'])
            self.assertEqual(snapshot(f.home), before)
            self.assertEqual((f.fake.commands, f.fake.root_calls, len(f.fake.backups)), calls)
            self.assertNotIn(review['id'], json.dumps(report), 'Only derived inert references, not action IDs')
        finally: f.close()

    def test_pending_payloads_are_counted_but_never_read_interpreted_or_cleaned(self):
        f = Fixture()
        try:
            f.publisher.review(f.a, approve=True); root = f.home / p.STATE
            pending = root / 'transactions' / ('.pending-' + 'a' * 32)
            pending.write_bytes(b'SYNTHETIC_SECRET'); pending.chmod(0o600)
            original = f.fs.read
            def guarded(relative, *args):
                if '.pending-' in relative: raise AssertionError('No pending payload reads')
                return original(relative, *args)
            with patch.object(f.fs, 'read', side_effect=guarded): report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'incomplete'); self.assertEqual(report['pendingFiles']['observed'], 1)
            self.assertNotIn('SYNTHETIC', json.dumps(report)); self.assertEqual(pending.read_bytes(), b'SYNTHETIC_SECRET')
        finally: f.close()

    def test_busy_lock_causes_no_record_read_and_is_not_created_or_replaced(self):
        f = Fixture()
        try:
            f.publisher.review(f.a, approve=True); root = f.home / p.STATE; before = snapshot(f.home)
            fd = os.open(root / 'lock', os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(f.fs, 'read', side_effect=AssertionError('No record read while busy')):
                    report = p.EvidenceInspector(f.fs).inspect()
                self.assertEqual(report['state'], 'busy'); self.assertIsNone(report['reviews']['retained'])
            finally: os.close(fd)
            self.assertEqual(snapshot(f.home), before)
        finally: f.close()

    def test_missing_unsafe_or_foreign_lock_and_state_are_unavailable_without_repair(self):
        for kind in ('missing-lock', 'symlink-lock', 'hardlink-lock', 'public-lock', 'fifo-lock', 'public-state', 'symlink-state'):
            f = Fixture()
            try:
                f.publisher.review(f.a, approve=True); root = f.home / p.STATE; lock = root / 'lock'
                if kind == 'missing-lock': lock.unlink()
                elif kind == 'symlink-lock': lock.unlink(); lock.symlink_to(f.root / 'absent')
                elif kind == 'hardlink-lock': os.link(lock, f.root / 'alias')
                elif kind == 'public-lock': lock.chmod(0o644)
                elif kind == 'fifo-lock': lock.unlink(); os.mkfifo(lock)
                elif kind == 'public-state': root.chmod(0o755)
                else: root.rename(root.with_name('retained')); root.symlink_to(root.with_name('retained'))
                report = p.EvidenceInspector(f.fs).inspect()
                self.assertEqual(report['state'], 'unavailable', kind)
                self.assertIsNone(report['transactions']['retained']); self.assertFalse(report['actionable'])
                self.assertEqual(report['pendingFiles']['coverage'], 'not-checked')
            finally: f.close()

    def test_unknown_names_schema_raw_errors_and_values_are_never_echoed(self):
        for kind in ('name', 'registry', 'review', 'error', 'huge'):
            f = Fixture()
            try:
                reviewed = f.publisher.review(f.a, approve=True); root = f.home / p.STATE
                path = root / 'reviews' / (reviewed['id'] + '.json')
                if kind == 'name': (root / 'SYNTHETIC_SECRET').write_text('not read')
                elif kind == 'registry': (root / 'registry.json').write_text('{"owner":"SYNTHETIC_SECRET"}')
                elif kind == 'review':
                    row = json.loads(path.read_text()); row['status'] = 'SYNTHETIC_SECRET'; path.write_text(json.dumps(row))
                elif kind == 'huge': path.write_bytes(b'SYNTHETIC_SECRET' * 10000)
                original = f.fs.read
                def reader(relative, *args):
                    if kind == 'error': raise OSError('SYNTHETIC_SECRET private path')
                    return original(relative, *args)
                with patch.object(f.fs, 'read', side_effect=reader): report = p.EvidenceInspector(f.fs).inspect()
                self.assertEqual(report['state'], 'unknown')
                self.assertNotIn('SYNTHETIC', json.dumps(report)); self.assertFalse(report['recoveryAuthorized'])
            finally: f.close()

    def test_dangling_root_active_and_public_links_are_metadata_only_never_followed(self):
        f = Fixture()
        try:
            f.install(); root = f.home / p.STATE
            active = root / 'active'; active.unlink(); active.symlink_to('/SYNTHETIC_SECRET/not-present')
            retained = next((root / 'roots').iterdir()); retained.unlink(); retained.symlink_to('/SYNTHETIC_SECRET/not-present')
            with patch.object(p, 'Artifact', side_effect=AssertionError('No artifact reads')), \
                 patch.object(f.fake, 'verify_root', side_effect=AssertionError('No root helper')):
                report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'observed'); self.assertFalse(report['actionable'])
            self.assertIn('artifact-contents', report['notChecked']); self.assertIn('root-registration', report['notChecked'])
            self.assertNotIn('SYNTHETIC', json.dumps(report))
            with self.assertRaises(p.Refusal): f.publisher.inspect()
        finally: f.close()

    def test_partial_initialization_and_missing_inventory_are_unknown_not_empty(self):
        f = Fixture()
        try:
            root = f.home / p.STATE; root.mkdir(parents=True, mode=0o700)
            (root / 'lock').touch(mode=0o600)
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'unknown'); self.assertIsNone(report['transactions']['retained'])
            self.assertEqual(report['coverage']['registry'], 'unavailable')
            self.assertEqual(report['pendingFiles']['coverage'], 'partial')
            self.assertFalse((root / 'registry.json').exists()); self.assertFalse((root / 'reviews').exists())
        finally: f.close()

    def test_quota_overflow_is_unavailable_and_output_rows_are_bounded(self):
        f = Fixture()
        try:
            review = f.publisher.review(f.a, approve=True); root = f.home / p.STATE
            base = json.loads((root / 'reviews' / (review['id'] + '.json')).read_text()); base['status'] = 'discarded'
            for index in range(60):
                row = {**base, 'id': format(index, '032x')}; path = root / 'reviews' / (row['id'] + '.json')
                path.write_bytes(p.canonical(row)); path.chmod(0o600)
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['reviews']['retained'], 61); self.assertEqual(len(report['reviews']['rows']), 50)
            self.assertEqual(report['reviews']['omittedRows'], 11); self.assertEqual(report['reviews']['unknownRecords'], 0)
            for index in range(60, 130):
                row = {**base, 'id': format(index, '032x')}; path = root / 'reviews' / (row['id'] + '.json')
                path.write_bytes(p.canonical(row)); path.chmod(0o600)
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'unknown'); self.assertIsNone(report['reviews']['retained'])
            self.assertEqual(report['coverage']['reviews'], 'unavailable')
        finally: f.close()

    def test_mid_read_identity_drift_is_changed_and_never_claims_snapshot_stability(self):
        f = Fixture()
        try:
            f.publisher.review(f.a, approve=True); root = f.home / p.STATE; original = f.fs.read
            once = [False]
            def replace(relative, *args):
                value = original(relative, *args)
                if relative.endswith('registry.json') and not once[0]:
                    once[0] = True; path = root / 'registry.json'; path.rename(root / 'retained'); path.write_bytes(value); path.chmod(0o600)
                return value
            with patch.object(f.fs, 'read', side_effect=replace): report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'changed'); self.assertIs(report['snapshotStable'], False)
            self.assertFalse(report['actionable']); self.assertTrue((root / 'retained').exists())
        finally: f.close()

    def test_transferred_owner_can_be_observed_but_not_adopted_or_reactivated(self):
        f = Fixture()
        try:
            f.install(); path = f.home / p.STATE / 'registry.json'
            row = json.loads(path.read_text()); row['owner'] = 'transferred-to-hm'; path.write_bytes(p.canonical(row))
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['registry']['owner'], 'transferred-to-hm'); self.assertFalse(report['actionable'])
            with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
            self.assertEqual(json.loads(path.read_text())['owner'], 'transferred-to-hm')
        finally: f.close()

    def test_failed_apply_journal_is_inspectable_but_not_discarded_retried_or_repaired(self):
        f = Fixture()
        try:
            f.install(); next_artifact = f.artifact(revision='e' * 40, pretty=True)
            reviewed = f.publisher.review(next_artifact, approve=True); f.fake.fail = 'backup'
            with self.assertRaises(p.Refusal): f.publisher.apply(reviewed['id'], approve=True)
            before = snapshot(f.home); commands = list(f.fake.commands)
            report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'incomplete')
            self.assertEqual(report['transactions']['counts']['blocked'], 1)
            self.assertEqual(report['registry']['pending'], True)
            with self.assertRaises(p.Refusal): f.publisher.discard(reviewed['id'], approve=True)
            with self.assertRaises(p.Refusal): f.publisher.apply(reviewed['id'], approve=True)
            self.assertEqual(snapshot(f.home), before); self.assertEqual(f.fake.commands, commands)
        finally: f.close()

    def test_completed_transfer_record_is_observed_without_inspecting_store_or_changing_owner(self):
        f = Fixture()
        try:
            f.install(); generation = f.store / ('d' * 32 + '-home-manager-files'); generation.mkdir()
            f.fake.transfer = {'generation': str(generation), 'artifactHash': f.a.hash, 'approved': True}
            for name, target in p.TARGETS.items():
                dest = generation / target; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(f.a.payloads[name])
                live = f.home / target; live.unlink(); live.symlink_to(dest)
            f.publisher.record_transfer(approve=True); before = snapshot(f.home)
            with patch.object(p, 'Artifact', side_effect=AssertionError('No store access')):
                report = p.EvidenceInspector(f.fs).inspect()
            self.assertEqual(report['state'], 'observed')
            self.assertEqual(report['transactions']['counts']['transferred'], 1)
            self.assertEqual(report['registry']['owner'], 'transferred-to-hm')
            self.assertEqual(snapshot(f.home), before); self.assertFalse(report['actionable'])
            with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
        finally: f.close()

    def test_inspector_is_one_shot_and_does_not_leak_descriptors(self):
        f = Fixture()
        try:
            f.publisher.review(f.a, approve=True); before = len(os.listdir('/proc/self/fd'))
            inspector = p.EvidenceInspector(f.fs); inspector.inspect()
            with self.assertRaises(p.Refusal): inspector.inspect()
            self.assertEqual(len(os.listdir('/proc/self/fd')), before)
        finally: f.close()

    def test_cli_readonly_gate_never_constructs_helpers_or_reads_credentials(self):
        f = Fixture()
        try:
            def forbidden(*args, **kwargs): raise AssertionError('No native helper/API/credential')
            with patch.object(cli, 'fixed_paths', return_value={'home': f.home, 'uid': os.geteuid()}), \
                 patch.object(cli, 'OwnedRunner', side_effect=forbidden), patch.object(cli, 'LocalAPI', side_effect=forbidden), \
                 patch.object(cli, 'NativeIO', side_effect=forbidden), patch.object(cli, 'token_from_fd', side_effect=forbidden):
                report = cli.inspect_state(arguments())
                self.assertEqual(report['state'], 'absent'); self.assertFalse((f.home / p.STATE).exists())
            for overrides in ({'approve': False}, {'expected_publisher_sha256': '0' * 64}, {'api_token_fd': 3},
                              {'activation_plan': 'SYNTHETIC_SECRET'}, {'manifest': 'SYNTHETIC_SECRET'},
                              {'expected_source_revision': 'a' * 40}, {'expected_plan_sha256': 'a' * 64},
                              {'review_id': 'a' * 32}, {'mode': 'apply'}):
                with patch.object(cli, 'fixed_paths', side_effect=AssertionError('No host/home access')):
                    with self.assertRaises(p.Refusal): cli.inspect_state(arguments(**overrides))
            with patch.object(cli, 'safe_file', side_effect=AssertionError('No plan read')):
                for pin in (cli.code_identity(), ''):
                    with self.assertRaises(p.Refusal): cli.run(arguments(mode='apply', expected_publisher_sha256=pin))
        finally: f.close()

    def test_cli_mode_separation_redaction_and_public_inspect_still_has_no_home_access(self):
        f = Fixture()
        try:
            def invoke(args):
                out = io.StringIO(); error = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(error): code = p.main(args)
                return code, out.getvalue(), error.getvalue()
            with patch.object(cli, 'fixed_paths', return_value={'home': f.home, 'uid': os.geteuid()}):
                code, out, error = invoke(['inspect-state', '--approve', '--expected-publisher-sha256', cli.code_identity()])
                self.assertEqual(code, 0); self.assertEqual(json.loads(out)['state'], 'absent'); self.assertEqual(error, '')
            with patch.object(cli, 'fixed_paths', side_effect=AssertionError('No home access')):
                code, out, error = invoke(['inspect-state', '--approve', '--expected-publisher-sha256', 'SYNTHETIC_SECRET'])
                self.assertEqual(code, 2); self.assertEqual(out, ''); self.assertNotIn('SYNTHETIC', error)
                code, _, _ = invoke(['apply', '--approve', '--expected-publisher-sha256', cli.code_identity()])
                self.assertEqual(code, 2)
                artifact = p.Artifact
                with patch.object(p, 'Artifact', side_effect=lambda path, sha, rev: artifact(path, sha, rev, f.store)):
                    code, out, _ = invoke(['inspect', '--manifest', str(f.a.path), '--expected-manifest-sha256', f.a.hash, '--expected-source-revision', f.a.revision])
                    self.assertEqual(code, 0); self.assertFalse(json.loads(out)['writes'])
                code, _, _ = invoke(['inspect', '--expected-publisher-sha256', cli.code_identity()])
                self.assertEqual(code, 2)
                with patch.object(p, 'Artifact') as constructor:
                    code, _, _ = invoke(['inspect', '--manifest', str(f.a.path), '--expected-manifest-sha256', f.a.hash,
                                         '--expected-source-revision', f.a.revision, '--expected-publisher-sha256', ''])
                    self.assertEqual(code, 2); constructor.assert_not_called()
        finally: f.close()


if __name__ == '__main__': unittest.main()
