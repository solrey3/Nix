"""Explicit operator-window evidence adapter; NOT an atomic admission lease.

No action happens on import. Native operations require an independently pinned,
private activation plan and caller-supplied API credential FD. Tests inject only
fixture IO. The publisher CLI stays gated until exact activation-plan review.
"""
from __future__ import annotations
import math
import re
from datetime import datetime
from pathlib import Path
import sqlite3
import stat

from jukebox_playback import COMMANDS, HEX, ID, Refusal, canonical, digest, object_json, require

WINDOW = "operator-coordinated-no-concurrent-clients-or-external-edits-v1"
POLICY = "manual-block-no-retry-resume-rollback-or-containment-stop-v1"
ENDPOINTS = {"config", "scan", "operations/schedule", "discovery", "discovery/runs"}
FIELDS = {"profiles", "flags", "source", "invocation", "unit", "resources", "tools", "stopPolicy"}


def validate_plan(plan, expected_digest, publisher_digest, artifact):
    """Plan identity/approval comes from the operator, never a manifest claim."""
    require(type(plan) is dict and set(plan) == {"schema", "id", "publisher", "artifact", "window", "failurePolicy",
            "allowPreparation", "allowManagerStopStart", "allowUserDaemonReload", "bootId", "createdUtc", "createdMonotonic", "expiresUtc", "expiresMonotonic", "backup", "expected"},
            "Unsupported activation plan")
    require(HEX.fullmatch(expected_digest) and digest(canonical(plan)) == expected_digest, "Activation plan pin mismatch")
    require(type(plan["schema"]) is int and plan["schema"] == 1 and type(plan["id"]) is str and ID.fullmatch(plan["id"]),
            "Invalid activation plan identity")
    require(plan["publisher"] == publisher_digest and plan["artifact"] == (artifact.record() if artifact else None),
            "Activation source/publisher/artifact mismatch")
    require(plan["window"] == WINDOW and plan["failurePolicy"] == POLICY, "Explicit window/failure policy required")
    require(all(plan[k] is True for k in ("allowPreparation", "allowManagerStopStart", "allowUserDaemonReload")),
            "Missing activation permission scope")
    require(type(plan['bootId']) is str and 0 < len(plan['bootId']) <= 128, 'Invalid plan boot identity')
    require(all(type(plan[k]) in (int, float) and math.isfinite(plan[k]) and plan[k] >= 0
                for k in ('createdUtc', 'createdMonotonic', 'expiresUtc', 'expiresMonotonic')), 'Invalid plan expiry')
    require(0 < plan['expiresUtc'] - plan['createdUtc'] <= 600 and
            0 < plan['expiresMonotonic'] - plan['createdMonotonic'] <= 600
            and abs((plan['expiresUtc'] - plan['createdUtc']) -
                    (plan['expiresMonotonic'] - plan['createdMonotonic'])) <= 0.001, 'Unbounded/inconsistent operator window')
    require(type(plan['backup']) is dict and set(plan['backup']) == {'id', 'hash'}
            and type(plan['backup']['id']) is str and ID.fullmatch(plan['backup']['id'])
            and type(plan['backup']['hash']) is str and HEX.fullmatch(plan['backup']['hash']), 'Exact backup pin required')
    require(type(plan["expected"]) is dict and set(plan["expected"]) == FIELDS and
            all(type(x) is str and HEX.fullmatch(x) for x in plan["expected"].values()), "Missing independently reviewed observations")
    return plan


SCHEDULE_SQL = "CREATE TABLE collector_schedule_v1(station TEXT PRIMARY KEY CHECK(station='KEXP'),json TEXT NOT NULL)"
SCHEDULE_RIGHTS = 'I confirm permission for recurring private KEXP metadata lookup under the current source terms.'
SCHEDULE_FIELDS = {'station', 'enabled', 'intervalHours', 'startHour', 'endHour', 'version', 'revision',
                   'nextAt', 'activeSlot', 'watermark', 'failures', 'rightsConfirmedAt', 'rightsAttestation', 'last'}
SCHEDULE_OUTCOMES = {'never', 'configured', 'complete', 'partial', 'failed', 'skipped-busy', 'skipped-cooldown',
                     'skipped-late', 'disabled-failures', 'disabled-access', 'disabled-interrupted',
                     'disabled-feature', 'disabled-uncertain'}
UUID4 = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')


