"""Whole-group ownership and closure: virtual proc/cgroup trees only."""
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jukebox_native as n
import jukebox_playback as p
from test_jukebox_native_fixture import NativeFixture


def group(x): return x.paths['cgroup'] / 'user.slice' / n.UNIT

def actions(x): return [args for tool, args in x.calls if tool == 'systemctl' and 'show' not in args]


def empty_stopped_group(x):
    x.active = False
    shutil.rmtree(x.paths['proc'] / str(x.pid))
    (group(x) / 'cgroup.procs').write_text('')
    (group(x) / 'cgroup.events').write_text('populated 0\nfrozen 0\n')


def compiler(x, thread='1100'):
    pid = '200'; proc = x.paths['proc'] / pid
    (proc / 'task' / pid).mkdir(parents=True)
    fields = ['S'] + ['0'] * 18 + ['23456'] + ['0'] * 4
    (proc / 'stat').write_text(pid + ' (esbuild) ' + ' '.join(fields))
    executable = x.paths['app'] / 'node_modules/@esbuild/linux-x64/bin/esbuild'
    (proc / 'exe').symlink_to(executable)
    (proc / 'cmdline').write_bytes(str(executable).encode() + b'\0--service=0.25\0--ping\0')
    (proc / 'task' / pid / 'children').write_text('')
    (x.paths['proc'] / str(x.pid) / 'task' / thread / 'children').write_text(pid)
    (group(x) / 'cgroup.procs').write_text(str(x.pid) + '\n' + pid + '\n')
    return proc


