"""Synthetic scheduler responses matching App/shared/schedule.ts; no app IO."""
from uuid import uuid4

SCHEDULE_SQL = "CREATE TABLE collector_schedule_v1(station TEXT PRIMARY KEY CHECK(station='KEXP'),json TEXT NOT NULL)"

def cold_state(at=1000000, revision=None):
    return {'station': 'KEXP', 'enabled': False, 'intervalHours': 1, 'startHour': 0, 'endHour': 24,
            'version': 1, 'revision': revision or str(uuid4()), 'nextAt': None, 'activeSlot': None,
            'watermark': None, 'failures': 0, 'rightsConfirmedAt': None, 'rightsAttestation': None,
            'last': {'kind': 'never', 'at': at, 'slotAt': None, 'runId': None}}

def status(state=None, captured_at=1000000):
    return {'capturedAt': captured_at, 'available': True, 'capability': False,
            'active': False, 'blocked': False, 'state': cold_state() if state is None else state}
