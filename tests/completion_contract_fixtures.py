"""SYNTHETIC DESIGN MODEL ONLY (#135), not a proof producer or admission validator.

Pure values: no files, adapters, clocks, credentials, commands or runtime import.
Even consistent claims never authorize writes or release native admission. A digest
comparison tests relationships, NOT authenticity or truth of supplied evidence.
"""
from copy import deepcopy
import hashlib


class ClaimsRefused(ValueError):
    pass


def need(condition):
    if not condition:
        raise ClaimsRefused('Synthetic contract claims inconsistent; no authority')


def sha(label):
    return hashlib.sha256(('SYNTHETIC ONLY: ' + label).encode()).hexdigest()


def hex_string(value, length=64):
    return type(value) is str and len(value) == length and all(c in '0123456789abcdef' for c in value)


CHECKPOINTS = (
    'read-existing-lock', 'pin-originals', 'verify-history', 'verify-current',
    'intent-write', 'intent-fsync', 'proof-write', 'proof-fsync',
    'namespace-recheck', 'registry-cas', 'registry-file-fsync',
    'registry-directory-fsync', 'independent-reread', 'commit-receipt-write',
    'commit-receipt-fsync', 'operator-acceptance',
)


def example():
    """Invented IDs/claims only. Never reads retained #131 evidence."""
    pins = {'incident': 'a' * 32, 'artifact': sha('artifact'),
            'originals': {name: sha(name) for name in ('registry', 'review', 'transaction')},
            'history': sha('separately selected historical report'),
            'producer': sha('historical producer'), 'ownership': sha('full raw link and parent identities')}
    claims = {
        'kind': 'synthetic-external-acceptance-design',
        'incident': pins['incident'], 'artifact': pins['artifact'],
        'originals': deepcopy(pins['originals']), 'history': pins['history'],
        'producer': pins['producer'], 'currentOwnership': pins['ownership'],
        'state': {'owner': 'dedicated-v1', 'pending': pins['incident'],
                  'current': None, 'review': 'consumed', 'phase': 'blocked'},
        # These are *claimed* independently produced proof digests, not booleans
        # that a real reader may trust or a way to select paths/helpers.
        'proofs': [(name, sha(name)) for name in
                   ('provenance', 'roots', 'runtime', 'namespace', 'helperClosure', 'freshApproval')],
        'resources': {'atPublication': sha('historical dataset'),
                      'current': sha('historical dataset'),
                      'freshBackupDataset': sha('historical dataset'),
                      'freshReviewDataset': sha('historical dataset'),
                      'laterChangesAcknowledgement': None},
        'window': {'bootExpected': sha('boot'), 'bootObserved': sha('boot'),
                   'sourceExpected': 'b' * 40, 'sourceObserved': 'b' * 40,
                   'captured': 100, 'now': 101, 'expires': 110},
    }
    return pins, claims


def assess_claim_relationships(pins, claims):
    """Check synthetic equality/shape only. Output is ALWAYS non-authoritative."""
    reference_pins, reference_claims = example()
    need(type(pins) is dict and set(pins) == set(reference_pins))
    need(type(claims) is dict and set(claims) == set(reference_claims))
    need(claims['kind'] == reference_claims['kind'])
    need(hex_string(pins['incident'], 32))
    for name in ('artifact', 'history', 'producer', 'ownership'):
        need(hex_string(pins[name]))
    need(type(pins['originals']) is dict and set(pins['originals']) == {'registry', 'review', 'transaction'})
    need(all(hex_string(value) for value in pins['originals'].values()))
    for name in ('incident', 'artifact', 'originals', 'history', 'producer'):
        need(type(claims[name]) is type(pins[name]) and claims[name] == pins[name])
    need(claims['currentOwnership'] == pins['ownership'])
    need(type(claims['state']) is dict and claims['state'] == {'owner': 'dedicated-v1', 'pending': pins['incident'],
                            'current': None, 'review': 'consumed', 'phase': 'blocked'})
    rows = claims['proofs']
    need(type(rows) is list and len(rows) == 6)
    proofs = {}
    for row in rows:
        need(type(row) is tuple and len(row) == 2)
        name, value = row
        need(type(name) is str and name not in proofs and hex_string(value))
        proofs[name] = value
    need(set(proofs) == {'provenance', 'roots', 'runtime', 'namespace', 'helperClosure', 'freshApproval'})
    resources = claims['resources']
    need(type(resources) is dict and set(resources) == set(reference_claims['resources']))
    for key in ('atPublication', 'current', 'freshBackupDataset', 'freshReviewDataset'):
        need(hex_string(resources[key]))
    need(resources['current'] == resources['freshBackupDataset'] == resources['freshReviewDataset'])
    changed = resources['atPublication'] != resources['current']
    need(hex_string(resources['laterChangesAcknowledgement']) if changed
         else resources['laterChangesAcknowledgement'] is None)
    window = claims['window']
    need(type(window) is dict and set(window) == set(reference_claims['window']))
    need(hex_string(window['bootExpected']) and window['bootObserved'] == window['bootExpected'])
    need(hex_string(window['sourceExpected'], 40) and window['sourceObserved'] == window['sourceExpected'])
    need(all(type(window[key]) is int for key in ('captured', 'now', 'expires')))
    need(window['captured'] <= window['now'] < window['expires'] <= window['captured'] + 600)
    return {'claimRelationshipsConsistent': True, 'laterResourcesChanged': changed,
            'writes': False, 'actionable': False, 'nativeAdmissionReleased': False,
            'notVerified': ('authenticity', 'historicalProvenance', 'currentSystemFacts',
                            'ownership', 'durability', 'approval', 'safeReleaseFeasibility')}


def checkpoint_claims(pins, claims, fault_at=None):
    """Trace design labels, NOT syscalls/crash recovery. No positive release path."""
    report = assess_claim_relationships(pins, claims)
    need(fault_at is None or fault_at in CHECKPOINTS)
    visited = []
    for point in CHECKPOINTS:
        visited.append(point)
        if point == fault_at:
            break
    return {**report, 'visited': tuple(visited), 'uncertainAt': fault_at,
            'nativeAdmission': 'blocked', 'writerImplemented': False,
            'filesystemFaultCoverage': False, 'automaticResume': False}