class OwnershipTests(unittest.TestCase):
    def test_extra_active_cgroup_process_is_not_an_eligible_manager(self):
        x = NativeFixture()
        try:
            (group(x) / 'cgroup.procs').write_text('100\n999\n')
            with self.assertRaises((p.Refusal, OSError)): x.io.observe()
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_unknown_worker_thread_child_cannot_hide_from_ownership_checks(self):
        x = NativeFixture()
        try:
            (x.paths['proc'] / '100/task/1100/children').write_text('999\n')
            with self.assertRaises((p.Refusal, OSError)): x.io.observe()
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_empty_direct_membership_is_not_recursive_closure(self):
        x = NativeFixture()
        try:
            x.io.observe(); shutil.rmtree(x.paths['proc'] / '100'); x.active = False
            (group(x) / 'cgroup.procs').write_text('')
            nested = group(x) / 'unexpected'; nested.mkdir(); (nested / 'cgroup.procs').write_text('999\n')
            with self.assertRaises((p.Refusal, OSError)): x.io.observe(stopped=True)
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_known_compiler_from_main_or_loader_thread_has_exact_group_membership(self):
        for thread in ('100', '1100'):
            x = NativeFixture()
            try:
                compiler(x, thread)
                self.assertTrue(x.io.observe()['jobsIdle'])
                self.assertIsNotNone(x.io.manager_group_identity)
                self.assertEqual(actions(x), [])
            finally: x.close()

    def test_known_child_does_not_excuse_omitted_extra_duplicate_or_foreign_group_owners(self):
        for kind in ('omitted', 'extra', 'duplicate-child', 'grandchild', 'worker-grandchild', 'wrong-exe', 'wrong-argv'):
            with self.subTest(kind=kind):
                x = NativeFixture()
                try:
                    child = compiler(x)
                    if kind == 'omitted': (group(x) / 'cgroup.procs').write_text('100')
                    elif kind == 'extra': (group(x) / 'cgroup.procs').write_text('100\n200\n999')
                    elif kind == 'duplicate-child': (x.paths['proc'] / '100/task/100/children').write_text('200')
                    elif kind == 'grandchild': (child / 'task/200/children').write_text('999')
                    elif kind == 'worker-grandchild':
                        worker = child / 'task/201'; worker.mkdir(); (worker / 'children').write_text('999')
                    elif kind == 'wrong-exe':
                        (child / 'exe').unlink(); (child / 'exe').symlink_to(x.node)
                    else: (child / 'cmdline').write_bytes(b'foreign\0--wrong-args\0')
                    with self.assertRaises((p.Refusal, OSError)): x.io.observe()
                    self.assertEqual(actions(x), [])
                finally: x.close()

    def test_unexpected_empty_or_populated_subgroups_refuse_while_active(self):
        for populated in (False, True):
            x = NativeFixture()
            try:
                nested = group(x) / 'unexpected'; nested.mkdir()
                (nested / 'cgroup.procs').write_text('999' if populated else '')
                with self.assertRaises(p.Refusal): x.io.observe()
                self.assertTrue(nested.exists()); self.assertEqual(actions(x), [])
            finally: x.close()

    def test_active_group_procs_events_and_node_types_must_be_available_bounded_and_consistent(self):
        cases = [('procs', '100\n100'), ('procs', '0100'), ('procs', '0'), ('procs', '100 foreign'),
                 ('procs', '9' * 8200), ('events', 'populated 0\nfrozen 0\n'),
                 ('events', 'populated 1\nfrozen 1\n'), ('events', 'populated 1\n'),
                 ('events', 'populated 1\nfrozen 0\nforeign 0\n'),
                 ('events', 'populated 1\npopulated 1\nfrozen 0\n'),
                 ('events', 'x' * 4100), ('missing-events', ''), ('symlink-events', ''),
                 ('fifo-events', ''), ('missing-procs', ''), ('symlink-group', '')]
        for kind, text in cases:
            with self.subTest(kind=kind, text=text[:20]):
                x = NativeFixture()
                try:
                    if kind in ('events', 'procs'): (group(x) / ('cgroup.' + kind)).write_text(text)
                    elif kind == 'symlink-group':
                        saved = group(x).with_name('retained'); group(x).rename(saved); group(x).symlink_to(saved)
                    else:
                        name = 'cgroup.procs' if kind == 'missing-procs' else 'cgroup.events'
                        path = group(x) / name; path.unlink()
                        if kind == 'symlink-events': path.symlink_to(group(x) / 'absent')
                        if kind == 'fifo-events': os.mkfifo(path)
                    with self.assertRaises((p.Refusal, OSError)): x.io.observe()
                    self.assertEqual(actions(x), [])
                finally: x.close()

    def test_stopped_group_may_only_be_same_empty_unfrozen_group_or_proven_absence(self):
        for kind in ('empty', 'gone', 'population', 'frozen', 'replaced', 'missing-events', 'missing-root', 'subgroup'):
            with self.subTest(kind=kind):
                x = NativeFixture()
                try:
                    x.io.observe(); empty_stopped_group(x)
                    if kind == 'gone': shutil.rmtree(group(x))
                    elif kind == 'population': (group(x) / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
                    elif kind == 'frozen': (group(x) / 'cgroup.events').write_text('populated 0\nfrozen 1\n')
                    elif kind == 'replaced':
                        group(x).rename(group(x).with_name('retained'))
                        group(x).mkdir(); (group(x) / 'cgroup.procs').write_text(''); (group(x) / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
                    elif kind == 'missing-events': (group(x) / 'cgroup.events').unlink()
                    elif kind == 'missing-root': x.paths['cgroup'].rename(x.paths['cgroup'].with_name('retained-cgroup-root'))
                    elif kind == 'subgroup': (group(x) / 'unexpected').mkdir()
                    if kind in ('empty', 'gone'): self.assertTrue(x.io.observe(stopped=True)['processClosed'])
                    else:
                        with self.assertRaises((p.Refusal, OSError)): x.io.observe(stopped=True)
                    self.assertEqual(actions(x), [])
                finally: x.close()

    def test_missing_unreadable_or_unavailable_proc_metadata_is_not_exit(self):
        for kind in ('missing-stat', 'denied-stat', 'missing-root', 'reused-pid'):
            x = NativeFixture()
            try:
                x.io.observe(); x.active = False
                (group(x) / 'cgroup.procs').write_text(''); (group(x) / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
                path = x.paths['proc'] / '100/stat'
                if kind == 'missing-stat': path.unlink()
                if kind == 'missing-root': x.paths['proc'].rename(x.paths['proc'].with_name('retained-proc-root'))
                if kind == 'reused-pid': path.write_text(path.read_text().replace('12345', '54321'))
                original = n.kernel_text
                def read(fd, name, *args):
                    if kind == 'denied-stat' and name == 'stat': raise PermissionError('synthetic denied metadata')
                    return original(fd, name, *args)
                with patch.object(n, 'kernel_text', side_effect=read):
                    if kind == 'reused-pid': self.assertTrue(x.io.observe(stopped=True)['processClosed'])
                    else:
                        with self.assertRaises((p.Refusal, OSError)): x.io.observe(stopped=True)
                self.assertEqual(actions(x), [])
            finally: x.close()

    def test_permission_denial_in_group_ancestry_is_not_missing_group(self):
        x = NativeFixture()
        try:
            x.io.observe(); empty_stopped_group(x); original = n.os.open
            def denied(path, *args, **kwargs):
                if path == 'user.slice': raise PermissionError('synthetic denied ancestry')
                return original(path, *args, **kwargs)
            with patch.object(n.os, 'open', side_effect=denied):
                with self.assertRaises(PermissionError): x.io.observe(stopped=True)
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_mid_read_group_membership_identity_and_pid_changes_refuse(self):
        for kind in ('members', 'group-identity', 'subgroup', 'pid-start'):
            x = NativeFixture()
            try:
                if kind == 'pid-start':
                    original = n.cgroup_snapshot
                    def changed(*args, **kwargs):
                        result = original(*args, **kwargs)
                        path = x.paths['proc'] / '100/stat'; path.write_text(path.read_text().replace('12345', '54321'))
                        return result
                    with patch.object(n, 'cgroup_snapshot', side_effect=changed):
                        with self.assertRaises(p.Refusal): x.io.observe()
                else:
                    original = n.kernel_text; count = [0]
                    def changed(fd, name, *args):
                        result = original(fd, name, *args)
                        if name == 'cgroup.events':
                            count[0] += 1
                            if kind == 'members' and count[0] == 1: (group(x) / 'cgroup.procs').write_text('100\n999')
                            if kind == 'subgroup' and count[0] == 2: (group(x) / 'unexpected').mkdir()
                            if kind == 'group-identity' and count[0] == 2:
                                group(x).rename(group(x).with_name('retained'))
                                group(x).mkdir(); (group(x) / 'cgroup.procs').write_text('100'); (group(x) / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
                        return result
                    with patch.object(n, 'kernel_text', side_effect=changed):
                        with self.assertRaises(p.Refusal): x.io.observe()
                self.assertEqual(actions(x), [])
            finally: x.close()

    def test_unknown_metadata_failure_does_not_leak_descriptors_or_clean_evidence(self):
        x = NativeFixture()
        try:
            (group(x) / 'cgroup.events').write_text('populated 1\nunknown 0\n')
            before = len(os.listdir('/proc/self/fd'))
            for _ in range(3):
                with self.assertRaises(p.Refusal): x.io.observe()
            self.assertEqual(len(os.listdir('/proc/self/fd')), before)
            self.assertEqual((group(x) / 'cgroup.events').read_text(), 'populated 1\nunknown 0\n')
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_thread_child_metadata_must_be_bounded_present_and_canonical(self):
        for kind in ('missing', 'oversized', 'bad-pid', 'duplicate', 'bad-main-name', 'unknown-thread-id'):
            x = NativeFixture()
            try:
                path = x.paths['proc'] / '100/task/1100/children'
                if kind == 'missing': path.unlink()
                elif kind == 'oversized': path.write_text('2 ' * 5000)
                elif kind == 'bad-pid': path.write_text('000200')
                elif kind == 'duplicate': path.write_text('200 200')
                elif kind == 'bad-main-name':
                    (x.paths['proc'] / '100/task/100/comm').write_text('WorkerThread')
                    (x.paths['proc'] / '100/task/1100/comm').write_text('MainThread')
                else:
                    (x.paths['proc'] / '100/task/1100').rename(x.paths['proc'] / '100/task/01100')
                with self.assertRaises((p.Refusal, OSError)): x.io.observe()
                self.assertEqual(actions(x), [])
            finally: x.close()

    def test_group_path_and_namespace_bounds_fail_closed_without_descriptor_leaks(self):
        x = NativeFixture()
        try:
            before = len(os.listdir('/proc/self/fd'))
            for path in ('relative', '/user.slice/../' + n.UNIT, '//user.slice/' + n.UNIT,
                         '/./' + n.UNIT, '/x' * 200 + '/' + n.UNIT):
                with self.assertRaises(p.Refusal): n.cgroup_snapshot(x.paths['cgroup'], path)
            for index in range(513): (group(x) / ('controller-' + str(index))).write_text('')
            with self.assertRaises(p.Refusal): x.io.observe()
            self.assertEqual(len(os.listdir('/proc/self/fd')), before)
            self.assertEqual(actions(x), [])
        finally: x.close()

    def test_stale_ownership_recheck_blocks_a_review_before_any_service_command(self):
        x = NativeFixture()
        try:
            x.seal_backup(); x.f.publisher.adapter = x.make_adapter(x.f.a)
            reviewed = x.f.publisher.review(x.f.a, approve=True)
            (group(x) / 'cgroup.procs').write_text('100\n999')
            with self.assertRaises(p.Refusal): x.f.publisher.apply(reviewed['id'], approve=True)
            self.assertEqual(actions(x), [])
        finally: x.close()


if __name__ == '__main__': unittest.main()
