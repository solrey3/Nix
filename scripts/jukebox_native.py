"""Native IO for the explicitly coordinated operator-window policy.

No work at import; no credential search, MPD endpoint, profile operation or kill.
Only construction via fixed_paths() binds production. Tests inject fixture paths,
runner and API. This module is not a CLI plugin/manifest executable interface.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import urllib.error

from jukebox_playback import COMMANDS, HEX, ID, REV, STATE, Refusal, canonical, digest, object_json, require
from jukebox_window import ENDPOINTS, database_digest
from jukebox_backup import SealedBundle

UNIT = "jukebox-manager.service"
PROPS = ("MainPID", "InvocationID", "ActiveState", "SubState", "FragmentPath", "DropInPaths",
         "KillMode", "SendSIGKILL", "TimeoutStopUSec", "Result", "ControlGroup", "WorkingDirectory")


class OwnedRunner:
    """Timeout is not exit. Never kill a helper; drain before releasing exclusion."""
    def __init__(self, home, uid):
        self.home, self.uid, self.pending = str(home), uid, []
        self.tools = {n: str((Path('/run/current-system/sw/bin') / n).resolve(strict=True))
                      for n in ('systemctl', 'nix-store', 'git')}

    def run(self, name, args, timeout=15, limit=2_000_000):
        require(name in self.tools and not self.pending, "Unknown tool or pending helper")
        env = {'PATH': '/run/current-system/sw/bin', 'HOME': self.home, 'USER': 'budchris',
               'LANG': 'C.UTF-8', 'XDG_RUNTIME_DIR': f'/run/user/{self.uid}',
               'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{self.uid}/bus', 'NIX_REMOTE': 'daemon'}
        # Pin the resolved executable, but preserve its approved multicall name.
        # Nix's nix-store symlink resolves to nix; argv[0]=.../nix selects the
        # wrong CLI even though the same trusted executable is launched.
        proc = subprocess.Popen([name, *args], executable=self.tools[name], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        os.set_blocking(proc.stdout.fileno(), False)
        self.pending.append(proc)
        output = bytearray(); deadline = time.monotonic() + timeout
        try:
            while True:
                try: chunk = os.read(proc.stdout.fileno(), 65536)
                except BlockingIOError: chunk = None
                if chunk:
                    output.extend(chunk)
                    require(len(output) <= limit, "Helper output exceeds bound; exit not implied")
                if chunk == b'' and proc.poll() is not None: break
                require(time.monotonic() < deadline, "Helper deadline; exit not implied")
                if chunk is None: time.sleep(0.01)
            code = proc.wait(); proc.stdout.close(); self.pending.remove(proc)
            require(code == 0, "Helper refused; inspect without retry")
            return output.decode('utf8', errors='strict').strip()
        except BaseException:
            # Even decoding/output/deadline errors must leave a live helper owned.
            raise Refusal("Helper outcome unavailable; no retry or automatic termination") from None

    def drain(self):
        while self.pending:
            proc = self.pending[0]
            while True:
                try: chunk = os.read(proc.stdout.fileno(), 65536)
                except BlockingIOError: chunk = None
                if chunk == b'' and proc.poll() is not None: break
                if chunk is None: time.sleep(0.01)
            proc.wait(); proc.stdout.close(); self.pending.pop(0)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refusal("API redirects prohibited")


class LocalAPI:
    def __init__(self, token):
        require(type(token) is bytes and 24 <= len(token) <= 256 and
                all(33 <= c <= 126 for c in token), "Invalid private API credential channel")
        self.token = token.decode('ascii')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, endpoint):
        require(endpoint in ENDPOINTS, "Unsupported API endpoint")
        request = urllib.request.Request('http://127.0.0.1:3080/api/' + endpoint,
                                        headers={'Authorization': 'Bearer ' + self.token, 'Connection': 'close'})
        try:
            deadline = time.monotonic() + 10
            with self.opener.open(request, timeout=10) as response:
                require(response.status == 200, "API readiness unavailable")
                sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
                require(sock is not None and callable(getattr(response, 'read1', None)), 'Bounded API transport unavailable')
                body = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, 'Total API observation deadline')
                    sock.settimeout(remaining)
                    chunk = response.read1(min(65536, 2_000_001 - len(body)))
                    if not chunk: break
                    body.extend(chunk)
                    require(len(body) <= 2_000_000 and time.monotonic() <= deadline, 'API response exceeds bound/deadline')
                    if callable(getattr(response, 'isclosed', None)) and response.isclosed(): break
                body = bytes(body)
                # discovery is the sole list endpoint; strict JSON duplicate rejection still applies.
                if endpoint == 'discovery':
                    return object_json(b'{"rows":' + body + b'}', 2_000_032)['rows']
                return object_json(body, 2_000_000)
        except BaseException as error:
            if isinstance(error, urllib.error.HTTPError): error.close()
            raise Refusal("Read-only API observation unavailable") from None


def fixed_paths():
    account = pwd.getpwnam('budchris')
    require(os.geteuid() == account.pw_uid and os.geteuid() != 0 and
            socket.gethostname().split('.')[0] == 'bravo' and account.pw_dir == '/home/budchris',
            "Wrong account/host/home; no override")
    home = Path(account.pw_dir); root = Path('/mnt/files2/Jukebox')
    project = home / 'Projects/Jukebox'; app = project / 'App'
    return {'home': home, 'root': root, 'project': project, 'app': app, 'data': app / 'data',
            'telemetry': project / 'Telemetry/JukeboxApp',
            'system': Path('/run/current-system'), 'hm': Path('/etc/profiles/per-user/budchris'),
            'proc': Path('/proc'), 'store': Path('/nix/store'), 'cgroup': Path('/sys/fs/cgroup'), 'uid': account.pw_uid}


def safe_directory(path):
    q = Path(path)
    while q != q.parent:
        s = q.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid in (0, os.geteuid()) and
                (not s.st_mode & 0o022 or (s.st_uid == 0 and s.st_mode & stat.S_ISVTX)), "Unsafe metadata ancestry")
        q = q.parent


def safe_file(path, limit=32 * 1024 * 1024, uid=None, private=False):
    # Nix store source files are handled separately by the artifact verifier.
    path = Path(path); q = path.parent
    while q != q.parent:
        s = q.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid in (0, os.geteuid()) and
                (not s.st_mode & 0o022 or (s.st_uid == 0 and s.st_mode & stat.S_ISVTX)), "Unsafe metadata ancestry")
        q = q.parent
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= limit and
                (uid is None or s.st_uid == uid) and (not private or not s.st_mode & 0o077), "Unsafe metadata file")
        data = os.read(fd, limit + 1)
        require(len(data) == s.st_size and len(data) <= limit, "Metadata changed/exceeds bound")
        return data
    finally: os.close(fd)


def file_inventory(folder, allowed_dirs=(), limit=500, exclude=()):
    result = {}; folder = Path(folder)
    safe_directory(folder)
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.name in exclude: continue
            require(len(result) < limit, "Metadata inventory exceeds bound")
            s = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode):
                require(entry.name in allowed_dirs, "Unknown state directory; separate review required")
                continue
            b = safe_file(Path(entry.path), uid=os.geteuid())
            result[entry.name] = {'hash': digest(b), 'size': len(b), 'mode': stat.S_IMODE(s.st_mode)}
    return result


def kernel_text(directory, name, limit=8192):
    """Bounded read-only pseudo-file read; virtual files need not report a size."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'Unexpected kernel metadata type')
        data = bytearray()
        while True:
            chunk = os.read(fd, min(4096, limit + 1 - len(data)))
            if not chunk: break
            data.extend(chunk); require(len(data) <= limit, 'Kernel metadata exceeds bound')
        try: return data.decode('ascii')
        except UnicodeError: raise Refusal('Invalid kernel metadata encoding') from None
    finally: os.close(fd)


