"""Scheduler observation regressions: isolated SQLite and recorded fake services."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jukebox_playback as p
import jukebox_window as w
from test_jukebox_native_fixture import NativeFixture
from schedule_fixtures import SCHEDULE_SQL, cold_state, status


def put_state(x, state):
    record = {**state, 'root': str(x.paths['root'])}
    db = sqlite3.connect(x.paths['data'] / 'jukebox.sqlite')
    try:
        db.execute('DELETE FROM collector_schedule_v1')
        db.execute('INSERT INTO collector_schedule_v1 VALUES(?,?)', ('KEXP', json.dumps(record)))
        db.commit()
    finally: db.close()


def historical_state():
    state = cold_state(999000)
    state.update(intervalHours=4, startHour=6, endHour=22, watermark=998000, failures=2,
                 rightsConfirmedAt='2026-10-30T01:02:03.123Z', rightsAttestation=w.SCHEDULE_RIGHTS,
                 last={'kind': 'disabled-access', 'at': 999000, 'slotAt': 998000,
                       'runId': cold_state()['revision']})
    return state


class SchedulerTests(unittest.TestCase):
    def test_repeated_empty_table_reads_ignore_capture_time_only_after_storage_proof(self):
        x = NativeFixture()
        try:
            x.seal_backup(); adapter = x.make_adapter(x.f.a)
            first = adapter.snapshot(); second = adapter.snapshot()
            self.assertEqual(first, second)
            self.assertGreater(x.captured_at, 1000000)
            self.assertFalse(any(tool == 'systemctl' and 'show' not in args for tool, args in x.calls))
        finally: x.close()

    def test_empty_table_fake_restart_changes_only_process_local_identity_and_never_persists_a_definition(self):
        x = NativeFixture()
        try:
            x.seal_backup(); before = copy.deepcopy(x.cold_schedule)
            x.f.publisher.adapter = x.make_adapter(x.f.a)
            reviewed = x.f.publisher.review(x.f.a, approve=True)
            x.f.publisher.apply(reviewed['id'], approve=True)
            self.assertNotEqual(x.cold_schedule['revision'], before['revision'])
            self.assertNotEqual(x.cold_schedule['last']['at'], before['last']['at'])
            self.assertEqual(x.f.publisher.inspect()['state'], 'owned')
            db = sqlite3.connect(x.paths['data'] / 'jukebox.sqlite')
            try: self.assertEqual(db.execute('SELECT count(*) FROM collector_schedule_v1').fetchone()[0], 0)
            finally: db.close()
        finally: x.close()

    def test_persisted_disabled_history_preserves_every_state_field_across_repeated_reads_and_restart(self):
        for state in (cold_state(999000), historical_state()):
            x = NativeFixture()
            try:
                put_state(x, state); x.seal_backup(); adapter = x.make_adapter(x.f.a)
                context = adapter.snapshot()
                self.assertEqual(adapter.before['schedule']['storage'], 'stored')
                self.assertEqual(adapter.before['schedule']['state'], state)
                self.assertEqual(adapter.snapshot(), context)
                x.f.publisher.adapter = adapter
                reviewed = x.f.publisher.review(x.f.a, approve=True); x.f.publisher.apply(reviewed['id'], approve=True)
                self.assertEqual(adapter.before['schedule']['state'], state)
                db = sqlite3.connect(x.paths['data'] / 'jukebox.sqlite')
                try: self.assertEqual(json.loads(db.execute('SELECT json FROM collector_schedule_v1').fetchone()[0]), {**state, 'root': str(x.paths['root'])})
                finally: db.close()
            finally: x.close()

    def test_empty_api_defaults_require_independent_known_schema_and_exact_empty_storage(self):
        for kind in ('missing', 'wrong-columns', 'weakened-constraint', 'trigger', 'malformed', 'duplicate-key', 'wrong-root', 'extra-row'):
            with self.subTest(kind=kind):
                x = NativeFixture()
                try:
                    db = sqlite3.connect(x.paths['data'] / 'jukebox.sqlite')
                    try:
                        if kind in ('missing', 'wrong-columns', 'weakened-constraint'):
                            db.execute('DROP TABLE collector_schedule_v1')
                            if kind == 'wrong-columns': db.execute('CREATE TABLE collector_schedule_v1(foo TEXT)')
                            if kind == 'weakened-constraint': db.execute('CREATE TABLE collector_schedule_v1(station TEXT PRIMARY KEY,json TEXT NOT NULL)')
                        elif kind == 'trigger': db.execute('CREATE TRIGGER unsupported AFTER INSERT ON collector_schedule_v1 BEGIN SELECT 1; END')
                        else:
                            record = {**cold_state(), 'root': str(x.paths['root'])}
                            if kind == 'wrong-root': record['root'] = '/wrong-root'
                            raw = json.dumps(record)
                            if kind == 'malformed': raw = '{}'
                            if kind == 'duplicate-key': raw = raw[:-1] + ',"enabled":false}'
                            db.execute('INSERT INTO collector_schedule_v1 VALUES(?,?)', ('KEXP', raw))
                            if kind == 'extra-row':
                                db.execute('PRAGMA ignore_check_constraints=ON')
                                db.execute('INSERT INTO collector_schedule_v1 VALUES(?,?)', ('foreign', raw))
                        db.commit()
                    finally: db.close()
                    with self.assertRaises((p.Refusal, sqlite3.DatabaseError)): x.io.observe()
                    self.assertFalse(any(tool == 'systemctl' and 'show' not in args for tool, args in x.calls))
                finally: x.close()

    def test_schema_and_storage_rows_are_collected_in_the_same_logical_read_transaction(self):
        x = NativeFixture()
        try:
            contents = w.database_contents; storage = w.scheduler_storage; connections = []
            def hash_rows(db, *args, **kwargs):
                result = contents(db, *args, **kwargs)
                self.assertTrue(db.in_transaction); connections.append(id(db)); return result
            def read_storage(db, root):
                self.assertTrue(db.in_transaction); connections.append(id(db)); return storage(db, root)
            with patch.object(w, 'database_contents', side_effect=hash_rows), patch.object(w, 'scheduler_storage', side_effect=read_storage):
                observed = x.io.observe()
            self.assertEqual(len(connections), 2); self.assertEqual(connections[0], connections[1])
            self.assertEqual(observed['scheduleStorage'], {'kind': 'empty'})
            self.assertEqual(x.io.offline['database']['tables']['collector_schedule_v1']['count'], 0)
        finally: x.close()

    def test_unconfigured_projection_omits_only_process_local_ids_and_does_not_mutate_raw_dto(self):
        raw = status(); original = copy.deepcopy(raw)
        projected = w.schedule_observation(raw, {'kind': 'empty'})
        expected = copy.deepcopy(raw['state']); expected.pop('revision'); expected['last'].pop('at')
        self.assertEqual(projected['state'], expected); self.assertEqual(projected['storage'], 'empty')
        self.assertNotIn('capturedAt', projected); self.assertEqual(raw, original)
        for evidence in (None, {}, {'kind': 'unknown'}, {'kind': 'empty', 'selfAsserted': True}):
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, evidence)

    def test_status_flags_types_unknown_fields_and_forged_api_storage_evidence_refuse(self):
        mutations = [lambda r: r.pop('available'), lambda r: r.update(extra=True),
                     lambda r: r.update(storage={'kind': 'empty'}), lambda r: r.update(capturedAt=True),
                     lambda r: r.update(capturedAt=-1), lambda r: r.update(capturedAt=float('nan')),
                     lambda r: r.update(available=False), lambda r: r.update(available=1),
                     lambda r: r.update(capability=True), lambda r: r.update(capability=0),
                     lambda r: r.update(active=True), lambda r: r.update(blocked=True),
                     lambda r: r.update(state=None)]
        for mutate in mutations:
            raw = status(); mutate(raw)
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'empty'})

    def test_empty_storage_does_not_excuse_nondefault_state_or_bad_identity(self):
        mutations = [('station', 'foreign'), ('version', True), ('version', 2), ('enabled', True),
                     ('intervalHours', 2), ('intervalHours', True), ('startHour', 1), ('endHour', 23),
                     ('nextAt', 1), ('activeSlot', 1), ('watermark', 1), ('failures', 1), ('failures', True),
                     ('revision', 'not-a-uuid'), ('rightsConfirmedAt', '2026-10-30T01:02:03.123Z'),
                     ('rightsAttestation', w.SCHEDULE_RIGHTS)]
        for key, value in mutations:
            raw = status(); raw['state'][key] = value
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'empty'})
        for key, value in (('kind', 'configured'), ('slotAt', 1), ('runId', cold_state()['revision']), ('at', True)):
            raw = status(); raw['state']['last'][key] = value
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'empty'})
        raw = status(); raw['state']['unexpected'] = True
        with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'empty'})
        raw = status(); raw['state']['last']['unexpected'] = True
        with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'empty'})

    def test_api_state_must_equal_the_stored_record_not_just_look_disabled(self):
        state = historical_state()
        for key, value in [('revision', cold_state()['revision']), ('intervalHours', 6), ('startHour', 7),
                           ('endHour', 23), ('watermark', 997000), ('failures', 1),
                           ('rightsConfirmedAt', '2026-10-30T01:02:04.123Z')]:
            raw = status(copy.deepcopy(state)); raw['state'][key] = value
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'stored', 'state': state})
        for key, value in [('kind', 'disabled-failures'), ('at', 999001), ('slotAt', 997000), ('runId', cold_state()['revision'])]:
            raw = status(copy.deepcopy(state)); raw['state']['last'][key] = value
            with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'stored', 'state': state})
        raw = status(copy.deepcopy(state)); raw['state']['rightsConfirmedAt'] = '2026-02-30T01:02:03.123Z'
        with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'stored', 'state': raw['state']})
        raw = status(copy.deepcopy(state)); raw['state']['rightsAttestation'] = 'different'
        with self.assertRaises(p.Refusal): w.schedule_observation(raw, {'kind': 'stored', 'state': raw['state']})

    def test_configured_state_changes_and_storage_presence_transitions_invalidate_plan_before_service_action(self):
        for kind in ('revision', 'last-time', 'definition', 'failure', 'rights', 'watermark', 'insert', 'delete'):
            with self.subTest(kind=kind):
                x = NativeFixture()
                try:
                    state = historical_state()
                    if kind != 'insert': put_state(x, state)
                    x.seal_backup(); adapter = x.make_adapter(x.f.a)
                    changed = copy.deepcopy(state)
                    if kind == 'revision': changed['revision'] = cold_state()['revision']
                    if kind == 'last-time': changed['last']['at'] += 1
                    if kind == 'definition': changed['intervalHours'] = 6
                    if kind == 'failure': changed['failures'] = 1
                    if kind == 'rights': changed['rightsConfirmedAt'] = '2026-10-30T01:02:04.123Z'
                    if kind == 'watermark': changed['watermark'] -= 1
                    if kind == 'delete':
                        db = sqlite3.connect(x.paths['data'] / 'jukebox.sqlite'); db.execute('DELETE FROM collector_schedule_v1'); db.commit(); db.close()
                    else: put_state(x, changed)
                    with self.assertRaises(p.Refusal): adapter.snapshot()
                    self.assertFalse(any(tool == 'systemctl' and 'show' not in args for tool, args in x.calls))
                finally: x.close()

    def test_post_start_real_state_drift_still_blocks_without_automatic_retry_or_rollback(self):
        for kind in ('stored-revision', 'new-definition', 'unexpected-default', 'unavailable'):
            x = NativeFixture()
            try:
                state = historical_state()
                if kind == 'stored-revision': put_state(x, state)
                x.seal_backup(); x.f.publisher.adapter = x.make_adapter(x.f.a)
                reviewed = x.f.publisher.review(x.f.a, approve=True)
                def mutate():
                    if kind == 'stored-revision':
                        changed = copy.deepcopy(state); changed['revision'] = cold_state()['revision']; put_state(x, changed)
                    elif kind == 'new-definition': put_state(x, historical_state())
                    elif kind == 'unexpected-default': x.cold_schedule['failures'] = 1
                    else:
                        original = x.api
                        def api(endpoint):
                            result = original(endpoint)
                            if endpoint == 'operations/schedule': result['available'] = False
                            return result
                        x.api = api
                x.on_start = mutate
                with self.assertRaises(p.Refusal): x.f.publisher.apply(reviewed['id'], approve=True)
                actions = [args for tool, args in x.calls if tool == 'systemctl' and 'show' not in args]
                self.assertEqual(actions, [['--user', 'stop', 'jukebox-manager.service'], ['--user', 'daemon-reload'], ['--user', 'start', 'jukebox-manager.service']])
            finally: x.close()


if __name__ == '__main__': unittest.main()
