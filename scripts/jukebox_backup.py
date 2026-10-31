"""Read sealed, already-prepared offline copies; no backup producer or live IO.

All opens are read-only. Exact bounded namespace/identity checks precede SQLite;
only the checked offline descriptor uses immutable=1. Live WAL observation stays
in jukebox_window.database_digest. No retry, repair, cleanup or file creation.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import stat
import time

from jukebox_playback import HEX, require
from jukebox_window import database_contents

SUBDIRS = {'transactions', 'save-transactions', 'tag-transactions', 'restore-transactions'}
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def expected_files(dataset):
    require(type(dataset) is dict and set(dataset) == {'database', 'state', 'telemetry', 'environment', 'playlists'},
            'Unknown sealed dataset')
    require(type(dataset['state']) is dict and len(dataset['state']) <= 500
            and type(dataset['telemetry']) is dict and len(dataset['telemetry']) <= 25000, 'Sealed dataset bound')
    result = {'receipt.json': 2 * 1024 ** 2, 'jukebox.sqlite': 8 * 1024 ** 3, 'configuration.env': 32 * 1024 ** 2}
    for name, meta in dataset['state'].items():
        require(type(name) is str and name not in ('', '.', '..') and '/' not in name and '\\' not in name
                and '\0' not in name and type(meta) is dict and set(meta) == {'hash', 'size', 'mode'}
                and type(meta['hash']) is str and HEX.fullmatch(meta['hash']) and type(meta['size']) is int
                and 0 <= meta['size'] <= 32 * 1024 ** 2 and type(meta['mode']) is int
                and 0 <= meta['mode'] <= 0o777, 'Unsupported sealed state entry')
        result['app-files/' + name] = 32 * 1024 ** 2
    for name, value in dataset['telemetry'].items():
        require(type(name) is str and '\\' not in name and '\0' not in name and name.endswith(('.json', '.jsonl')),
                'Unsupported sealed telemetry name')
        parts = name.split('/')
        require(all(x not in ('', '.', '..') for x in parts) and
                (len(parts) == 1 or (len(parts) == 2 and parts[0] in SUBDIRS)) and
                type(value) is str and HEX.fullmatch(value), 'Unsupported sealed telemetry entry')
        result['telemetry-metadata/' + name] = 8 * 1024 ** 2
    return result


class SealedBundle:
    def __init__(self, path, dataset, uid):
        self.path, self.uid = Path(path), uid
        require(self.path.is_absolute() and self.path == Path(os.path.abspath(self.path)), 'Absolute sealed path required')
        self.expected = expected_files(dataset)
        self.fd = None

    def _root(self):
        fd = os.open('/', DIR_FLAGS)
        try:
            for name in self.path.parts[1:]:
                nxt = os.open(name, DIR_FLAGS, dir_fd=fd)
                os.close(fd); fd = nxt
                s = os.fstat(fd)
                require(s.st_uid in (0, self.uid) and
                        (not s.st_mode & 0o022 or (s.st_uid == 0 and s.st_mode & stat.S_ISVTX)), 'Unsafe sealed ancestry')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _scan(self):
        result = {}; files = set(); total = 0
        allowed_dirs = {'app-files', 'telemetry-metadata'} | {'telemetry-metadata/' + name for name in SUBDIRS}
        def walk(fd, relative):
            nonlocal total
            before = os.fstat(fd)
            require(before.st_uid == self.uid and not before.st_mode & 0o077, 'Sealed directory must be private')
            result[relative] = identity(before)
            with os.scandir(fd) as entries:
                for entry in entries:
                    require(len(result) < 30000, 'Sealed namespace bound')
                    name = relative + '/' + entry.name if relative else entry.name
                    require(name not in ('.receipt-export-intent.json', '.receipt-pending'), 'Uncertain receipt export; no recovery')
                    s = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(s.st_mode):
                        require(name in allowed_dirs, 'Unknown sealed directory')
                        child = os.open(entry.name, DIR_FLAGS, dir_fd=fd)
                        try:
                            require(identity(os.fstat(child)) == identity(s), 'Sealed directory changed')
                            walk(child, name)
                        finally: os.close(child)
                    else:
                        require(name in self.expected or name == 'export.json', 'Unknown sealed file/SQLite sidecar')
                        require(stat.S_ISREG(s.st_mode) and s.st_uid == self.uid and s.st_nlink == 1
                                and not s.st_mode & 0o077 and s.st_size <= self.expected.get(name, 65536), 'Unsafe sealed file')
                        files.add(name); result[name] = identity(s)
                        if name != 'jukebox.sqlite': total += s.st_size
                        require(total <= 512 * 1024 ** 2, 'Sealed metadata byte bound')
            require(identity(os.fstat(fd)) == identity(before), 'Sealed namespace changed')
        walk(self.fd, '')
        require(files - {'export.json'} == set(self.expected), 'Missing/extra sealed copies')
        return result

    def __enter__(self):
        self.fd = self._root()
        try:
            self.snapshot = self._scan()
            return self
        except BaseException:
            os.close(self.fd); self.fd = None
            raise

    def recheck(self):
        # Reopen only to prove the named root still identifies the anchored root.
        named = self._root()
        try: require(identity(os.fstat(named)) == self.snapshot[''], 'Sealed root identity changed')
        finally: os.close(named)
        require(self._scan() == self.snapshot, 'Sealed evidence/namespace changed')

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None: self.recheck()
        finally:
            os.close(self.fd); self.fd = None

    @contextmanager
    def opened(self, relative):
        require(relative in self.snapshot and (relative in self.expected or relative == 'export.json'), 'Unreviewed sealed file')
        parent = os.dup(self.fd); fd = None
        try:
            prefix = ''
            for name in relative.split('/')[:-1]:
                prefix = prefix + '/' + name if prefix else name
                nxt = os.open(name, DIR_FLAGS, dir_fd=parent)
                os.close(parent); parent = nxt
                require(identity(os.fstat(parent)) == self.snapshot[prefix], 'Sealed parent changed')
            name = relative.split('/')[-1]
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            require(identity(os.fstat(fd)) == self.snapshot[relative], 'Sealed copy changed')
            yield fd
            require(identity(os.fstat(fd)) == self.snapshot[relative] and
                    identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == self.snapshot[relative], 'Sealed copy changed')
        finally:
            if fd is not None: os.close(fd)
            os.close(parent)

    def read(self, relative):
        limit = self.expected.get(relative, 65536)
        with self.opened(relative) as fd:
            data = bytearray()
            while True:
                chunk = os.read(fd, min(65536, limit + 1 - len(data)))
                if not chunk: break
                data.extend(chunk); require(len(data) <= limit, 'Sealed copy exceeds bound')
            require(len(data) == os.fstat(fd).st_size, 'Sealed copy read incomplete')
            return bytes(data)

    def database(self):
        self.recheck()  # Sidecars/foreign evidence appearing after receipt read still refuse before SQLite.
        with self.opened('jukebox.sqlite') as fd:
            deadline = time.monotonic() + 60
            db = sqlite3.connect('file:/proc/self/fd/' + str(fd) + '?mode=ro&immutable=1', uri=True, timeout=1)
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            def check(): require(time.monotonic() < deadline, 'Sealed SQLite deadline')
            try: return database_contents(db, check)
            finally: db.close()