def epoch(value):
    return type(value) is int and 0 <= value <= 8640000000000000


def disabled_schedule_state(state):
    """Strict current app DTO, not an inferred/partial disabled state."""
    require(type(state) is dict and set(state) == SCHEDULE_FIELDS, 'Unknown scheduler state shape')
    require(state['station'] == 'KEXP' and type(state['version']) is int and state['version'] == 1
            and state['enabled'] is False and state['nextAt'] is None and state['activeSlot'] is None,
            'Scheduler must be independently disabled and slot-free')
    require(type(state['intervalHours']) is int and state['intervalHours'] in (1, 2, 3, 4, 6, 8, 12, 24)
            and type(state['startHour']) is int and type(state['endHour']) is int
            and 0 <= state['startHour'] < state['endHour'] <= 24, 'Invalid scheduler definition')
    require(type(state['revision']) is str and UUID4.fullmatch(state['revision'])
            and (state['watermark'] is None or epoch(state['watermark']))
            and type(state['failures']) is int and 0 <= state['failures'] <= 3, 'Invalid scheduler identity/counters')
    last = state['last']
    require(type(last) is dict and set(last) == {'kind', 'at', 'slotAt', 'runId'}
            and type(last['kind']) is str and last['kind'] in SCHEDULE_OUTCOMES and epoch(last['at'])
            and (last['slotAt'] is None or epoch(last['slotAt']))
            and (last['runId'] is None or type(last['runId']) is str and UUID4.fullmatch(last['runId'])),
            'Invalid scheduler outcome')
    rights = state['rightsConfirmedAt']
    if rights is None:
        require(state['rightsAttestation'] is None, 'Ambiguous scheduler rights state')
    else:
        require(type(rights) is str and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z', rights)
                and state['rightsAttestation'] == SCHEDULE_RIGHTS, 'Invalid scheduler rights state')
        try: datetime.strptime(rights, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError: raise Refusal('Invalid scheduler rights date') from None
    return state


def scheduler_storage(db, root):
    """Read-only evidence from the SAME transaction as logical table hashes.

    No API claim, cached default or table count alone can establish absence.
    Exact current schema + bounded rows + strict JSON/root/state must be proven.
    """
    schema = db.execute("SELECT sql FROM sqlite_schema WHERE type='table' AND name='collector_schedule_v1'").fetchall()
    require(len(schema) == 1 and schema[0][0] == SCHEDULE_SQL, 'Scheduler schema unavailable/unsupported')
    columns = [(row['name'], row['type'], row['notnull'], row['dflt_value'], row['pk'])
               for row in db.execute('PRAGMA table_info(collector_schedule_v1)')]
    require(columns == [('station', 'TEXT', 0, None, 1), ('json', 'TEXT', 1, None, 0)]
            and not db.execute("SELECT 1 FROM sqlite_schema WHERE type='trigger' AND tbl_name='collector_schedule_v1'").fetchone(),
            'Scheduler schema/ownership ambiguous')
    rows = db.execute('SELECT station,substr(json,1,16385) value,length(json) n FROM collector_schedule_v1 LIMIT 2').fetchall()
    require(len(rows) <= 1, 'Unknown scheduler rows')
    if not rows: return {'kind': 'empty'}
    row = rows[0]
    require(row['station'] == 'KEXP' and type(row['value']) is str and type(row['n']) is int
            and 0 < row['n'] <= 16384 and len(row['value'].encode()) <= 16384, 'Invalid scheduler storage')
    record = object_json(row['value'].encode(), 16384)
    require(set(record) == SCHEDULE_FIELDS | {'root'} and record['root'] == str(root), 'Scheduler storage root/shape differs')
    state = {key: value for key, value in record.items() if key != 'root'}
    disabled_schedule_state(state)
    return {'kind': 'stored', 'state': state}


def schedule_observation(status, storage):
    """Project volatility only after independent SQLite evidence, never an app lease."""
    require(type(status) is dict and set(status) == {'capturedAt', 'available', 'capability', 'active', 'blocked', 'state'}
            and epoch(status['capturedAt']) and status['available'] is True and status['capability'] is False
            and status['active'] is False and status['blocked'] is False, 'Scheduler unavailable/busy/ambiguous')
    state = disabled_schedule_state(status['state'])
    require(type(storage) is dict and storage.get('kind') in ('empty', 'stored'), 'Independent scheduler storage evidence required')
    projected = {**state, 'last': dict(state['last'])}
    if storage['kind'] == 'empty':
        require(set(storage) == {'kind'}, 'Unknown scheduler absence evidence')
        projected.pop('revision'); projected['last'].pop('at')
        require(projected == {'station': 'KEXP', 'enabled': False, 'intervalHours': 1, 'startHour': 0, 'endHour': 24,
                             'version': 1, 'nextAt': None, 'activeSlot': None, 'watermark': None, 'failures': 0,
                             'rightsConfirmedAt': None, 'rightsAttestation': None,
                             'last': {'kind': 'never', 'slotAt': None, 'runId': None}},
                'Empty storage does not match exact unconfigured API defaults')
    else:
        require(set(storage) == {'kind', 'state'}, 'Unknown configured scheduler evidence')
        disabled_schedule_state(storage['state'])
        require(state == storage['state'], 'API scheduler state differs from stored row')
    return {'available': True, 'capability': False, 'active': False, 'blocked': False,
            'storage': storage['kind'], 'state': projected}


def database_digest(path, *, scheduler_root=None):
    """Logical rows/schema + integrity, read-only, no migrations/checkpoints."""
    path = Path(path)
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "Unsafe database")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        logical = database_contents(db)
        return (logical, scheduler_storage(db, scheduler_root)) if scheduler_root is not None else logical
    finally:
        db.close()


