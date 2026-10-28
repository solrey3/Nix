"""Gated native entry point. Never called by artifact-only inspection.

Source implementation does not authorize use. An independently approved private
plan and credential FD are mandatory, with an explicit coordinated window, not
an app lease. There are no production path/runner/adapter overrides.
"""
import os
import select
import stat
import time
from pathlib import Path
from jukebox_playback import Artifact, Home, Publisher, Refusal, canonical, digest, object_json, require
from jukebox_window import WindowAdapter, validate_plan
from jukebox_native import NativeIO, OwnedRunner, LocalAPI, fixed_paths, safe_file


def code_identity():
    folder = Path(__file__).parent
    return digest(canonical({name: digest((folder/name).read_bytes()) for name in
                             ('jukebox_playback.py','jukebox_window.py','jukebox_native.py','jukebox_cli.py')}))


def token_from_fd(fd):
    require(type(fd) is int and fd >= 3, 'Explicit private credential FD required')
    copied = os.dup(fd)
    try:
        info = os.fstat(copied); mode = info.st_mode
        require((stat.S_ISREG(mode) or stat.S_ISFIFO(mode)) and info.st_uid == os.geteuid()
                and not mode & 0o077 and info.st_nlink <= 1, 'Credential FD must be a private bounded file/closed pipe')
        data = bytearray(); deadline = time.monotonic() + 5
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0 and bool(select.select([copied], [], [], remaining)[0]), 'Credential channel deadline')
            chunk = os.read(copied, 258 - len(data))
            if not chunk: break
            data.extend(chunk)
            require(len(data) <= 257, 'Credential channel exceeds bound')
        token = bytes(data).removesuffix(b'\n')
        require(24 <= len(token) <= 256 and all(33 <= c <= 126 for c in token), 'Invalid credential channel')
        return token
    finally: os.close(copied)


def run(args):
    require(args.mode in ('review','apply','review-rollback','rollback','discard-review'),
            'Live HM transfer/recovery controller not included')
    require(args.approve is True and args.activation_plan and args.expected_plan_sha256,
            'Independent activation plan/explicit approval required')
    require(not args.manifest and not args.expected_manifest_sha256 and not args.expected_source_revision,
            'Use only plan-bound artifact for native modes')
    raw = safe_file(Path(args.activation_plan), 32768, os.geteuid(), True)
    plan = object_json(raw, 32768)
    record = plan.get('artifact')
    artifact = None
    if record is not None:
        require(type(record) is dict and set(record)=={'path','hash','revision','directory'},'Invalid plan artifact')
        artifact = Artifact(record['path'],record['hash'],record['revision'])
        require(artifact.record()==record,'Artifact directory/source pin mismatch')
    identity = code_identity()
    validate_plan(plan,args.expected_plan_sha256,identity,artifact)
    # No host/user/proc/unit lookup or token read occurs without the above pins.
    paths = fixed_paths()
    token = token_from_fd(args.api_token_fd)
    runner = OwnedRunner(paths['home'],paths['uid'])
    fs = None
    try:
        io = NativeIO(paths,runner,LocalAPI(token))
        adapter = WindowAdapter(io,plan,args.expected_plan_sha256,identity,artifact)
        adapter._window()  # before state/lock creation
        fs = Home(paths['home'],paths['uid'])
        publisher = Publisher(fs,adapter,identity,Artifact)
        if args.mode in ('review','review-rollback'):
            require(args.review_id is None,'Review ID is generated, not caller supplied')
            return publisher.review(artifact,approve=True,rollback=args.mode=='review-rollback')
        require(args.review_id,'Reviewed one-shot ID required')
        if args.mode=='discard-review':
            publisher.discard(args.review_id,approve=True)
            return {'id':args.review_id,'state':'discarded','activation':False}
        return publisher.apply(args.review_id,approve=True,rollback=args.mode=='rollback')
    finally:
        try: runner.drain()
        finally:
            if fs: fs.close()
