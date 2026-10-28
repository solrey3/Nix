#!/usr/bin/env python3
"""Schema-1 playback artifact verifier and fail-closed publication state machine.

Artifact inspection is read-only. Native operations are in separate modules and
require an independently pinned private activation plan, credential FD, explicit
operator-coordinated window and approval. Source publication is NOT activation
permission. No app admission lease, background action or automatic recovery.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import sys
import time

SCHEMA = 1
STATE = ".local/state/jukebox-playback-config-v1"
TARGETS = {
    "90-playback.conf": ".config/systemd/user/jukebox-manager.service.d/90-playback.conf",
    "playback.env": ".config/jukebox/playback.env",
}
COMMANDS = {name: ("systemctl", "--user", name, "jukebox-manager.service")
            for name in ("stop", "start")}
COMMANDS["reload"] = ("systemctl", "--user", "daemon-reload")
TERMINAL = {"verified", "rolled-back", "transferred"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
REV = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"[0-9a-f]{32}\Z")


class Refusal(Exception):
    """Public-safe error; never include an input value, token or raw adapter error."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def object_json(data, limit=65536):
    require(len(data) <= limit, "Record exceeds bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        result = json.loads(data, object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(Refusal("Nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal("Invalid JSON") from None
    require(type(result) is dict, "Expected JSON object")
    return result


def regular_bytes(path, limit, uid=None, immutable=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_size <= limit and
                (s.st_nlink == 1 or (immutable and not s.st_mode & 0o222)),
                "Unsafe regular file")
        require(uid is None or s.st_uid == uid, "Unexpected file owner")
        require(not s.st_mode & 0o111, "Executable payload refused")
        data = os.read(fd, limit + 1)
        require(len(data) <= limit and len(data) == s.st_size, "File changed or exceeds bound")
        return data
    finally:
        os.close(fd)


class Artifact:
    """All paths/digests are independently pinned; manifest claims are not trust."""
    def __init__(self, manifest, expected_hash, expected_revision, store=Path("/nix/store")):
        self.path = Path(manifest)
        self.store = Path(store)
        require(HEX.fullmatch(expected_hash) is not None and REV.fullmatch(expected_revision) is not None,
                "Independent source/artifact pins required")
        self._store_path(self.path)
        raw = regular_bytes(self.path, 32768, immutable=True)
        require(digest(raw) == expected_hash, "Manifest pin mismatch")
        m = object_json(raw, 32768)
        require(set(m) == {"schema", "publisherSchema", "role", "account", "configHome", "sourceRevision",
                           "lockSha256", "filesDirectory", "files"}, "Unsupported manifest fields")
        require(type(m["schema"]) is int and m["schema"] == SCHEMA and type(m["publisherSchema"]) is int
                and m["publisherSchema"] == SCHEMA, "Unsupported schema")
        require((m["role"], m["account"], m["configHome"]) == ("bravo", "budchris", ".config"),
                "Unsupported account/role/config location")
        require(m["sourceRevision"] == expected_revision, "Source pin mismatch or dirty candidate")
        require(type(m["lockSha256"]) is str and HEX.fullmatch(m["lockSha256"]), "Invalid lock digest")
        require(type(m["filesDirectory"]) is str, "Invalid directory")
        self.directory = Path(m["filesDirectory"])
        self._store_path(self.directory)
        ds = self.directory.lstat()
        require(stat.S_ISDIR(ds.st_mode) and not ds.st_mode & 0o022, "Unsafe artifact directory")
        require(sorted(os.listdir(self.directory)) == sorted(TARGETS), "Unexpected artifact entries")
        require(type(m["files"]) is list and len(m["files"]) == 2, "Invalid payload list")
        seen = set()
        self.payloads = {}
        for f in m["files"]:
            require(type(f) is dict and set(f) == {"name", "target", "sha256", "size"}, "Invalid payload metadata")
            name = f["name"]
            require(type(name) is str and name in TARGETS and name not in seen, "Invalid payload name")
            seen.add(name)
            require(f["target"] == TARGETS[name] and type(f["size"]) is int and 0 < f["size"] <= 4096,
                    "Invalid destination or size")
            require(type(f["sha256"]) is str and HEX.fullmatch(f["sha256"]), "Invalid payload digest")
            data = regular_bytes(self.directory / name, 4096, immutable=True)
            require(len(data) == f["size"] and digest(data) == f["sha256"], "Payload integrity mismatch")
            self.payloads[name] = data
        self._public_values()
        self.hash = expected_hash
        self.revision = expected_revision
        self.manifest = m

    def _store_path(self, p):
        require(p.is_absolute() and p.parent == self.store and not p.name.endswith(".drv")
                and re.fullmatch(r"[0-9a-z]{32}-[A-Za-z0-9._+-]+", p.name), "Not a direct store artifact")
        # Store itself/ancestors may not be redirected by symlink.
        q = self.store
        while q != q.parent:
            s = q.lstat()
            require(stat.S_ISDIR(s.st_mode) and (not s.st_mode & 0o022 or
                    (s.st_uid == 0 and s.st_mode & stat.S_ISVTX)), "Unsafe store ancestry")
            q = q.parent

    def _public_values(self):
        data = self.payloads["playback.env"]
        try:
            require(b"\r" not in data and data.endswith(b"\n"), "Noncanonical environment")
            lines = data.decode().splitlines()
            require(len(lines) == 2, "Unsupported environment fields")
            values = {}
            for line in lines:
                tokens = shlex.split(line)
                require(len(tokens) == 1 and "=" in tokens[0], "Invalid environment syntax")
                key, value = tokens[0].split("=", 1)
                require(key not in values, "Duplicate environment field")
                values[key] = value
            require(set(values) == {"MPD_ZONES", "NAVIDROME_URL"} and values["NAVIDROME_URL"] == "",
                    "Unsupported environment values")
            zones = object_json(values["MPD_ZONES"].encode(), 4096)
            require(zones == {"bravo": {"host": "127.0.0.1", "port": 6600, "musicPrefix": "Music/"}}
                    and type(zones["bravo"]["port"]) is int, "Unsupported zone settings")
            require(self.payloads["90-playback.conf"].decode().splitlines() ==
                    ["[Service]", "EnvironmentFile=%h/.config/jukebox/playback.env"], "Unsupported drop-in")
        except (ValueError, UnicodeError):
            raise Refusal("Invalid public payload") from None

    def record(self):
        return {"path": str(self.path), "hash": self.hash, "revision": self.revision,
                "directory": str(self.directory)}


class Home:
    """No-follow, directory-relative home operations. Same UID is trusted, not an adversary boundary."""
    def __init__(self, path, uid=None, fault=lambda _: None):
        self.path = Path(path)
        self.uid = os.geteuid() if uid is None else uid
        self.fault = fault
        require(self.path.is_absolute(), "Home must be absolute")
        # Walk from / without following any symlink.
        self.fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.path.parts[1:]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = nxt
                s = os.fstat(nxt)
                # /tmp is accepted only by fixture callers; live CLI never constructs Home.
                require(s.st_uid in (0, self.uid) and (not s.st_mode & 0o022 or
                        (s.st_uid == 0 and s.st_mode & stat.S_ISVTX)), "Untrusted home ancestry")
            s = os.fstat(self.fd)
            require(s.st_uid == self.uid and not s.st_mode & 0o022, "Unsafe home owner/mode")
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        os.close(self.fd)

    @contextlib.contextmanager
    def parent(self, relative, create=False):
        require(type(relative) is str and not relative.startswith("/") and
                all(x not in ("", ".", "..") for x in relative.split("/")), "Invalid relative path")
        parts = relative.split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                        self.fault("mkdir")
                        os.fsync(fd)
                        self.fault("mkdir-sync")
                    except FileExistsError:
                        pass
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                s = os.fstat(nxt)
                require(s.st_uid == self.uid and not s.st_mode & 0o022, "Unsafe parent directory")
                os.close(fd)
                fd = nxt
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def snapshot(self, relative):
        try:
            with self.parent(relative) as (fd, name):
                try:
                    s = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    return None
                require(s.st_uid == self.uid and (stat.S_ISDIR(s.st_mode) or s.st_nlink == 1), "Foreign owner or hardlink")
                info = {"dev": s.st_dev, "ino": s.st_ino, "uid": s.st_uid, "mode": s.st_mode,
                        "ctime": s.st_ctime_ns, "mtime": s.st_mtime_ns}
                if stat.S_ISLNK(s.st_mode):
                    info["link"] = os.readlink(name, dir_fd=fd)
                elif stat.S_ISREG(s.st_mode):
                    info["hash"] = digest(self.read(relative))
                elif stat.S_ISDIR(s.st_mode):
                    require(not s.st_mode & 0o022, "Unsafe directory")
                else:
                    raise Refusal("Unsupported path type")
                return info
        except FileNotFoundError:
            return None

    def ancestry(self, relative):
        result = {}
        parts = relative.split("/")
        for i in range(1, len(parts)):
            p = "/".join(parts[:i])
            try:
                with self.parent(p) as (fd, name):
                    s = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    require(stat.S_ISDIR(s.st_mode) and s.st_uid == self.uid and not s.st_mode & 0o022,
                            "Unsafe parent ancestry")
                    result[p] = [s.st_dev, s.st_ino, s.st_uid, s.st_mode]
            except FileNotFoundError:
                result[p] = None
        return result

    def read(self, relative, limit=65536):
        with self.parent(relative) as (fd, name):
            f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                s = os.fstat(f)
                require(stat.S_ISREG(s.st_mode) and s.st_uid == self.uid and s.st_nlink == 1
                        and not s.st_mode & 0o077 and s.st_size <= limit, "Unsafe private record")
                data = os.read(f, limit + 1)
                require(len(data) <= limit and len(data) == s.st_size, "Record changed or too large")
                return data
            finally:
                os.close(f)

    def write(self, relative, value, new=False):
        data = canonical(value)
        require(len(data) <= 65536, "Record exceeds bound")
        with self.parent(relative) as (fd, name):
            if self.snapshot(relative) is not None:
                require(not new, "Record collision")
                self.read(relative)
            tmp = ".pending-" + secrets.token_hex(16)
            f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            try:
                with os.fdopen(f, "wb") as out:
                    out.write(data)
                    self.fault("record-write")
                    out.flush()
                    os.fsync(out.fileno())
                    self.fault("record-sync")
                if new:
                    # link, not replace: do not overwrite an entry appearing after check.
                    os.link(tmp, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                    os.unlink(tmp, dir_fd=fd)
                else:
                    os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
                self.fault("record-commit")
                os.fsync(fd)
                self.fault("record-directory-sync")
            except BaseException:
                # Retain pending evidence; never auto-clean uncertain records.
                raise

    def mkdir(self, relative):
        with self.parent(relative + "/sentinel", create=True):
            pass

    def names(self, relative):
        with self.parent(relative + "/sentinel") as (fd, _):
            require(not os.fstat(fd).st_mode & 0o077, "State directory must be private")
            names = []
            with os.scandir(fd) as entries:
                for entry in entries:
                    require(len(names) < 128, "Inventory bound exceeded")
                    names.append(entry.name)
            return sorted(names)

    def symlink(self, relative, target, replace=False):
        with self.parent(relative, create=True) as (fd, name):
            if replace:
                old = self.snapshot(relative)
                require(old is None or "link" in old, "Pointer collision")
                tmp = ".pending-" + secrets.token_hex(16)
                os.symlink(target, tmp, dir_fd=fd)
                self.fault("pointer-stage")
                require(self.snapshot(relative) == old, "Pointer changed")
                if old is None:
                    os.link(tmp, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                    self.fault("pointer-first-link")
                    os.unlink(tmp, dir_fd=fd)
                else:
                    os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
            else:
                os.symlink(target, name, dir_fd=fd)
            self.fault("symlink-commit")
            os.fsync(fd)
            self.fault("symlink-sync")

    def retire(self, relative, destination):
        with self.parent(relative) as (fd, name), self.parent(destination) as (other, dest):
            require(self.snapshot(destination) is None, "Retirement collision")
            os.link(name, dest, src_dir_fd=fd, dst_dir_fd=other, follow_symlinks=False)
            os.fsync(other)
            self.fault("retire-link")
            os.unlink(name, dir_fd=fd)
            os.fsync(fd)
            self.fault("retire-unlink")

    def unlink_owned(self, relative, expected):
        require(self.snapshot(relative) == expected and expected is not None and "link" in expected,
                "Owned link changed")
        with self.parent(relative) as (fd, name):
            os.unlink(name, dir_fd=fd)
            self.fault("unlink")
            os.fsync(fd)
            self.fault("unlink-sync")


class Publisher:
    """Transactional core. Adapter MUST prove observations/backup/root/closure.

    Required adapter methods: snapshot(), clock()->(boot, monotonic, UTC),
    root(artifact,path), verify_root(artifact,path), backup(snapshot)->receipt,
    verify_backup(receipt,snapshot), command(allowlisted_argv), stopped(snapshot),
    ready(artifact_or_None,snapshot), drain(). They may refuse, never guess.
    The window adapter requires explicit operator coordination, not an app lease.
    Fixtures exercise contracts without running real service/API/root operations.
    """
    def __init__(self, home, adapter, publisher_hash, artifact_loader,
                 roots_limit=32, records_limit=128):
        require(HEX.fullmatch(publisher_hash), "Publisher identity required")
        self.fs, self.adapter, self.publisher_hash, self.load = home, adapter, publisher_hash, artifact_loader
        self.roots_limit, self.records_limit = roots_limit, records_limit

    def _path(self, leaf):
        return STATE + "/" + leaf

    @contextlib.contextmanager
    def lock(self, create=False, shared=False):
        if create:
            self.fs.mkdir(STATE)
        with self.fs.parent(self._path("lock")) as (fd, name):
            directory = os.fstat(fd)
            require(directory.st_uid == self.fs.uid and not directory.st_mode & 0o077,
                    "State root must be private")
            flags = os.O_RDONLY if shared else os.O_RDWR
            if create:
                flags |= os.O_CREAT
            lock = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
            acquired = False
            try:
                s = os.fstat(lock)
                require(stat.S_ISREG(s.st_mode) and s.st_uid == self.fs.uid and s.st_nlink == 1
                        and not s.st_mode & 0o077, "Unsafe lock")
                try:
                    fcntl.flock(lock, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    raise Refusal("Publisher busy; no queue") from None
                yield
            finally:
                try:
                    # Also covers observation/validation helpers failing before a
                    # review/transaction intent exists. Drain never means kill.
                    if acquired:
                        self.adapter.drain()
                finally:
                    os.close(lock)

    def _read(self, leaf):
        return object_json(self.fs.read(self._path(leaf)))

    def _write(self, leaf, value, new=False):
        self.fs.write(self._path(leaf), value, new)

    def _registry(self, initialize=False):
        if initialize and self.fs.snapshot(self._path("registry.json")) is None:
            require(self.fs.names(STATE) == ["lock"], "Unrecognized existing state")
            for sub in ("reviews", "transactions", "roots", "retired"):
                self.fs.mkdir(self._path(sub))
            self._write("registry.json", {"schema": 1, "owner": "dedicated-v1", "current": None,
                                          "lastTransaction": None, "pending": None}, True)
        allowed = {"lock", "registry.json", "reviews", "transactions", "roots", "retired", "active"}
        require(set(self.fs.names(STATE)) <= allowed, "Unknown state evidence")
        r = self._read("registry.json")
        require(set(r) == {"schema", "owner", "current", "lastTransaction", "pending"}
                and type(r["schema"]) is int and r["schema"] == 1
                and r["owner"] == "dedicated-v1", "Unsupported/transferred owner")
        require(r["pending"] is None, "Incomplete registry commit blocks work")
        require(r["lastTransaction"] is None or
                (type(r["lastTransaction"]) is str and ID.fullmatch(r["lastTransaction"])), "Invalid journal pointer")
        known = {}
        for sub in ("reviews", "transactions"):
            names = self.fs.names(self._path(sub))
            require(len(names) <= self.records_limit, "Evidence quota reached")
            for name in names:
                require(re.fullmatch(r"[a-f0-9]{32}\.json", name), "Unknown evidence entry")
                row = self._read(sub + "/" + name)
                require(row.get("id") == name[:-5], "Evidence identity mismatch")
                if sub == "transactions":
                    require(row.get("phase") in TERMINAL, "Incomplete transaction blocks work")
                else:
                    require(row.get("status") in {"pending", "consumed", "discarded", "blocked"}, "Unknown review state")
                    require(row.get("status") != "blocked", "Uncertain preparation blocks work")
                artifacts = [row.get("artifact")] if sub == "reviews" else [row.get("before"), row.get("after")]
                for item in artifacts:
                    if item is not None:
                        a = self._artifact(item)
                        require(a.hash not in known or known[a.hash].record() == item, "Conflicting retained artifact")
                        known[a.hash] = a
        roots = self.fs.names(self._path("roots"))
        require(len(roots) <= self.roots_limit and all(HEX.fullmatch(x) for x in roots), "Root quota/unknown entry")
        require(set(roots) == set(known), "Missing or foreign retained artifact root")
        for name in roots:
            self.adapter.verify_root(known[name], self.fs.path / self._path("roots/" + name))
            s = self.fs.snapshot(self._path("roots/" + name))
            require(s is not None and "link" in s, "Unsafe retained root")
        for name in self.fs.names(self._path("retired")):
            require(ID.fullmatch(name), "Unknown retired entry")
            s = self.fs.snapshot(self._path("retired/" + name))
            require(s is not None and "link" in s, "Unsafe retired pointer")
            tx = self._read("transactions/" + name + ".json")
            require(tx.get("phase") == "rolled-back" and tx.get("after") is None
                    and type(tx.get("before")) is dict and s["link"] == tx["before"].get("directory"),
                    "Retired pointer lacks rollback proof")
        return r

    def _artifact(self, row):
        require(type(row) is dict and set(row) == {"path", "hash", "revision", "directory"}, "Invalid artifact record")
        a = self.load(row["path"], row["hash"], row["revision"])
        require(a.record() == row, "Artifact identity changed")
        return a

    def _owned(self, registry):
        current = registry["current"]
        targets = {name: self.fs.snapshot(path) for name, path in TARGETS.items()}
        active = self.fs.snapshot(self._path("active"))
        if current is None:
            require(all(x is None for x in targets.values()) and active is None, "Foreign/partial targets")
        else:
            a = self._artifact(current)
            self.adapter.verify_root(a, self.fs.path / self._path("roots/" + a.hash))
            require(active is not None and active.get("link") == str(a.directory), "Active pointer mismatch")
            require(registry["lastTransaction"] is not None, "Missing ownership transaction")
            t = self._read("transactions/" + registry["lastTransaction"] + ".json")
            require(t.get("phase") in {"verified", "rolled-back"} and t.get("after") == current,
                    "Ownership journal mismatch")
            require(type(t.get("ownership")) is dict and t["ownership"].get("targets") == targets
                    and t["ownership"].get("active") == active, "Owned link identities changed")
            for name, s in targets.items():
                expected = str(self.fs.path / self._path("active/" + name))
                require(s is not None and s.get("link") == expected, "Foreign/equal-byte/partial target")
        return {"targets": targets, "active": active,
                "parents": {name: self.fs.ancestry(path) for name, path in TARGETS.items()}}

    def _binding(self, r, exclude=None):
        observation = self.adapter.snapshot()
        fields = {"profiles", "flags", "source", "invocation", "unit", "resources", "tools", "stopPolicy"}
        require(type(observation) is dict and set(observation) == fields | {"eligible"}
                and observation["eligible"] is True, "Preflight unavailable/busy/uncertain")
        require(all(type(observation[k]) is str and HEX.fullmatch(observation[k]) for k in fields),
                "Only reviewed non-secret preflight digests may be retained")
        evidence = {}
        for sub in ("reviews", "transactions"):
            evidence[sub] = {name: digest(self.fs.read(self._path(sub + "/" + name)))
                             for name in self.fs.names(self._path(sub)) if name != str(exclude) + ".json"}
        evidence["roots"] = {name: self.fs.snapshot(self._path("roots/" + name))
                             for name in self.fs.names(self._path("roots"))}
        return {"registry": r, "owned": self._owned(r), "platform": observation,
                "publisher": self.publisher_hash, "evidence": evidence,
                "adapterPlan": self.adapter.review_identity() if hasattr(self.adapter, 'review_identity') else None}

    def _clock(self):
        boot, mono, utc = self.adapter.clock()
        require(type(boot) is str and 0 < len(boot) <= 128 and
                all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (mono, utc)),
                "Invalid clock evidence")
        return boot, mono, utc

    def inspect(self):
        if self.fs.snapshot(STATE) is None:
            require(all(self.fs.snapshot(p) is None for p in TARGETS.values()), "Foreign targets")
            return {"state": "absent", "writes": False}
        with self.lock(shared=True):
            r = self._registry()
            self._owned(r)
            return {"state": "owned" if r["current"] else "empty", "current": r["current"], "writes": False}

    def review(self, artifact, approve=False, rollback=False):
        require(approve is True, "Explicit preparation approval required")
        with self.lock(create=True):
            r = self._registry(initialize=True)
            reviews = self.fs.names(self._path("reviews"))
            require(len(reviews) < self.records_limit and
                    len(self.fs.names(self._path("transactions"))) < self.records_limit, "Evidence quota reached")
            require(not any(self._read("reviews/" + x)["status"] == "pending" for x in reviews),
                    "Pending review requires explicit discard")
            if rollback:
                require(r["current"] is not None and r["lastTransaction"] is not None, "Nothing to roll back")
                last = self._read("transactions/" + r["lastTransaction"] + ".json")
                previous = last.get("rollbackTarget", last["before"])
                require(artifact is None if previous is None else artifact is not None and artifact.record() == previous,
                        "Rollback must select exact retained predecessor")
            else:
                require(artifact is not None, "Artifact required")
            binding = self._binding(r)
            boot, mono, utc = self._clock()
            row = {"id": secrets.token_hex(16), "status": "blocked", "rollback": rollback,
                   "artifact": artifact.record() if artifact else None, "binding": binding,
                   "boot": boot, "mono": mono, "utc": utc}
            leaf = "reviews/" + row["id"] + ".json"
            self._write(leaf, row, True)  # durable uncertainty guard before root helper
            try:
                if artifact:
                    root = self.fs.path / self._path("roots/" + artifact.hash)
                    if self.fs.snapshot(self._path("roots/" + artifact.hash)) is None:
                        require(len(self.fs.names(self._path("roots"))) < self.roots_limit, "Root quota reached")
                        self.adapter.root(artifact, root)
                    self.adapter.verify_root(artifact, root)
                final_binding = self._binding(r, exclude=row["id"])
                require(all(final_binding[k] == binding[k] for k in ("registry", "owned", "platform", "publisher", "adapterPlan")),
                        "State changed during preparation")
                row["binding"] = final_binding
                row["status"] = "pending"
                self._write(leaf, row)
                return {"id": row["id"], "expiresSeconds": 600, "rollback": rollback}
            finally:
                # Drain holds lock until actual exit, even after timeout/refusal.
                # Crash leaves blocked evidence; no subsequent mutation can resume.
                self.adapter.drain()

    def discard(self, review_id, approve=False):
        require(approve is True and ID.fullmatch(review_id), "Explicit valid discard required")
        with self.lock():
            self._registry()
            row = self._read("reviews/" + review_id + ".json")
            require(row["status"] == "pending", "Review not discardable")
            row["status"] = "discarded"
            self._write("reviews/" + review_id + ".json", row)

    def apply(self, review_id, approve=False, rollback=False):
        require(approve is True and ID.fullmatch(review_id), "Explicit valid apply approval required")
        with self.lock():
            r = self._registry()
            row = self._read("reviews/" + review_id + ".json")
            require(row["status"] == "pending" and row["rollback"] is rollback, "Consumed or wrong review mode")
            boot, mono, utc = self._clock()
            require(boot == row["boot"] and 0 <= mono - row["mono"] < 600 and
                    0 <= utc - row["utc"] < 600, "Expired/clock/reboot review")
            require(self._binding(r, exclude=review_id) == row["binding"], "Stale source/settings/ownership/preflight")
            after = row["artifact"]
            artifact = self._artifact(after) if after else None
            if hasattr(self.adapter, 'admit_target'):
                self.adapter.admit_target(artifact)
            if artifact:
                self.adapter.verify_root(artifact, self.fs.path / self._path("roots/" + artifact.hash))
            prior = object_json(canonical(r))
            same_directory = bool(r["current"] and after and r["current"]["directory"] == after["directory"])
            rollback_target = r['current']
            if r['current'] == after and r['lastTransaction'] is not None:
                last = self._read('transactions/' + r['lastTransaction'] + '.json')
                rollback_target = last.get('rollbackTarget', last['before'])
            tx = {"id": review_id, "phase": "consumed", "before": r["current"], "after": after,
                  "rollbackTarget": rollback_target, "rollback": rollback, "backup": None, "noOp": same_directory}
            self._write("transactions/" + review_id + ".json", tx, True)
            row["status"] = "consumed"
            self._write("reviews/" + review_id + ".json", row)
            r["pending"] = review_id
            self._write("registry.json", r)
            def phase(value):
                tx["phase"] = value
                self._write("transactions/" + review_id + ".json", tx)
            try:
                phase("backup-requested")
                receipt = self.adapter.backup(row["binding"]["platform"])
                require(type(receipt) is dict and set(receipt) == {"id", "hash"}
                        and type(receipt["id"]) is str and ID.fullmatch(receipt["id"])
                        and type(receipt["hash"]) is str and HEX.fullmatch(receipt["hash"]),
                        "Invalid bounded backup reference")
                self.adapter.verify_backup(receipt, row["binding"]["platform"])
                require(self._read("registry.json") == r and self._binding(prior, exclude=review_id) == row["binding"],
                        "State changed while preparing backup")
                tx["backup"] = receipt
                phase("backup-verified")
                if not tx["noOp"]:
                    phase("stop-requested")
                    self.adapter.command(COMMANDS["stop"])
                    self.adapter.stopped(row["binding"]["platform"])
                    require(self._read("registry.json") == r and self._owned(prior) == row["binding"]["owned"],
                            "Stopped-state paths changed")
                    phase("service-stopped")
                    if after is not None:
                        if r["current"] is None:
                            phase("links-intent")
                            for name, target in TARGETS.items():
                                self.fs.symlink(target, str(self.fs.path / self._path("active/" + name)))
                        phase("links-staged")
                        self.fs.symlink(self._path("active"), str(artifact.directory), replace=True)
                    else:
                        require(rollback and r["current"] is not None, "Absence only valid for initial rollback")
                        phase("remove-links-intent")
                        for name, target in TARGETS.items():
                            self.fs.unlink_owned(target, row["binding"]["owned"]["targets"][name])
                        self.fs.retire(self._path("active"), self._path("retired/" + review_id))
                    phase("pointer-committed")
                    # Conservative schema-1 policy: explicitly approve a reload for every change.
                    phase("reload-requested")
                    self.adapter.command(COMMANDS["reload"])
                    phase("start-requested")
                    self.adapter.command(COMMANDS["start"])
                published = {"targets": {name: self.fs.snapshot(path) for name, path in TARGETS.items()},
                             "active": self.fs.snapshot(self._path("active"))}
                if artifact:
                    require(self._artifact(after).record() == after, "Artifact changed after publication")
                    self.adapter.verify_root(artifact, self.fs.path / self._path("roots/" + artifact.hash))
                self.adapter.ready(artifact, row["binding"]["platform"])
                self.adapter.verify_backup(receipt, row["binding"]["platform"])
                # Verify actual links before writing ownership; no content-only adoption.
                if after:
                    require(self.fs.snapshot(self._path("active"))["link"] == str(artifact.directory), "Final pointer mismatch")
                    for name, target in TARGETS.items():
                        require(self.fs.snapshot(target)["link"] == str(self.fs.path / self._path("active/" + name)),
                                "Final public link mismatch")
                else:
                    require(all(self.fs.snapshot(p) is None for p in TARGETS.values()) and
                            self.fs.snapshot(self._path("active")) is None, "Rollback absence mismatch")
                require(published == {"targets": {name: self.fs.snapshot(path) for name, path in TARGETS.items()},
                                      "active": self.fs.snapshot(self._path("active"))},
                        "Published link identities changed during readiness")
                tx["ownership"] = published
                phase("rolled-back" if rollback else "verified")
                r["current"], r["lastTransaction"], r["pending"] = after, review_id, None
                self._write("registry.json", r)
                return {"id": review_id, "phase": tx["phase"], "noOp": tx["noOp"]}
            except BaseException:
                # Do not mask a crash with attempted repairs. Even if recording blocked
                # fails, prior nonterminal intent still blocks all future mutation.
                try:
                    phase("blocked")
                except BaseException:
                    pass
                raise
            finally:
                self.adapter.drain()

    def record_transfer(self, approve=False):
        """No unlink/activation here: adapter must prove an independently approved HM handoff."""
        require(approve is True, "Explicit handoff approval required")
        with self.lock():
            r = self._registry()
            require(r["current"] is not None, "No dedicated owner")
            require(not any(self._read("reviews/" + x)["status"] == "pending"
                            for x in self.fs.names(self._path("reviews"))), "Pending review blocks transfer")
            a = self._artifact(r["current"])
            proof = self.adapter.transfer_proof(r["current"])
            require(type(proof) is dict and set(proof) == {"generation", "artifactHash", "approved"}
                    and proof["approved"] is True and proof["artifactHash"] == a.hash,
                    "Independent handoff identity/approval required")
            generation = Path(proof["generation"])
            a._store_path(generation)
            require(generation.name.endswith("-home-manager-files") and generation.is_dir(),
                    "Invalid Home Manager generation")
            for name, target in TARGETS.items():
                link = self.fs.snapshot(target)
                require(link is not None and link.get("link") == str(generation / target),
                        "Actual Home Manager links required; equal bytes are insufficient")
                resolved = (generation / target).resolve(strict=True)
                require(resolved.is_relative_to(a.store), "Handoff source escapes store")
                require(regular_bytes(resolved, 4096, immutable=True) == a.payloads[name], "Handoff payload differs")
            require(len(self.fs.names(self._path("transactions"))) < self.records_limit,
                    "Evidence quota reached")
            transfer_id = secrets.token_hex(16)
            tx = {"id": transfer_id, "phase": "transfer-recorded", "before": r["current"],
                  "after": r["current"], "generation": str(generation)}
            self._write("transactions/" + transfer_id + ".json", tx, True)
            r["pending"] = transfer_id
            self._write("registry.json", r)
            tx["phase"] = "transferred"
            self._write("transactions/" + transfer_id + ".json", tx)
            r["owner"], r["pending"], r["lastTransaction"] = "transferred-to-hm", None, transfer_id
            self._write("registry.json", r)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("Invalid arguments")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("mode", choices=["inspect", "review", "apply", "review-rollback", "rollback", "discard-review", "transfer"])
    parser.add_argument("--manifest")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--activation-plan")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--api-token-fd", type=int)
    parser.add_argument("--review-id")
    parser.add_argument("--approve", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.mode != 'inspect':
            require(args.approve and args.activation_plan and args.expected_plan_sha256,
                    'No native operation without independent plan and explicit approval')
            from jukebox_cli import run
            print(json.dumps(run(args),sort_keys=True))
            return 0
        require(not args.approve and not args.activation_plan and args.api_token_fd is None
                and args.review_id is None and not args.expected_plan_sha256, 'Artifact inspect is read-only')
        require(args.manifest and args.expected_manifest_sha256 and args.expected_source_revision,
                "Independent manifest/source pins required")
        a = Artifact(args.manifest, args.expected_manifest_sha256, args.expected_source_revision)
        print(json.dumps({"schema": 1, "artifact": a.record(), "writes": False,
                          "activationAuthorized": False}, sort_keys=True))
        return 0
    except Exception:
        # Never echo raw input, private adapter data, filesystem errors or traceback.
        print("Playback publisher refused; inspect trusted source/evidence. No automatic recovery.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
