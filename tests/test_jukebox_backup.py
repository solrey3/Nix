"""Only owned synthetic offline bundles; no live app, service or credentials."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jukebox_backup as b
from jukebox_playback import Refusal, canonical, digest
from jukebox_window import database_digest


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sealed-copy-fixture-')
        self.parent = Path(self.tmp.name)
        self.root = self.parent / 'bundle'; self.root.mkdir(mode=0o700)
        db = sqlite3.connect(self.root / 'jukebox.sqlite')
        db.executescript('CREATE TABLE tracks(id INTEGER PRIMARY KEY,title TEXT);'
                         'INSERT INTO tracks VALUES(1,"fixture");'
                         'CREATE TABLE editions(id TEXT PRIMARY KEY,title TEXT) WITHOUT ROWID;'
                         'INSERT INTO editions VALUES("a","fixture edition");')
        db.close(); (self.root / 'jukebox.sqlite').chmod(0o600)
        self.write('configuration.env', b'SYNTHETIC_ONLY=not-a-secret\n')
        self.write('app-files/scan-state.json', b'{"running":false}')
        self.write('telemetry-metadata/transactions/fixture.json', b'{"status":"complete"}')
        self.dataset = {'database': database_digest(self.root / 'jukebox.sqlite'),
                        'environment': digest((self.root / 'configuration.env').read_bytes()),
                        'state': {'scan-state.json': {'hash': digest(b'{"running":false}'), 'size': 17, 'mode': 0o644}},
                        'telemetry': {'transactions/fixture.json': digest(b'{"status":"complete"}')},
                        'playlists': {'count': 0, 'hash': digest(b'')}}
        self.write('receipt.json', canonical({'schema': 1, 'dataset': self.dataset}))

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for parent in p.parents:
            if parent == self.root: break
            parent.chmod(0o700)
        p.write_bytes(data); p.chmod(0o600)

    def bundle(self): return b.SealedBundle(self.root, self.dataset, os.geteuid())
    def close(self): self.tmp.cleanup()
    def snapshot(self):
        return {str(p.relative_to(self.root)): (b.identity(p.lstat()), p.read_bytes())
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}


class SealedCopyTests(unittest.TestCase):
    def test_descriptor_immutable_transport_matches_live_encoding_without_touching_copies(self):
        f = Fixture()
        try:
            before = f.snapshot(); connect = b.sqlite3.connect; calls = []
            def capture(database, **kwargs):
                calls.append((database, kwargs)); return connect(database, **kwargs)
            with patch.object(b.sqlite3, 'connect', side_effect=capture):
                with f.bundle() as bundle:
                    self.assertEqual(bundle.database(), f.dataset['database'])
                    self.assertEqual(bundle.read('configuration.env'), b'SYNTHETIC_ONLY=not-a-secret\n')
                    self.assertEqual(bundle.read('app-files/scan-state.json'), b'{"running":false}')
                    self.assertEqual(bundle.read('telemetry-metadata/transactions/fixture.json'), b'{"status":"complete"}')
            self.assertEqual(len(calls), 1)
            self.assertRegex(calls[0][0], r'^file:/proc/self/fd/\d+\?mode=ro&immutable=1$')
            self.assertTrue(calls[0][1]['uri'])
            self.assertEqual(f.snapshot(), before)
            self.assertFalse(any((f.root / ('jukebox.sqlite' + suffix)).exists() for suffix in ('-wal', '-shm', '-journal')))
        finally: f.close()

    def test_unknown_nodes_sidecars_and_unsafe_namespaces_refuse_before_sqlite(self):
        for kind in ('unknown-file', 'unknown-nested-file', 'unknown-dir', 'unknown-nested-dir',
                     'wal', 'shm', 'journal', 'dangling', 'symlink', 'hardlink', 'fifo',
                     'file-mode', 'directory-mode', 'bundle-mode', 'missing', 'wrong-type'):
            with self.subTest(kind=kind):
                f = Fixture()
                try:
                    if kind == 'unknown-file': f.write('foreign.json', b'')
                    elif kind == 'unknown-nested-file': f.write('telemetry-metadata/transactions/foreign.json', b'')
                    elif kind == 'unknown-dir': (f.root / 'foreign').mkdir(mode=0o700)
                    elif kind == 'unknown-nested-dir': (f.root / 'app-files/foreign').mkdir(mode=0o700)
                    elif kind in ('wal', 'shm', 'journal'): f.write('jukebox.sqlite-' + kind, b'')
                    elif kind == 'dangling': (f.root / 'foreign').symlink_to(f.parent / 'absent')
                    elif kind == 'symlink':
                        p = f.root / 'configuration.env'; p.rename(f.parent / 'saved'); p.symlink_to(f.parent / 'saved')
                    elif kind == 'hardlink': os.link(f.root / 'configuration.env', f.parent / 'hardlink')
                    elif kind == 'fifo':
                        (f.root / 'configuration.env').unlink(); os.mkfifo(f.root / 'configuration.env', 0o600)
                    elif kind == 'file-mode': (f.root / 'configuration.env').chmod(0o644)
                    elif kind == 'directory-mode': (f.root / 'app-files').chmod(0o755)
                    elif kind == 'bundle-mode': f.root.chmod(0o755)
                    elif kind == 'missing': (f.root / 'receipt.json').unlink()
                    elif kind == 'wrong-type':
                        (f.root / 'configuration.env').unlink(); (f.root / 'configuration.env').mkdir(mode=0o700)
                    with patch.object(b.sqlite3, 'connect', side_effect=AssertionError('No SQLite open')):
                        with self.assertRaises((Refusal, OSError)):
                            with f.bundle(): pass
                    self.assertTrue(f.root.exists(), 'No evidence cleanup')
                finally: f.close()

    def test_unknown_root_or_nested_entry_appearing_after_open_blocks_sqlite(self):
        for name in ('jukebox.sqlite-wal', 'telemetry-metadata/transactions/foreign.json'):
            f = Fixture()
            try:
                with self.assertRaises(Refusal):
                    with f.bundle() as bundle:
                        f.write(name, b'')
                        with patch.object(b.sqlite3, 'connect', side_effect=AssertionError('No SQLite open')):
                            bundle.database()
                self.assertTrue((f.root / name).exists())
            finally: f.close()

    def test_final_recheck_refuses_late_extra_or_changed_copy_even_if_bytes_match(self):
        for kind in ('extra', 'same-bytes-replacement', 'edited', 'parent-replacement', 'root-replacement', 'proof-added'):
            f = Fixture()
            try:
                with self.assertRaises(Refusal):
                    with f.bundle() as bundle:
                        bundle.database(); bundle.read('configuration.env')
                        if kind == 'extra': f.write('foreign.json', b'')
                        elif kind == 'same-bytes-replacement':
                            p = f.root / 'configuration.env'; data = p.read_bytes(); p.unlink(); f.write('configuration.env', data)
                        elif kind == 'edited': f.write('configuration.env', b'changed')
                        elif kind == 'parent-replacement':
                            (f.root / 'app-files').rename(f.root / 'app-files-old'); (f.root / 'app-files').mkdir(mode=0o700)
                        elif kind == 'root-replacement':
                            f.root.rename(f.parent / 'retained'); f.root.mkdir(mode=0o700)
                        elif kind == 'proof-added': f.write('export.json', b'{}')
            finally: f.close()

    def test_file_replacement_during_sqlite_open_is_detected_without_rewriting_it(self):
        f = Fixture()
        try:
            connect = b.sqlite3.connect
            def replaced(database, **kwargs):
                p = f.root / 'jukebox.sqlite'; data = p.read_bytes()
                p.rename(f.root / 'retained.sqlite'); f.write('jukebox.sqlite', data)
                return connect(database, **kwargs)
            with self.assertRaises((Refusal, sqlite3.OperationalError)):
                with f.bundle() as bundle:
                    with patch.object(b.sqlite3, 'connect', side_effect=replaced): bundle.database()
            self.assertTrue((f.root / 'retained.sqlite').exists())
        finally: f.close()

    def test_private_no_follow_ancestry_and_replaced_root_refuse(self):
        for kind in ('symlink', 'parent-mode'):
            f = Fixture()
            try:
                if kind == 'symlink':
                    actual = f.parent / 'actual'; f.root.rename(actual); f.root.symlink_to(actual)
                else: f.parent.chmod(0o777)
                with self.assertRaises((Refusal, OSError)):
                    with f.bundle(): pass
            finally: f.parent.chmod(0o700); f.close()

    def test_dataset_paths_are_validated_before_opening_the_bundle(self):
        for mutate in (lambda d: d['state'].update({'../escape': next(iter(d['state'].values()))}),
                       lambda d: d['telemetry'].update({'transactions/../../escape.json': 'a' * 64}),
                       lambda d: d['state']['scan-state.json'].update(size=True)):
            f = Fixture()
            try:
                mutate(f.dataset)
                with patch.object(b.SealedBundle, '_root', side_effect=AssertionError('No path access')):
                    with self.assertRaises(Refusal):
                        with f.bundle(): pass
            finally: f.close()

    def test_deadline_cleans_up_handles_but_never_modifies_evidence(self):
        f = Fixture()
        try:
            before = f.snapshot(); descriptors = len(os.listdir('/proc/self/fd'))
            with self.assertRaises((Refusal, sqlite3.OperationalError)):
                with f.bundle() as bundle:
                    with patch.object(b.time, 'monotonic', side_effect=[0, 100000] + [100000] * 100): bundle.database()
            self.assertEqual(f.snapshot(), before)
            self.assertEqual(len(os.listdir('/proc/self/fd')), descriptors)
        finally: f.close()

    def test_live_reader_still_observes_committed_wal_but_sealed_copy_refuses_it(self):
        f = Fixture(); writer = None
        try:
            writer = sqlite3.connect(f.root / 'jukebox.sqlite')
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('INSERT INTO tracks VALUES(2,"committed WAL row")'); writer.commit()
            self.assertTrue((f.root / 'jukebox.sqlite-wal').exists())
            self.assertEqual(database_digest(f.root / 'jukebox.sqlite')['tables']['tracks']['count'], 2)
            with patch.object(b.sqlite3, 'connect', side_effect=AssertionError('No sealed SQLite open')):
                with self.assertRaises(Refusal):
                    with f.bundle(): pass
        finally:
            if writer: writer.close()
            f.close()

    def test_sealed_file_size_bound_refuses_before_sqlite(self):
        f = Fixture()
        try:
            with (f.root / 'jukebox.sqlite').open('r+b') as file: file.truncate(8 * 1024 ** 3 + 1)
            with patch.object(b.sqlite3, 'connect', side_effect=AssertionError('No SQLite open')):
                with self.assertRaises(Refusal):
                    with f.bundle(): pass
        finally: f.close()

    def test_all_five_implementation_files_participate_in_publisher_identity(self):
        import jukebox_cli as cli
        source = Path(cli.__file__).parent
        expected = digest(canonical({name: digest((source / name).read_bytes()) for name in
                           ('jukebox_playback.py', 'jukebox_window.py', 'jukebox_native.py', 'jukebox_backup.py', 'jukebox_cli.py')}))
        self.assertEqual(cli.code_identity(), expected)


if __name__ == '__main__': unittest.main()
