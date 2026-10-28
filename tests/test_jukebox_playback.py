"""Temporary homes/store only. No user-systemd, API, GC roots or real media."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("playback", ROOT / "scripts/jukebox_playback.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Fake:
    def __init__(self, fs):
        self.fs = fs
        self.context = {key: p.digest(key.encode()) for key in
                        ("profiles", "flags", "source", "invocation", "unit", "resources", "tools", "stopPolicy")}
        self.context["eligible"] = True
        self.now = ["boot-1", 1000, 2000]
        self.commands = []
        self.active = True
        self.fail = None
        self.root_calls = 0
        self.backups = []
        self.pending = False
        self.release = threading.Event()
        self.entered = threading.Event()
        self.transfer = None

    def snapshot(self):
        return copy.deepcopy(self.context)

    def clock(self):
        return tuple(self.now)

    def root(self, artifact, target):
        self.root_calls += 1
        if self.fail == "root-timeout":
            self.pending = True
            raise p.Refusal("Owned helper deadline, not exit")
        if self.fail == "root":
            raise p.Refusal("Unavailable root capability")
        target.symlink_to(artifact.path)

    def verify_root(self, artifact, target):
        p.require(target.is_symlink() and os.readlink(target) == str(artifact.path), "Missing/foreign fixture root")

    def backup(self, snapshot):
        if self.fail == "backup":
            raise p.Refusal("Backup unavailable")
        receipt = {"id": format(len(self.backups), "032x"), "hash": p.digest(p.canonical(snapshot))}
        self.backups.append(receipt)
        return receipt

    def verify_backup(self, receipt, snapshot):
        p.require(receipt in self.backups and receipt["hash"] == p.digest(p.canonical(snapshot)), "Stale backup")

    def command(self, argv):
        p.require(argv in p.COMMANDS.values(), "Unknown command")
        self.commands.append(argv)
        action = next(k for k, v in p.COMMANDS.items() if v == argv)
        if self.fail == action:
            raise p.Refusal("Uncertain fixture command")
        if action == "stop":
            self.active = False
        elif action == "start":
            self.active = True
            self.context["invocation"] = p.digest(self.context["invocation"].encode())

    def stopped(self, snapshot):
        p.require(not self.active, "Stop not proven")
        self.unchanged(snapshot)

    def unchanged(self, before):
        for key in before:
            if key != "invocation":
                p.require(before[key] == self.context[key], "Profile/config/source changed")

    def ready(self, artifact, before):
        p.require(self.active and self.fail != "ready", "Readiness not proven")
        self.unchanged(before)
        for name, target in p.TARGETS.items():
            path = self.fs.path / target
            if artifact:
                p.require(path.read_bytes() == artifact.payloads[name], "Effective payload mismatch")
            else:
                p.require(not path.exists() and not path.is_symlink(), "Expected prior absence")

    def drain(self):
        if self.pending:
            self.entered.set()
            self.release.wait(5)
            p.require(self.release.is_set(), "Fixture helper still owns resources")
            self.pending = False

    def transfer_proof(self, artifact):
        return self.transfer


class Fixture:
    def __init__(self, fault=lambda _: None, **limits):
        self.tmp = tempfile.TemporaryDirectory(prefix="nix-playback-fixture-")
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.store = self.root / "store"
        self.store.mkdir(mode=0o700)
        self.fs = p.Home(self.home, fault=fault)
        self.fake = Fake(self.fs)
        self.publisher = p.Publisher(self.fs, self.fake, "b" * 64, self.load, **limits)
        self.a = self.artifact()

    def load(self, path, sha, rev):
        return p.Artifact(path, sha, rev, self.store)

    def artifact(self, revision="a" * 40, pretty=False, mutate=None):
        values = {name: (ROOT / "config/jukebox/bravo" / name).read_bytes() for name in p.TARGETS}
        if pretty:
            values["playback.env"] = values["playback.env"].replace(b'"port":6600', b'"port": 6600')
        if mutate:
            mutate(values)
        identity = p.digest(b"".join(values.values()))[:32]
        directory = self.store / (identity + "-bravo-jukebox-playback-files")
        directory.mkdir(exist_ok=True)
        for name, data in values.items():
            (directory / name).write_bytes(data)
        m = {"schema": 1, "publisherSchema": 1, "role": "bravo", "account": "budchris", "configHome": ".config",
             "sourceRevision": revision, "lockSha256": "c" * 64, "filesDirectory": str(directory),
             "files": [{"name": name, "target": p.TARGETS[name], "size": len(data), "sha256": p.digest(data)}
                       for name, data in values.items()]}
        raw = p.canonical(m)
        path = self.store / (p.digest(raw)[:32] + "-bravo-jukebox-playback-manifest.json")
        path.write_bytes(raw)
        return self.load(path, p.digest(raw), revision)

    def install(self, a=None):
        r = self.publisher.review(a or self.a, approve=True)
        return self.publisher.apply(r["id"], approve=True)

    def close(self):
        self.fs.close()
        self.tmp.cleanup()


class Playback(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def test_inspect_absent_is_read_only_and_approvals(self):
        self.assertEqual(self.f.publisher.inspect(), {"state": "absent", "writes": False})
        self.assertFalse((self.f.home / ".local").exists())
        with self.assertRaises(p.Refusal):
            self.f.publisher.review(self.f.a)
        self.assertFalse((self.f.home / ".local").exists())

    def test_install_update_noop_metadata_only_and_manual_rollback(self):
        pub, a = self.f.publisher, self.f.a
        result = self.f.install()
        self.assertEqual(result["phase"], "verified")
        self.assertEqual(self.f.fake.commands, [p.COMMANDS[x] for x in ("stop", "reload", "start")])
        self.assertEqual(pub.inspect()["state"], "owned")
        root_count = self.f.fake.root_calls
        self.f.fake.commands.clear()
        self.f.install()
        self.assertEqual(self.f.fake.commands, [])
        self.assertEqual(self.f.fake.root_calls, root_count)
        # Same payload, new immutable source: metadata-only, no restart.
        metadata = self.f.artifact(revision="d" * 40)
        self.f.install(metadata)
        self.assertEqual(self.f.fake.commands, [])
        changed = self.f.artifact(revision="e" * 40, pretty=True)
        self.f.install(changed)
        roots = list((self.f.home / p.STATE / "roots").iterdir())
        rollback = pub.review(metadata, approve=True, rollback=True)
        pub.apply(rollback["id"], approve=True, rollback=True)
        self.assertEqual(pub.inspect()["current"], metadata.record())
        self.assertEqual(list((self.f.home / p.STATE / "roots").iterdir()), roots)
        # Every consumed approval is one-shot, including successful rollback.
        before = len(self.f.fake.commands)
        with self.assertRaises(p.Refusal):
            pub.apply(rollback["id"], approve=True, rollback=True)
        self.assertEqual(len(self.f.fake.commands), before)

    def test_initial_rollback_restores_absence_retains_evidence(self):
        self.f.install()
        r = self.f.publisher.review(None, approve=True, rollback=True)
        self.f.publisher.apply(r["id"], approve=True, rollback=True)
        self.assertEqual(self.f.publisher.inspect()["state"], "empty")
        for path in p.TARGETS.values():
            self.assertFalse((self.f.home / path).is_symlink())
        self.assertEqual(len(list((self.f.home / p.STATE / "roots").iterdir())), 1)
        self.assertEqual(len(list((self.f.home / p.STATE / "retired").iterdir())), 1)

    def test_foreign_identical_symlink_broken_half_pair_and_permissions(self):
        for kind in ("regular", "same-link", "broken", "directory", "hardlink", "ancestor-link", "writable"):
            with self.subTest(kind=kind):
                f = Fixture()
                try:
                    target = f.home / p.TARGETS["playback.env"]
                    target.parent.mkdir(parents=True)
                    if kind == "regular":
                        target.write_bytes(f.a.payloads["playback.env"])
                        target.chmod(0o600)
                    elif kind == "same-link":
                        target.symlink_to(f.a.directory / "playback.env")
                    elif kind == "broken":
                        target.symlink_to(f.home / "missing")
                    elif kind == "directory":
                        target.mkdir()
                    elif kind == "hardlink":
                        other = f.home / "sentinel"
                        other.write_text("private sentinel")
                        other.chmod(0o600)
                        os.link(other, target)
                    elif kind == "ancestor-link":
                        target.parent.rmdir()
                        target.parent.symlink_to(f.store)
                    else:
                        target.parent.chmod(0o777)
                    with self.assertRaises((p.Refusal, OSError)):
                        f.publisher.review(f.a, approve=True)
                    self.assertEqual(f.fake.commands, [])
                    self.assertEqual(f.fake.root_calls, 0)
                finally:
                    f.close()

    def test_review_clock_boot_source_publisher_busy_and_other_context_drift(self):
        for changed in ("expired-mono", "expired-utc", "rollback-time", "reboot", "source", "profiles", "flags", "unit", "invocation", "busy", "publisher"):
            with self.subTest(changed=changed):
                f = Fixture()
                try:
                    r = f.publisher.review(f.a, approve=True)
                    if changed == "expired-mono": f.fake.now[1] += 601
                    elif changed == "expired-utc": f.fake.now[2] += 601
                    elif changed == "rollback-time": f.fake.now[2] -= 1
                    elif changed == "reboot": f.fake.now[0] = "boot-2"
                    elif changed == "busy": f.fake.context["eligible"] = False
                    elif changed == "publisher": f.publisher.publisher_hash = "f" * 64
                    else: f.fake.context[changed] = p.digest(b"changed")
                    with self.assertRaises(p.Refusal):
                        f.publisher.apply(r["id"], approve=True)
                    self.assertEqual(f.fake.commands, [])
                finally:
                    f.close()

    def test_pending_review_discard_expiry_and_quota_no_purge(self):
        pub = self.f.publisher
        r = pub.review(self.f.a, approve=True)
        self.f.fake.now[1] += 900
        with self.assertRaises(p.Refusal): pub.review(self.f.a, approve=True)
        with self.assertRaises(p.Refusal): pub.discard(r["id"])
        pub.discard(r["id"], approve=True)
        pub.records_limit = 1
        with self.assertRaises(p.Refusal): pub.review(self.f.a, approve=True)
        self.assertEqual(len(list((self.f.home / p.STATE / "reviews").iterdir())), 1)
        self.assertEqual(len(list((self.f.home / p.STATE / "roots").iterdir())), 1)

    def test_unknown_state_missing_root_and_later_edit_refuse(self):
        self.f.install()
        pub = self.f.publisher
        for kind in ("unknown", "missing-root", "later-edit", "identical-link-replaced"):
            # Separate home for each ambiguous state; never auto-repair.
            f = Fixture()
            try:
                f.install()
                f.fake.commands.clear()
                if kind == "unknown":
                    (f.home / p.STATE / "unknown-evidence").write_text("retain")
                elif kind == "missing-root":
                    (f.home / p.STATE / "roots" / f.a.hash).unlink()
                elif kind == 'identical-link-replaced':
                    target = f.home / p.TARGETS['playback.env']
                    raw = os.readlink(target)
                    target.rename(f.home / 'retained-foreign-link')
                    target.symlink_to(raw)
                else:
                    target = f.home / p.TARGETS["playback.env"]
                    target.unlink()
                    target.write_bytes(f.a.payloads["playback.env"])
                    target.chmod(0o600)
                with self.assertRaises((p.Refusal, OSError)):
                    f.publisher.review(None, approve=True, rollback=True)
                self.assertEqual(f.fake.commands, [])
            finally:
                f.close()

    def test_no_retry_rollback_or_repair_after_helper_or_service_failure(self):
        for failure in ("backup", "stop", "reload", "start", "ready"):
            with self.subTest(failure=failure):
                f = Fixture()
                try:
                    r = f.publisher.review(f.a, approve=True)
                    f.fake.fail = failure
                    with self.assertRaises(p.Refusal): f.publisher.apply(r["id"], approve=True)
                    before = list(f.fake.commands)
                    f.fake.fail = None
                    with self.assertRaises(p.Refusal): f.publisher.apply(r["id"], approve=True)
                    with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
                    self.assertEqual(f.fake.commands, before)
                    self.assertTrue((f.home / p.STATE / "transactions" / (r["id"] + ".json")).exists())
                finally:
                    f.close()

    def test_actual_helper_exit_holds_exclusion_and_uncertainty_is_durable(self):
        f = self.f
        f.fake.fail = "root-timeout"
        errors = []
        def first():
            try: f.publisher.review(f.a, approve=True)
            except p.Refusal: errors.append("refused")
        t = threading.Thread(target=first)
        t.start()
        self.assertTrue(f.fake.entered.wait(2))
        with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
        self.assertTrue(t.is_alive())
        f.fake.release.set()
        t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(errors, ["refused"])
        f.fake.fail = None
        with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
        self.assertEqual(f.fake.commands, [])

    def test_artifact_pin_schema_values_controls_and_source_validation(self):
        a = self.f.a
        with self.assertRaises(p.Refusal): self.f.load(a.path, "0" * 64, a.revision)
        with self.assertRaises(p.Refusal): self.f.load(a.path, a.hash, "0" * 40)
        for replacement in (b'https://remote.invalid', b'../Music', b'localhost'):
            with self.subTest(replacement=replacement), self.assertRaises(p.Refusal):
                self.f.artifact(mutate=lambda values: values.__setitem__("playback.env", values["playback.env"].replace(b'127.0.0.1', replacement)))
        for key, value in (("schema", True), ("sourceRevision", None), ("account", "other"), ("secret", "SYNTHETIC_SECRET")):
            m = copy.deepcopy(a.manifest)
            m[key] = value
            raw = p.canonical(m)
            path = self.f.store / (p.digest(raw)[:32] + "-invalid-manifest")
            path.write_bytes(raw)
            with self.assertRaises(p.Refusal): self.f.load(path, p.digest(raw), a.revision)
        with self.assertRaises(p.Refusal): p.object_json(b'{"a":1,"a":2}')
        with self.assertRaises(p.Refusal): p.object_json(b'{"a":NaN}')

    def test_handoff_requires_actual_generation_links_not_equal_contents(self):
        f = self.f
        f.install()
        generation = f.store / ("d" * 32 + "-home-manager-files")
        generation.mkdir()
        proof = {"generation": str(generation), "artifactHash": f.a.hash, "approved": True}
        f.fake.transfer = proof
        with self.assertRaises(p.Refusal): f.publisher.record_transfer(approve=True)
        for name, target in p.TARGETS.items():
            dest = generation / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(f.a.payloads[name])
            live = f.home / target
            live.unlink()
            live.symlink_to(dest)
        f.publisher.record_transfer(approve=True)
        with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
        self.assertEqual(len(list((f.home / p.STATE / "roots").iterdir())), 1)

    def test_cli_mutating_modes_cannot_access_home_or_execute_commands(self):
        for mode in ("review", "apply", "review-rollback", "rollback", "discard-review", "transfer"):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/jukebox_playback.py'), mode,
                                     '--manifest', 'SYNTHETIC_SECRET'], env={**os.environ, "HOME": str(self.f.home)},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("SYNTHETIC_SECRET", result.stdout + result.stderr)
            self.assertFalse((self.f.home / ".local").exists())

    def test_root_quota_unknown_roots_and_evidence_tampering_fail_closed(self):
        for kind in ('quota', 'foreign-root', 'historical-record', 'private-mode'):
            with self.subTest(kind=kind):
                f = Fixture(roots_limit=1)
                try:
                    r = f.publisher.review(f.a, approve=True)
                    f.publisher.discard(r['id'], approve=True)
                    if kind == 'quota':
                        candidate = f.artifact(revision='e' * 40, pretty=True)
                    elif kind == 'foreign-root':
                        (f.home / p.STATE / 'roots' / ('f' * 64)).symlink_to(f.a.path)
                        candidate = f.a
                    elif kind == 'historical-record':
                        path = f.home / p.STATE / 'reviews' / (r['id'] + '.json')
                        row = json.loads(path.read_text()); row['status'] = 'unknown'
                        path.write_text(json.dumps(row)); candidate = f.a
                    else:
                        (f.home / p.STATE).chmod(0o755); candidate = f.a
                    with self.assertRaises((p.Refusal, OSError)):
                        f.publisher.review(candidate, approve=True)
                    self.assertEqual(f.fake.commands, [])
                    self.assertTrue((f.home / p.STATE / 'roots' / f.a.hash).is_symlink())
                finally: f.close()

    def test_artifact_types_extra_entries_and_hash_changes_refused(self):
        for kind in ('extra', 'symlink', 'exec', 'hardlink', 'oversize', 'changed'):
            with self.subTest(kind=kind):
                f = Fixture()
                try:
                    payload = f.a.directory / 'playback.env'
                    if kind == 'extra': (f.a.directory / 'password').write_text('SYNTHETIC_SECRET')
                    elif kind == 'symlink':
                        payload.unlink(); payload.symlink_to(f.a.directory / '90-playback.conf')
                    elif kind == 'exec': payload.chmod(0o755)
                    elif kind == 'hardlink': os.link(payload, f.root / 'other')
                    elif kind == 'oversize': payload.write_bytes(b'x' * 5000)
                    else: payload.write_bytes(b'changed')
                    with self.assertRaises((p.Refusal, OSError)):
                        f.load(f.a.path, f.a.hash, f.a.revision)
                    self.assertEqual(f.fake.commands, [])
                finally: f.close()

    def test_readonly_optimized_store_hardlinks_not_mutable_home_hardlinks(self):
        payload = self.f.a.directory / 'playback.env'
        os.link(payload, self.f.root / 'store-optimizer-link')
        payload.chmod(0o444)
        self.assertEqual(self.f.load(self.f.a.path, self.f.a.hash, self.f.a.revision).hash, self.f.a.hash)
        # Mutable private records still require link count one even when read-only.
        self.f.fs.mkdir(p.STATE)
        record = self.f.home / p.STATE / 'record'
        record.write_text('{}'); record.chmod(0o600)
        os.link(record, self.f.home / 'foreign-record-link')
        with self.assertRaises(p.Refusal): self.f.fs.read(p.STATE + '/record')

    def test_nonfinite_clock_and_raw_preflight_or_backup_data_never_persist(self):
        for kind in ('clock', 'preflight', 'backup'):
            with self.subTest(kind=kind):
                f = Fixture()
                try:
                    if kind == 'clock': f.fake.now[1] = float('nan')
                    if kind == 'preflight': f.fake.context['password'] = 'SYNTHETIC_SECRET'
                    if kind == 'backup':
                        r = f.publisher.review(f.a, approve=True)
                        f.fake.backup = lambda _: {'id': 'SYNTHETIC_SECRET'}
                        with self.assertRaises(p.Refusal): f.publisher.apply(r['id'], approve=True)
                    else:
                        with self.assertRaises(p.Refusal): f.publisher.review(f.a, approve=True)
                    for path in f.home.rglob('*.json'):
                        self.assertNotIn(b'SYNTHETIC_SECRET', path.read_bytes())
                    self.assertEqual(f.fake.commands, [])
                finally: f.close()

    def test_first_pointer_collision_does_not_overwrite_foreign_file(self):
        f = self.f
        r = f.publisher.review(f.a, approve=True)
        inserted = [False]
        def race(label):
            if label == 'pointer-stage' and not inserted[0]:
                inserted[0] = True
                (f.home / p.STATE / 'active').write_text('foreign sentinel')
                (f.home / p.STATE / 'active').chmod(0o600)
        f.fs.fault = race
        with self.assertRaises((p.Refusal, OSError)): f.publisher.apply(r['id'], approve=True)
        self.assertEqual((f.home / p.STATE / 'active').read_text(), 'foreign sentinel')
        self.assertEqual(f.fake.commands, [p.COMMANDS['stop']])

    def test_cli_unknown_arguments_and_values_are_not_reflected(self):
        for args in (['SYNTHETIC_SECRET'], ['inspect', '--unknown', 'SYNTHETIC_SECRET'],
                     ['inspect', '--manifest', 'SYNTHETIC_SECRET']):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/jukebox_playback.py'), *args],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('SYNTHETIC_SECRET', result.stderr + result.stdout)

    def test_command_allowlist_and_busy_contention_are_not_queues(self):
        with self.assertRaises(p.Refusal): self.f.fake.command(('systemctl', 'restart', 'mpd'))
        with self.f.publisher.lock(create=True):
            with self.assertRaises(p.Refusal): self.f.publisher.review(self.f.a, approve=True)
        self.assertEqual(self.f.fake.commands, [])

    def test_post_review_parent_link_and_artifact_drift_do_not_touch_service(self):
        for kind in ('link', 'parent', 'artifact'):
            with self.subTest(kind=kind):
                f = Fixture()
                try:
                    f.install(); f.fake.commands.clear()
                    r = f.publisher.review(None, approve=True, rollback=True)
                    if kind == 'link':
                        target = f.home / p.TARGETS['playback.env']
                        target.unlink(); target.write_text('later user change'); target.chmod(0o600)
                    elif kind == 'parent':
                        (f.home / '.config/jukebox').chmod(0o777)
                    else:
                        (f.a.directory / 'playback.env').write_text('tampered store fixture')
                    with self.assertRaises((p.Refusal, OSError)):
                        f.publisher.apply(r['id'], approve=True, rollback=True)
                    self.assertEqual(f.fake.commands, [])
                finally: f.close()

    def test_rollback_and_update_faults_at_each_filesystem_boundary(self):
        for operation in ('update', 'rollback'):
            labels = []
            def execute(f):
                target = f.artifact(revision='e' * 40, pretty=True) if operation == 'update' else None
                r = f.publisher.review(target, approve=True, rollback=operation == 'rollback')
                f.publisher.apply(r['id'], approve=True, rollback=operation == 'rollback')
            f = Fixture()
            try:
                f.install(); f.fake.commands.clear(); f.fs.fault = labels.append; execute(f)
            finally: f.close()
            self.assertGreater(len(labels), 50)
            for index in range(len(labels)):
                with self.subTest(operation=operation, boundary=index, label=labels[index]):
                    f = Fixture()
                    try:
                        f.install(); f.fake.commands.clear(); count = [0]
                        def fail(_):
                            n = count[0]; count[0] += 1
                            if n == index: raise RuntimeError('Injected fixture crash')
                        f.fs.fault = fail
                        with self.assertRaises((RuntimeError, p.Refusal, OSError)): execute(f)
                        before = list(f.fake.commands)
                        if before:
                            with self.assertRaises((p.Refusal, OSError)):
                                f.publisher.review(f.a, approve=True)
                        self.assertEqual(f.fake.commands, before)
                    finally: f.close()

    def test_every_filesystem_boundary_fault_retains_guard_without_automatic_resume(self):
        labels = []
        f = Fixture(fault=labels.append)
        try: f.install()
        finally: f.close()
        self.assertGreater(len(labels), 60)
        for index in range(len(labels)):
            with self.subTest(boundary=index, label=labels[index]):
                count = [0]
                def fail(_):
                    n = count[0]
                    count[0] += 1
                    if n == index: raise RuntimeError("Injected fixture crash")
                f = Fixture(fault=fail)
                try:
                    with self.assertRaises((RuntimeError, p.Refusal, OSError)): f.install()
                    commands = list(f.fake.commands)
                    # Only inspect/review attempts, never recovery. If service actions occurred,
                    # retained nonterminal/registry/path evidence must prohibit another apply.
                    if commands:
                        with self.assertRaises((p.Refusal, OSError)):
                            f.publisher.review(f.a, approve=True)
                    self.assertEqual(f.fake.commands, commands)
                finally:
                    f.close()


if __name__ == "__main__":
    unittest.main()