def process_ids(text):
    values = text.split()
    require(len(values) <= 128 and len(values) == len(set(values)) and
            all(value.isascii() and value.isdecimal() and len(value) <= 10 and str(int(value)) == value and 1 < int(value) <= 2147483647
                for value in values), 'Unknown/duplicate process metadata')
    return set(values)


def process_stat(root, pid, *, allow_missing=False):
    """Only proven PID-directory ENOENT is absence; unavailable procfs/stat is not."""
    require(pid.isascii() and pid.isdecimal() and len(pid) <= 10 and str(int(pid)) == pid
            and 1 < int(pid) <= 2147483647, 'Invalid process identity')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(root, flags)
    try:
        try: fd = os.open(pid, flags, dir_fd=parent)
        except FileNotFoundError:
            require(allow_missing, 'Process disappeared')
            return None
        try: raw = kernel_text(fd, 'stat')
        finally: os.close(fd)
    finally: os.close(parent)
    require(raw.split(' ', 1)[0] == pid and ')' in raw, 'Process metadata identity differs')
    fields = raw.rsplit(')', 1)[1].strip().split()
    require(len(fields) >= 20 and fields[19].isascii() and fields[19].isdecimal(), 'Process metadata incomplete')
    return fields


def cgroup_snapshot(root, group, *, allow_missing=False):
    """Known non-delegated cgroup-v2 layout only; never adopt or traverse subgroups."""
    root = Path(root)
    require(root.is_absolute() and root == Path(os.path.abspath(root)) and type(group) is str
            and len(group) <= 4096 and group.startswith('/') and len(group[1:].split('/')) <= 128
            and all(part not in ('', '.', '..') for part in group[1:].split('/')), 'Unsafe cgroup path')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    def opened(missing):
        fd = os.open('/', flags)
        try:
            # Missing/unavailable cgroup mount is never evidence of process exit.
            for part in root.parts[1:]:
                child = os.open(part, flags, dir_fd=fd); os.close(fd); fd = child
            for part in group[1:].split('/'):
                try: child = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    require(missing, 'Active cgroup disappeared')
                    os.close(fd); return None
                os.close(fd); fd = child
            return fd
        except BaseException:
            os.close(fd); raise
    def read(fd):
        pids = process_ids(kernel_text(fd, 'cgroup.procs'))
        events = {}
        for line in kernel_text(fd, 'cgroup.events', 4096).splitlines():
            fields = line.split()
            require(len(fields) == 2 and fields[0] in ('populated', 'frozen') and
                    fields[0] not in events and fields[1] in ('0', '1'), 'Unknown cgroup events')
            events[fields[0]] = fields[1]
        require(set(events) == {'populated', 'frozen'} and events['frozen'] == '0', 'Cgroup events unavailable/frozen')
        return pids, events['populated'] == '1'
    fd = opened(allow_missing)
    if fd is None: return None
    try:
        before = os.fstat(fd); identity = (before.st_dev, before.st_ino)
        def namespace():
            names = {}
            with os.scandir(fd) as entries:
                for count, entry in enumerate(entries):
                    require(count < 512, 'Cgroup namespace exceeds bound')
                    info = entry.stat(follow_symlinks=False)
                    require(stat.S_ISREG(info.st_mode), 'Unexpected cgroup subgroup/link/node; no adoption')
                    names[entry.name] = (info.st_dev, info.st_ino, info.st_mode)
            return names
        first = read(fd); names = namespace()
        require(read(fd) == first and namespace() == names, 'Cgroup membership/events/namespace changed')
        named = opened(False)
        try:
            current = os.fstat(named)
            require((current.st_dev, current.st_ino) == identity, 'Cgroup identity changed')
        finally: os.close(named)
        return {'identity': identity, 'pids': first[0], 'populated': first[1]}
    finally: os.close(fd)


