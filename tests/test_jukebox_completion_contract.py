"""#135 design claims + CURRENT refusal behavior, synthetic filesystem/API only.

No completion writer or operational schema is implemented by these tests.
"""
import ast
from copy import deepcopy
import json
from pathlib import Path
import shutil
import unittest

import completion_contract_fixtures as model
from test_jukebox_native_fixture import NativeFixture
import jukebox_playback as p
import jukebox_window as w


class ClaimsModelTests(unittest.TestCase):
    def test_consistent_claims_still_have_no_authority(self):
        pins, claims = model.example()
        before = deepcopy((pins, claims))
        result = model.assess_claim_relationships(pins, claims)
        self.assertTrue(result['claimRelationshipsConsistent'])
        for field in ('writes', 'actionable', 'nativeAdmissionReleased'):
            self.assertIs(result[field], False)
        self.assertIn('authenticity', result['notVerified'])
        self.assertIn('safeReleaseFeasibility', result['notVerified'])
        self.assertEqual((pins, claims), before)

    def test_missing_or_unknown_top_level_fields_refuse(self):
        for key in model.example()[1]:
            pins, claims = model.example(); del claims[key]
            with self.subTest(missing=key), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)
        pins, claims = model.example(); claims['command'] = 'SYNTHETIC_FORBIDDEN'
        with self.assertRaises(model.ClaimsRefused): model.assess_claim_relationships(pins, claims)

    def test_incident_originals_artifact_history_and_producer_must_match_separate_pins(self):
        for key in ('incident', 'artifact', 'history', 'producer', 'currentOwnership'):
            pins, claims = model.example(); claims[key] = 'c' * (32 if key == 'incident' else 64)
            with self.subTest(key=key), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)
        for key in ('registry', 'review', 'transaction'):
            pins, claims = model.example(); claims['originals'][key] = model.sha('changed ' + key)
            with self.subTest(record=key), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)

    def test_consumed_blocked_pending_is_not_native_success_or_transfer(self):
        for key, value in [('review', 'pending'), ('phase', 'verified'), ('pending', None),
                           ('current', model.sha('artifact')), ('owner', 'transferred')]:
            pins, claims = model.example(); claims['state'][key] = value
            with self.subTest(key=key), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)

    def test_claimed_proofs_must_have_exact_distinct_domains_not_booleans_or_paths(self):
        for case in ('missing', 'duplicate', 'unknown', 'boolean', 'path'):
            pins, claims = model.example()
            if case == 'missing': claims['proofs'].pop()
            elif case == 'duplicate': claims['proofs'][-1] = claims['proofs'][0]
            elif case == 'unknown': claims['proofs'][-1] = ('repairCommand', model.sha('unknown'))
            else: claims['proofs'][0] = ('provenance', True if case == 'boolean' else '/SYNTHETIC/UNTRUSTED/PATH')
            with self.subTest(case=case), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)

    def test_equal_artifact_bytes_do_not_accept_new_link_parent_or_inode_claim(self):
        pins, claims = model.example()
        claims['currentOwnership'] = model.sha('same text but recreated inode or changed parent')
        self.assertEqual(claims['artifact'], pins['artifact'])
        with self.assertRaises(model.ClaimsRefused): model.assess_claim_relationships(pins, claims)

    def test_later_user_edits_need_current_review_and_backup_not_historical_restore(self):
        pins, claims = model.example(); original_history = claims['resources']['atPublication']
        for key in ('current', 'freshBackupDataset', 'freshReviewDataset'):
            claims['resources'][key] = model.sha('legitimate later edits')
        claims['resources']['laterChangesAcknowledgement'] = model.sha('fresh reviewed changes')
        result = model.assess_claim_relationships(pins, claims)
        self.assertTrue(result['laterResourcesChanged'])
        self.assertEqual(claims['resources']['atPublication'], original_history)
        self.assertFalse(result['nativeAdmissionReleased'])

    def test_unreviewed_later_edits_or_stale_backup_refuse(self):
        for case in ('missingAcknowledgement', 'oldBackup', 'oldReview'):
            pins, claims = model.example()
            for key in ('current', 'freshBackupDataset', 'freshReviewDataset'):
                claims['resources'][key] = model.sha('later edits')
            claims['resources']['laterChangesAcknowledgement'] = model.sha('fresh reviewed changes')
            if case == 'missingAcknowledgement': claims['resources']['laterChangesAcknowledgement'] = None
            elif case == 'oldBackup': claims['resources']['freshBackupDataset'] = claims['resources']['atPublication']
            else: claims['resources']['freshReviewDataset'] = claims['resources']['atPublication']
            with self.subTest(case=case), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)

    def test_reboot_source_time_drift_and_boolean_time_refuse(self):
        for key, value in [('bootObserved', model.sha('different boot')), ('sourceObserved', 'c' * 40),
                           ('now', 99), ('now', 110), ('expires', 701), ('now', True)]:
            pins, claims = model.example(); claims['window'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(model.ClaimsRefused):
                model.assess_claim_relationships(pins, claims)

    def test_copied_or_forged_matching_hash_claims_never_prove_authenticity(self):
        pins, claims = model.example()
        result = model.assess_claim_relationships(deepcopy(pins), deepcopy(claims))
        self.assertIn('historicalProvenance', result['notVerified'])
        self.assertIn('approval', result['notVerified'])
        self.assertFalse(result['actionable'])

    def test_each_design_checkpoint_is_non_operational_not_filesystem_fault_coverage(self):
        pins, claims = model.example(); before = deepcopy((pins, claims))
        for fault in (*model.CHECKPOINTS, None):
            with self.subTest(fault=fault):
                result = model.checkpoint_claims(pins, claims, fault)
                self.assertEqual(result['nativeAdmission'], 'blocked')
                self.assertFalse(result['writerImplemented'])
                self.assertFalse(result['filesystemFaultCoverage'])
                self.assertFalse(result['automaticResume'])
                self.assertEqual(result['uncertainAt'], fault)
        self.assertEqual((pins, claims), before)

    def test_model_has_no_operational_dependencies_or_runtime_consumer(self):
        source = Path(model.__file__).read_text(); tree = ast.parse(source)
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        modules.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual(modules, {'copy', 'hashlib'})
        for path in (Path(__file__).resolve().parents[1] / 'scripts').glob('jukebox*.py'):
            self.assertNotIn('completion_contract_fixtures', path.read_text())


class CurrentRuntimeRefusalTests(unittest.TestCase):
    def setUp(self):
        self.x = NativeFixture(); x = self.x
        def remove_loader():
            shutil.rmtree(x.paths['proc'] / str(x.pid) / 'task' / str(x.pid + 1000))
        x.on_start = remove_loader
        x.seal_backup(); adapter = x.make_adapter(x.f.a); x.f.publisher.adapter = adapter
        corrected_ready = adapter.ready
        def simulate_historical_false_verification(artifact, context):
            corrected_ready(artifact, context)
            raise p.Refusal('Synthetic historical post-publication worker rejection')
        adapter.ready = simulate_historical_false_verification
        self.review = x.f.publisher.review(x.f.a, approve=True)
        with self.assertRaises(p.Refusal): x.f.publisher.apply(self.review['id'], approve=True)
        self.originals = self.record_bytes()
        registry = json.loads(self.originals['registry'])
        self.assertIsNone(registry['current']); self.assertEqual(registry['pending'], self.review['id'])
        self.assertEqual(json.loads(self.originals['transaction'])['phase'], 'blocked')
        self.assertNotIn('ownership', json.loads(self.originals['transaction']))
        self.assertEqual(json.loads(self.originals['review'])['status'], 'consumed')
        self.assertEqual(x.f.fs.snapshot(p.STATE + '/active')['link'], str(x.f.a.directory))
        for target in p.TARGETS.values(): self.assertIsNotNone(x.f.fs.snapshot(target))
        self.published_paths = [*p.TARGETS.values(), p.STATE + '/active', p.STATE + '/roots/' + x.f.a.hash]
        self.published = {path: x.f.fs.snapshot(path) for path in self.published_paths}
        self.initial_actions = self.service_actions()
        self.assertEqual(len(self.initial_actions), 3)

    def tearDown(self): self.x.close()

    def record_bytes(self):
        fs = self.x.f.fs; rid = self.review['id']
        return {'registry': fs.read(p.STATE + '/registry.json'),
                'review': fs.read(p.STATE + '/reviews/' + rid + '.json'),
                'transaction': fs.read(p.STATE + '/transactions/' + rid + '.json')}

    def service_actions(self):
        return [args for tool, args in self.x.calls if tool == 'systemctl' and 'show' not in args]

    def assert_still_blocked(self):
        publisher = self.x.f.publisher
        with publisher.lock(shared=True):
            with self.assertRaises(p.Refusal): publisher._registry()
        self.assertEqual(self.record_bytes(), self.originals)
        self.assertEqual({path: self.x.f.fs.snapshot(path) for path in self.published_paths}, self.published)
        self.assertEqual(self.service_actions(), self.initial_actions)

    def test_corrected_readonly_observation_does_not_finalize_original_incident(self):
        prototype = object.__new__(w.WindowAdapter); prototype.io = self.x.io
        observed = prototype._observe()
        self.assertTrue(observed['jobsIdle']); self.assertTrue(observed['zonesOwned'])
        self.assert_still_blocked()

    def test_ordinary_apply_rollback_review_and_discard_do_not_release_blocked_state(self):
        publisher = self.x.f.publisher
        operations = [lambda: publisher.apply(self.review['id'], approve=True),
                      lambda: publisher.apply(self.review['id'], approve=True, rollback=True),
                      lambda: publisher.discard(self.review['id'], approve=True),
                      lambda: publisher.review(self.x.f.a, approve=True),
                      lambda: publisher.review(None, approve=True, rollback=True)]
        for operation in operations:
            with self.assertRaises(p.Refusal): operation()
            self.assert_still_blocked()

    def test_external_acceptance_report_alone_never_releases_current_admission(self):
        pins, claims = model.example(); report = model.assess_claim_relationships(pins, claims)
        (self.x.f.root / 'external-acceptance.json').write_text(json.dumps(report))
        self.assert_still_blocked()

    def test_new_unsupported_ledger_namespace_is_not_a_legacy_reader_exemption(self):
        fs = self.x.f.fs
        fs.mkdir(p.STATE + '/completions')
        fs.write(p.STATE + '/completions/unsupported.json', {'schema': 'UNACCEPTED-DESIGN', 'verified': True}, new=True)
        self.assert_still_blocked()

    def test_all_design_fault_labels_leave_actual_originals_and_service_actions_unchanged(self):
        pins, claims = model.example()
        for boundary in (*model.CHECKPOINTS, None):
            model.checkpoint_claims(pins, claims, boundary)
            self.assert_still_blocked()


if __name__ == '__main__': unittest.main()