def database_contents(db, check=lambda: None):
    """Shared logical encoding only; callers own live versus offline transport."""
    db.row_factory = sqlite3.Row
    db.execute("BEGIN")
    require([row[0] for row in db.execute("PRAGMA integrity_check")] == ["ok"], "Database integrity unavailable")
    schema = [dict(row) for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    tables = {}
    for item in schema:
        check()
        if item["type"] != "table": continue
        name = item["name"]
        quoted = '"' + name.replace('"', '""') + '"'
        columns = list(db.execute("PRAGMA table_info(" + quoted + ")"))
        primary = ','.join('"' + r['name'].replace('"', '""') + '"' for r in sorted(columns, key=lambda r: r['pk']) if r['pk'])
        try: cursor = db.execute("SELECT * FROM " + quoted + " ORDER BY rowid")
        except sqlite3.OperationalError:
            require(bool(primary), "Unordered table unsupported")
            cursor = db.execute("SELECT * FROM " + quoted + " ORDER BY " + primary)
        import hashlib
        sha = hashlib.sha256(); count = 0
        for row in cursor:
            check()
            # Canonical JSON deliberately refuses BLOB/nonfinite/unsupported values.
            sha.update(canonical(dict(row))); sha.update(b"\n"); count += 1
        tables[name] = {"count": count, "hash": sha.hexdigest()}
    check()
    return {"schema": digest(canonical(schema)), "tables": tables}


class WindowAdapter:
    """Evidence under a coordinated window, never a lease/global-idle claim.

    IO is trusted reviewed code, not a plugin path or callback in public data.
    It supplies actual bounded observations, independently pinned sealed backup verification,
    fixed root operations, normal manager-only commands and helper draining.
    All observation equality is checked here; unavailable evidence refuses.
    """
    def __init__(self, io, plan, plan_digest, publisher_digest, artifact):
        self.io = io
        self.plan = validate_plan(plan, plan_digest, publisher_digest, artifact)
        self.artifact = artifact
        self.plan_digest = plan_digest
        if hasattr(io, 'bind_backup'): io.bind_backup(plan['backup'])
        self.before = None

    def review_identity(self):
        return self.plan_digest

    def _window(self):
        boot, mono, utc = self.clock()
        require(boot == self.plan['bootId'] and self.plan['createdUtc'] <= utc < self.plan['expiresUtc']
                and self.plan['createdMonotonic'] <= mono < self.plan['expiresMonotonic']
                and abs((utc - self.plan['createdUtc']) - (mono - self.plan['createdMonotonic'])) <= 2,
                "Operator window expired/clock changed; no automatic extension")

    def clock(self):
        return self.io.clock()

    def _observe(self, stopped=False):
        observation = self.io.observe(stopped=stopped)
        require(type(observation) is dict and set(observation) == {"profiles", "tools", "unit", "stopPolicy", "source",
                "invocation", "processClosed", "jobsIdle", "privateState", "config", "scan", "schedule", "scheduleStorage", "zonesOwned"},
                "Observation coverage unavailable")
        for key in ("profiles", "tools", "unit", "stopPolicy", "source", "privateState"):
            require(type(observation[key]) is str and HEX.fullmatch(observation[key]), "Observation digest unavailable")
        require(type(observation["invocation"]) is str and HEX.fullmatch(observation["invocation"]), "Invocation identity missing")
        if stopped:
            require(observation["processClosed"] is True, "Manager/owned-process closure not proven")
        else:
            require(observation["processClosed"] is False and observation["jobsIdle"] is True
                    and observation["zonesOwned"] is True, "Busy/foreign-zone/uncertain observations")
            config, scan, schedule = observation["config"], observation["scan"], observation["schedule"]
            require(type(config) is dict and config.get("root") == "/mnt/files2/Jukebox"
                    and config.get("mpdPathMapping") is True, "Mapping-capable app identity unavailable")
            require(type(config.get("writes")) is bool and type(config.get("libraryEdits")) is bool,
                    "Permission observation missing")
            require(type(scan) is dict and scan.get("running") is False and
                    scan.get("phase") not in {"starting", "inventory", "pruning", "cancel_pending", "cancelling", "cleanup", "blocked"},
                    "Scan busy/uncertain")
            return {**observation, 'schedule': schedule_observation(schedule, observation['scheduleStorage'])}
        return observation

    @staticmethod
    def _stable_config(config):
        # Values remain private in memory; only this digest is retained by core.
        return {k: v for k, v in config.items() if k not in {"zones", "navidrome"}}

    def _context(self, o):
        return {"eligible": True, **{k: o[k] for k in ("profiles", "tools", "unit", "stopPolicy", "source", "invocation")},
                "flags": digest(canonical({"config": self._stable_config(o["config"]), "schedule": o["schedule"]})),
                "resources": digest(canonical({"state": o["privateState"], "scan": o["scan"]}))}

    def snapshot(self):
        self._window()
        o = self._observe()
        context = self._context(o)
        require({k: context[k] for k in FIELDS} == self.plan["expected"], "Observation drift from approved activation plan")
        self.before = o
        return context

    def admit_target(self, artifact):
        self._window()
        require((artifact.record() if artifact else None) == self.plan['artifact'], 'Target differs from approved plan')

    def root(self, artifact, path):
        self.admit_target(artifact)
        # IO must prohibit substitution/builds and prove the indirect registration.
        self.io.register_root(artifact, path)
        self.io.verify_root(artifact, path)

    def verify_root(self, artifact, path):
        self.io.verify_root(artifact, path)

    def backup(self, context):
        self._window()
        require(self.before is not None and self._context(self.before) == context, "Backup observation missing")
        receipt = self.io.backup(self.before)
        self.verify_backup(receipt, context)
        return receipt

    def verify_backup(self, receipt, context):
        require(receipt == self.plan['backup'], 'Backup differs from independent activation plan')
        require(self.before is not None and self._context(self.before) == context, "Backup binding changed")
        self.io.verify_backup(receipt, self.before)

    def command(self, argv):
        self._window()
        require(argv in COMMANDS.values(), "Unsupported service action")
        self.io.command(argv)

    def stopped(self, context):
        self._window()
        require(self.before is not None and self._context(self.before) == context, "Missing stopped-state binding")
        after = self._observe(stopped=True)
        for key in ("profiles", "tools", "unit", "stopPolicy", "source", "privateState"):
            require(after[key] == self.before[key], "Stopped state differs; inspect, no retry")

    def ready(self, artifact, context):
        self.admit_target(artifact)
        require(self.before is not None and self._context(self.before) == context, "Missing readiness binding")
        # Bounded read-only polling belongs to IO; never retries a service action.
        self.io.wait_config()
        after = self._observe()
        for key in ("profiles", "tools", "unit", "stopPolicy", "source", "privateState", "scan", "schedule"):
            require(after[key] == self.before[key], "Post-start state/config/profile drift")
        require(self._stable_config(after["config"]) == self._stable_config(self.before["config"]), "App flags/base config changed")
        desired = {"bravo": {"host": "127.0.0.1", "port": 6600, "musicPrefix": "Music/"}} if artifact else {}
        require(after["config"].get("zones") == desired and after["config"].get("navidrome") is None,
                "Effective playback config/precedence differs")

    def drain(self):
        self.io.drain()

    def transfer_proof(self, _):
        raise Refusal("Live HM handoff controller is separate; no implicit profile action")
