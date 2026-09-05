import json
from pathlib import Path
import jsonschema
from django.test import TestCase
from masi_finance.publish.run_schema import load_schema, FORMAT_CHECKER
from masi_finance.publish.invariants import payload_digest, assert_invariants
from api.finance_run_test_utils import actor, candidate, approve, golden


class SnapshotCompatTests(TestCase):
    def test_golden_projection_schema_digest_identity_and_new_codes(self):
        from api.finance_snapshot_compat import project_snapshot
        user=actor(); run=candidate(user); approve(run,user); run.refresh_from_db()
        p=project_snapshot(run)
        jsonschema.validate(p,load_schema('finance-snapshot-1.1.0.json'),format_checker=FORMAT_CHECKER)
        self.assertEqual(p['payload_sha256'],payload_digest(p)); assert_invariants(p)
        self.assertNotEqual(p['payload_sha256'],run.payload_sha256)
        self.assertRegex(p['run_id'],r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z-[0-9a-f]{6}$')
        self.assertEqual(p['funder_contracts'][0]['id'],golden()['derived']['funder_contracts'][0]['binding_digest'])
        self.assertEqual({f['code'] for f in p['findings']},{f['code'] for f in run.payload['findings']})
        for f in p['findings']:
            if f['code']=='ORPHAN_CONTRACT_CODE': self.assertIsNone(f['contract_id'])
        self.assertEqual(run.payload,golden()['derived'])

    def test_backend_schema_copy_is_packaged_schema(self):
        path=Path(__file__).parent/'contracts/finance-snapshot-1.1.0.json'
        self.assertEqual(json.loads(path.read_text()),load_schema('finance-snapshot-1.1.0.json'))

    def test_all_new_finding_codes_are_preserved(self):
        from copy import deepcopy
        from api.finance_snapshot_compat import project_snapshot
        artifact = golden()
        for code in ('TEXT_DATE', 'MISSING_CONTRACT_PERIOD', 'ORPHAN_CONTRACT_CODE'):
            finding = deepcopy(artifact['derived']['findings'][0])
            finding.update(code=code, contract_id='UNMATCHED' if code == 'ORPHAN_CONTRACT_CODE' else artifact['derived']['funder_contracts'][0]['id'], line_id=None)
            artifact['derived']['findings'].append(finding)
        user = actor()
        run = candidate(user, artifact=artifact)
        run = approve(run, user)
        projected = project_snapshot(run)
        self.assertTrue({'TEXT_DATE', 'MISSING_CONTRACT_PERIOD', 'ORPHAN_CONTRACT_CODE'} <= {f['code'] for f in projected['findings']})
        self.assertTrue(all(f['contract_id'] is None for f in projected['findings'] if f['code'] == 'ORPHAN_CONTRACT_CODE'))