class NativeIO:
    def __init__(self, paths, runner, api, *, now=time.time, sleep=time.sleep):
        self.p, self.runner, self.api, self.now, self.sleep = paths, runner, api, now, sleep
        self.offline = None
        self.schedule_storage = None
        self.baseline_config = None
        self.backup_receipts = {}
        self.manager_group = None
        self.manager_group_identity = None
        self.manager_runtime = None
        self.manager_process = None

    def clock(self):
        with open(self.p['proc'] / 'sys/kernel/random/boot_id', 'rb') as handle:
            raw = handle.read(257)
        require(0 < len(raw) <= 256, "Boot identity unavailable")
        boot = raw.decode().strip()
        return boot, time.clock_gettime(time.CLOCK_BOOTTIME), self.now()

    def _unit(self, name, user):
        require(name in (UNIT, 'mpd.service', 'navidrome.service'), "Unsupported unit metadata")
        args = (['--user'] if user else []) + ['show', '--all', name, *['--property=' + key for key in PROPS]]
        text = self.runner.run('systemctl', args)
        values = {}
        for line in text.splitlines():
            key, sep, value = line.partition('=')
            require(sep and key in PROPS and key not in values, "Unexpected unit metadata")
            values[key] = value
        require(set(values) == set(PROPS), "Unit metadata incomplete")
        return values

    def _dataset(self):
        data = self.p['data']; db = data / 'jukebox.sqlite'
        safe_directory(data)
        require(db.lstat().st_uid == self.p['uid'], 'Unexpected database owner')
        state = file_inventory(data, ('backups', 'deployment-backups'),
                               exclude=('jukebox.sqlite', 'jukebox.sqlite-wal', 'jukebox.sqlite-shm'))
        # Reject diagnostics/other directories rather than inventing backup coverage.
        telemetry = {}
        for sub in ('', 'transactions', 'save-transactions', 'tag-transactions', 'restore-transactions'):
            folder = self.p['telemetry'] / sub
            if not folder.exists() and not folder.is_symlink(): continue
            safe_directory(folder)
            with os.scandir(folder) as entries:
                count = 0
                for entry in entries:
                    count += 1; require(count <= 5000, "Transaction inventory exceeds bound")
                    if not entry.name.endswith(('.json', '.jsonl')): continue
                    b = safe_file(Path(entry.path), 8 * 1024 * 1024, self.p['uid'])
                    if sub and entry.name.endswith('.json'):
                        row = object_json(b, 8 * 1024 * 1024)
                        require(row.get('status') in ('complete', 'rolled-back', 'preparation-failed'), "Unsettled transaction")
                    telemetry[str(Path(sub) / entry.name)] = digest(b)
        env = safe_file(self.p['app'] / '.env', uid=self.p['uid'], private=True)
        playlists = hashlib.sha256(); count = 0; total = 0; names = []
        playlist_dir = self.p['root'] / 'Playlists'
        safe_directory(playlist_dir)
        with os.scandir(playlist_dir) as entries:
            for entry in entries:
                require(len(names) < 5000, 'Playlist namespace bound')
                names.append(entry.name)
        for name in sorted(names, key=lambda x: x.encode('utf-16be')):
            if not name.lower().endswith('.m3u'): continue
            require(count < 2000, "Playlist inventory exceeds bound")
            playlists.update(json.dumps(name, ensure_ascii=False, separators=(',', ':')).encode())
            data = safe_file(playlist_dir / name, 64 * 1024 * 1024); total += len(data)
            require(total <= 128 * 1024 * 1024, 'Playlist bytes exceed reviewed observation budget')
            playlists.update(data); count += 1
        logical, self.schedule_storage = database_digest(db, scheduler_root=self.p['root'])
        return {'database': logical, 'state': state, 'telemetry': telemetry,
                'environment': digest(env), 'playlists': {'count': count, 'hash': playlists.hexdigest()}}

    def _process(self, unit):
        pid = unit['MainPID']; require(pid.isascii() and pid.isdecimal() and len(pid) <= 10
                and 1 < int(pid) <= 2147483647 and unit['ActiveState'] == 'active' and unit['Result'] == 'success', "Manager not active/settled")
        proc = self.p['proc'] / pid
        initial = process_stat(self.p['proc'], pid)
        require(initial[0] != 'Z', 'Manager process identity unavailable')
        require((proc / 'cwd').resolve(strict=True) == self.p['app'], 'Manager cwd is not the reviewed project app')
        threads = []; tasks = []
        for entry in (proc / 'task').iterdir():
            require(len(threads) < 128 and entry.name.isascii() and entry.name.isdecimal()
                    and len(entry.name) <= 10 and str(int(entry.name)) == entry.name and int(entry.name) > 1, "Thread inventory bound/identity")
            threads.append((entry / 'comm').read_text().strip()); tasks.append(entry)
        require(threads.count('WorkerThread') == 1 and threads.count('MainThread') == 1
                and (proc / 'task' / pid) in tasks and threads[tasks.index(proc / 'task' / pid)] == 'MainThread'
                and all(x in ('MainThread', 'DelayedTaskSche', 'V8Worker',
                'SignalInspector', 'WorkerThread', 'libuv-worker') for x in threads), "Unexpected worker ownership")
        descriptors = []
        for entry in (proc / 'fd').iterdir():
            require(len(descriptors) < 512, "Descriptor inventory bound")
            descriptors.append(os.readlink(entry))
        require(str(self.p['data'] / 'jukebox.sqlite') in descriptors, "Actual app database path not proven")
        children = set()
        for task in tasks:
            fd = os.open(task, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try: found = process_ids(kernel_text(fd, 'children'))
            finally: os.close(fd)
            require(not children.intersection(found), 'Conflicting thread child ownership')
            children.update(found)
        require(len(children) <= 1 and pid not in children, "Unexpected manager children")
        package = object_json(safe_file(self.p['app'] / 'node_modules/esbuild/package.json'))
        expected = (self.p['app'] / 'node_modules/@esbuild/linux-x64/bin/esbuild').resolve(strict=True)
        child_starts = {}
        for child in children:
            require(child.isdigit(), "Invalid child identity")
            cp = self.p['proc'] / child
            status = process_stat(self.p['proc'], child)
            require(status[0] != 'Z' and (cp / 'exe').resolve(strict=True) == expected, "Unexpected/defunct child")
            argv = (cp / 'cmdline').read_bytes().split(b'\0')
            require([x.decode() for x in argv[1:] if x] == ['--service=' + package['version'], '--ping'], "Unexpected compiler ownership")
            child_tasks = []
            for task in (cp / 'task').iterdir():
                require(len(child_tasks) < 128 and task.name.isascii() and task.name.isdecimal()
                        and len(task.name) <= 10 and str(int(task.name)) == task.name and int(task.name) > 1, 'Compiler thread inventory bound/identity')
                child_tasks.append(task)
                fd = os.open(task, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try: require(not process_ids(kernel_text(fd, 'children')), 'Unexpected compiler descendants')
                finally: os.close(fd)
            require((cp / 'task' / child) in child_tasks, 'Compiler main thread unavailable')
            child_starts[child] = status[19]
        # This proves bounded observations, not an app admission lease.
        fields = process_stat(self.p['proc'], pid)
        require(fields[0] != 'Z' and fields[19] == initial[19], "Manager process identity unavailable/changed")
        group = unit['ControlGroup']
        require(group.startswith('/') and group.endswith('/' + UNIT), 'Manager cgroup identity unavailable')
        membership = cgroup_snapshot(self.p['cgroup'], group)
        require(membership is not None and membership['populated'] is True
                and membership['pids'] == children | {pid}, 'Unknown/inconsistent manager cgroup ownership')
        final = process_stat(self.p['proc'], pid)
        require(final[0] != 'Z' and final[19] == initial[19], 'Manager process changed during group observation')
        for child, start in child_starts.items():
            final_child = process_stat(self.p['proc'], child)
            require(final_child[0] != 'Z' and final_child[19] == start, 'Compiler changed during group observation')
        self.manager_group, self.manager_group_identity = group, membership['identity']
        self.manager_runtime = {'exe': str((proc / 'exe').resolve(strict=True)),
                                'argv': digest((proc / 'cmdline').read_bytes())}
        self.manager_process = (pid, fields[19])
        return digest(canonical({'pid': pid, 'invocation': unit['InvocationID'], 'start': fields[19],
                                 'cgroup': group, 'groupIdentity': membership['identity'], 'members': sorted(membership['pids']),
                                 'children': child_starts}))

    def observe(self, stopped=False):
        unit = self._unit(UNIT, True)
        require(unit['FragmentPath'] == str(self.p['home'] / '.config/systemd/user/jukebox-manager.service'), "Unexpected base unit owner")
        own = str(self.p['home'] / '.config/systemd/user/jukebox-manager.service.d/90-playback.conf')
        safety = self.p['home'] / '.config/systemd/user/jukebox-manager.service.d/80-stop-safety.conf'
        dropins = unit['DropInPaths'].split()
        require(len(dropins) == len(set(dropins)) and set(dropins) <= {own, str(safety)},
                "Other/duplicate drop-ins require separate review")
        safety_evidence = None
        if str(safety) in dropins:
            before = safety.lstat()
            contents = safe_file(safety, 1024, self.p['uid'], private=True)
            after = safety.lstat()
            def identity(info):
                return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
                        info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            require(identity(before) == identity(after) and contents == b'[Service]\nSendSIGKILL=no\n',
                    'Stop-safety drop-in differs from approved canonical file')
            safety_evidence = {'identity': identity(after), 'sha256': digest(contents)}
        else:
            require(not safety.exists() and not safety.is_symlink(), 'Unloaded stop-safety file requires review')
        # Refuse any policy that can escalate a stuck stop; never alter it here.
        require(unit['SendSIGKILL'] == 'no' and unit['KillMode'] == 'control-group', "Stop escalation policy requires separate approval/configuration")
        require(unit['WorkingDirectory'] == str(self.p['app']), 'Manager WorkingDirectory differs from reviewed project')
        base = safe_file(unit['FragmentPath'], uid=self.p['uid'])
        git_prefix = ['--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                      '-c', 'core.hooksPath=/dev/null', '-C', str(self.p['project'])]
        source = self.runner.run('git', [*git_prefix, 'rev-parse', 'HEAD', 'HEAD^{tree}'])
        require(all(REV.fullmatch(x) for x in source.splitlines()) and len(source.splitlines()) == 2, "Source identity unavailable")
        require(not self.runner.run('git', [*git_prefix, 'status', '--porcelain', '--untracked-files=normal', '--ignore-submodules=all']), "App source dirty")
        profiles = {'system': str(self.p['system'].resolve(strict=True)), 'home': str(self.p['hm'].resolve(strict=True))}
        user_profile = self.p['home'] / '.local/state/nix/profiles/home-manager'
        if user_profile.exists() or user_profile.is_symlink():
            require(user_profile.is_symlink(), 'Unknown standalone HM profile ownership')
            profiles['standaloneHome'] = str(user_profile.resolve(strict=True))
        require(all(x.startswith(str(self.p['store']) + '/') for x in profiles.values()), "Profile identity unavailable")
        peers = {name: self._unit(name, False) for name in ('mpd.service', 'navidrome.service')}
        dataset = self._dataset()
        invocation = None if stopped else self._process(unit)
        require(self.manager_runtime is not None, 'Prior manager runtime identity unavailable')
        storage = {key: str(self.p[key]) for key in ('root', 'project', 'app', 'data', 'telemetry')}
        immutable = {'profiles': digest(canonical(profiles)), 'source': digest(canonical({'git': source, 'storage': storage})),
                     'unit': digest(canonical({'base': digest(base), 'stopSafety': safety_evidence})),
                     'stopPolicy': digest(canonical({k: unit[k] for k in ('KillMode', 'SendSIGKILL', 'TimeoutStopUSec')})),
                     'tools': digest(canonical({'tools': self.runner.tools, 'python': str(Path(sys.executable).resolve()),
                                               'manager': self.manager_runtime})),
                     'privateState': digest(canonical({'dataset': dataset, 'peers': peers}))}
        if stopped:
            require(unit['MainPID'] == '0' and unit['ActiveState'] == 'inactive' and unit['SubState'] == 'dead' and unit['Result'] == 'success',
                    "Normal stop/closure unavailable")
            require(self.manager_group is not None and self.manager_group_identity is not None
                    and self.manager_process is not None, "Prior cgroup/process identity unavailable")
            old_pid, old_start = self.manager_process
            old_fields = process_stat(self.p['proc'], old_pid, allow_missing=True)
            require(old_fields is None or old_fields[19] != old_start, 'Prior owned process has not exited')
            membership = cgroup_snapshot(self.p['cgroup'], self.manager_group, allow_missing=True)
            require(membership is None or (membership['identity'] == self.manager_group_identity
                    and not membership['pids'] and membership['populated'] is False),
                    'Owned cgroup identity/recursive closure unavailable')
            return {**immutable, 'invocation': digest(b'stopped'), 'processClosed': True, 'jobsIdle': False,
                    'config': None, 'scan': None, 'schedule': None, 'scheduleStorage': self.schedule_storage, 'zonesOwned': False}
        group = unit['ControlGroup']
        require(group.startswith('/') and group.endswith('/' + UNIT) and '..' not in group.split('/'),
                "Manager cgroup identity unavailable")
        self.manager_group = group
        config = self.api.get('config'); scan = self.api.get('scan'); schedule = self.api.get('operations/schedule')
        candidates = self.api.get('discovery'); runs = self.api.get('discovery/runs')
        require(config.get('scan') == scan, "Scan observations changed")
        require(type(candidates) is list and type(runs) is dict and type(runs.get('rows')) is list, "Job coverage missing")
        jobs_idle = all(type(x) is dict and x.get('status') in ('review', 'download_failed', 'staged', 'imported', 'dismissed') for x in candidates)
        jobs_idle = jobs_idle and not any(x.get('status') == 'running' for x in runs['rows'])
        desired = {'bravo': {'host': '127.0.0.1', 'port': 6600, 'musicPrefix': 'Music/'}}
        zones_owned = config.get('zones') in ({}, desired) and config.get('navidrome') is None
        registry_path = self.p['home'] / STATE / 'registry.json'
        registry = object_json(safe_file(registry_path, 65536, self.p['uid'], True)) if registry_path.exists() else {'current': None, 'pending': None}
        if registry.get('current') is None and registry.get('pending') is None:
            require(config.get('zones') == {} and own not in dropins, "Initial publication requires original empty playback config")
        require(type(config.get('indexedCount')) is int and config['indexedCount'] >= 0
                and 'tracks' in dataset['database']['tables']
                and config['indexedCount'] == dataset['database']['tables']['tracks']['count'], "Index/database identity differs")
        self.offline = dataset
        if self.baseline_config is None: self.baseline_config = config
        return {**immutable, 'invocation': invocation, 'processClosed': False, 'jobsIdle': jobs_idle,
                'config': config, 'scan': scan, 'schedule': schedule, 'scheduleStorage': self.schedule_storage, 'zonesOwned': zones_owned}

    def register_root(self, artifact, path):
        require(path.parent == self.p['home'] / STATE / 'roots' and path.name == artifact.hash, "Root destination not allowed")
        for source in (artifact.path, artifact.directory):
            self.runner.run('nix-store', ['--option', 'substitute', 'false', '--option', 'max-jobs', '0', '--option', 'builders', '',
                                         '--check-validity', str(source)])
        self.runner.run('nix-store', ['--option', 'substitute', 'false', '--option', 'max-jobs', '0', '--option', 'builders', '',
                                     '--add-root', str(path), '--indirect', '--realise', str(artifact.path)])

    def verify_root(self, artifact, path):
        require(path.parent == self.p['home'] / STATE / 'roots' and path.name == artifact.hash and path.is_symlink()
                and os.readlink(path) == str(artifact.path), "Missing/foreign root")
        refs = self.runner.run('nix-store', ['--query', '--references', str(artifact.path)]).splitlines()
        require(str(artifact.directory) in refs, "Manifest reference closure missing")
        roots = self.runner.run('nix-store', ['--query', '--roots', str(artifact.path)]).splitlines()
        proven = False
        for line in roots:
            left, sep, right = line.partition(' -> ')
            if sep and right == str(artifact.path) and left == str(path): proven = True
            if sep and Path(left).parent == Path('/nix/var/nix/gcroots/auto'):
                auto = Path(left)
                if auto.is_symlink() and os.readlink(auto) == str(path) and right == str(artifact.path): proven = True
        require(proven, "Indirect root registration not independently proven")

    def command(self, argv):
        require(argv in COMMANDS.values(), "Unsupported service action")
        self.runner.run('systemctl', list(argv[1:]), timeout=25)

    def wait_config(self):
        deadline = time.monotonic() + 90
        for _ in range(60):
            try: self.api.get('config'); return
            except Refusal:
                if time.monotonic() >= deadline: break
                self.sleep(0.5)
        raise Refusal('Read-only readiness deadline; no service retry')

    def prior_absent_config(self):
        require(self.baseline_config is not None and self.baseline_config.get('zones') == {}, "Prior absence not proven")
        return {}

    def bind_backup(self, reference):
        require(type(reference) is dict and set(reference) == {'id', 'hash'}
                and type(reference['id']) is str and ID.fullmatch(reference['id'])
                and type(reference['hash']) is str and HEX.fullmatch(reference['hash']), 'Exact backup pin required')
        self.backup_reference = dict(reference)

    def backup(self, before):
        # No directory search, silent selection or creation of a supposed backup.
        # Independently pin the receipt, then open/hash its actual sealed copies.
        require(self.offline is not None and getattr(self, 'backup_reference', None) is not None,
                'Fresh independently pinned backup required')
        reference = dict(self.backup_reference)
        self.verify_backup(reference, before)
        return reference

    def verify_backup(self, reference, before):
        require(reference == getattr(self, 'backup_reference', None), 'Backup pin differs from approved plan')
        require(type(reference) is dict and set(reference) == {'id', 'hash'} and ID.fullmatch(reference['id'])
                and HEX.fullmatch(reference['hash']) and self.offline is not None, "Backup reference invalid")
        directory = self.p['data'] / 'deployment-backups' / ('publisher-reviewed-' + reference['id'])
        with SealedBundle(directory, self.offline, self.p['uid']) as bundle:
            raw = bundle.read('receipt.json')
            require(digest(raw) == reference['hash'], "Backup receipt changed")
            receipt = object_json(raw, 2 * 1024 * 1024)
            require(set(receipt) == {'schema', 'dataset'} and type(receipt['schema']) is int
                    and receipt['schema'] == 1 and receipt['dataset'] == self.offline, "Stale/unknown backup receipt")
            if 'export.json' in bundle.snapshot:
                proof = object_json(bundle.read('export.json'))
                require(type(proof.get('schema')) is int and
                        proof == {'schema': 1, 'receipt': reference, 'datasetHash': digest(canonical(self.offline))},
                        'Deployment receipt export proof differs')
            require(bundle.database() == self.offline['database'], "Backup SQLite mismatch")
            require(digest(bundle.read('configuration.env')) == self.offline['environment'], "Private configuration backup mismatch")
            for name, meta in self.offline['state'].items():
                copied = bundle.read('app-files/' + name)
                require(len(copied) == meta['size'] and digest(copied) == meta['hash'], "App backup mismatch")
            for name, sha in self.offline['telemetry'].items():
                require(digest(bundle.read('telemetry-metadata/' + name)) == sha, "Telemetry backup mismatch")
            require(digest(canonical({'dataset': self.offline, 'peers': {name: self._unit(name, False) for name in ('mpd.service', 'navidrome.service')}}))
                    == before['privateState'], "Backup/resource binding differs")

    def drain(self): self.runner.drain()
