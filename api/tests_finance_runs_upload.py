from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlencode
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from masi_finance.publish.run_artifact import build_run_artifact, facts_digest, payload_digest
from api.finance_run_test_utils import actor
from api.models import FinanceRun, LedgerRow, LedgerAllocation
from api.tests_finance_upload_safety import workbook_bytes, rewrite, MIME, NAME


class FinanceUploadTests(TestCase):
    def setUp(self):
        self.user = actor()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.data = workbook_bytes()
        self.url = '/api/finance/runs/?' + urlencode(dict(kind='funders', year=2026, source_name=NAME))

    def upload(self, data=None, suffix=''):
        return self.client.post(self.url + suffix, data if data is not None else self.data, content_type=MIME)

    def test_raw_upload_manifest_version_digests_metrics(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.data)
        run = FinanceRun.objects.get()
        artifact = build_run_artifact(self.data, source_name=NAME, accounting_year=2026)
        self.assertEqual(run.status, 'candidate')
        self.assertEqual(run.manifest, artifact['manifest'])
        self.assertEqual((run.schema_version, run.producer_version), ('2.0.0', '0.2.0'))
        self.assertEqual(run.payload_sha256, payload_digest(artifact))
        self.assertEqual(run.facts_sha256, facts_digest(artifact['ledger']))
        self.assertEqual((run.fact_row_count, run.allocation_count), (1, 1))
        self.assertGreater(run.peak_memory_bytes, 0)
        self.assertGreaterEqual(run.total_duration_ms, run.parse_duration_ms)
        self.assertGreater(run.parse_duration_ms, 0)

    def test_second_publisher_replay_review_approve_preserves_uploader(self):
        first = self.upload()
        self.assertEqual(first.status_code, 201)
        other = actor('other')
        self.client.force_authenticate(other)
        with patch('api.services.finance_runs.build_run_artifact', side_effect=AssertionError('recomputed')):
            replay = self.upload()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data['id'], first.data['id'])
        detail = '/api/finance/runs/' + replay.data['id'] + '/'
        self.assertEqual(self.client.get(detail).status_code, 200)
        approved = self.client.post(detail + 'approve/', {'acknowledge_findings': True, 'note': 'Reviewed'}, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)
        run = FinanceRun.objects.get()
        self.assertEqual((run.uploaded_by_id, run.approved_by_id), (self.user.pk, other.pk))

    def test_known_producer_failure_creates_one_safe_failed_run(self):
        from masi_finance.publish.contracts import ContractKeyError
        with patch('api.services.finance_runs.build_run_artifact', side_effect=ContractKeyError('REVERSED_CONTRACT_PERIOD')):
            response = self.upload()
        self.assertEqual(response.status_code, 201)
        run = FinanceRun.objects.get()
        self.assertEqual(run.failure, {'phase': 'producer', 'code': 'REVERSED_CONTRACT_PERIOD', 'message': 'REVERSED_CONTRACT_PERIOD'})
        self.assertEqual(run.status, 'failed')
        self.assertIsNone(run.payload)
        self.assertFalse(LedgerRow.objects.exists())
        self.assertEqual(self.upload().status_code, 200)

    def test_sheet_failure_is_failed_history(self):
        data = rewrite(self.data, {'xl/workbook.xml': lambda x: x.replace(b'Expenditure', b'Other')})
        self.assertEqual(self.upload(data).status_code, 201)
        self.assertEqual(FinanceRun.objects.get().failure['code'], 'REQUIRED_SHEETS')

    def test_unexpected_failure_rolls_back_all_inserts_value_free(self):
        from api.services.finance_runs import materialise_facts
        def fail(run, artifact):
            materialise_facts(run, artifact)
            raise RuntimeError('PRIVATE_NAME 123.45')
        with patch('api.services.finance_runs.materialise_facts', side_effect=fail):
            response = self.upload()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {'code': 'UPLOAD_INTERNAL_ERROR'})
        self.assertFalse(FinanceRun.objects.exists())
        self.assertFalse(LedgerRow.objects.exists())
        self.assertFalse(LedgerAllocation.objects.exists())

    def test_internal_producer_failure_and_untrusted_error_are_not_failed_rows(self):
        from masi_finance.publish.run_artifact import RunArtifactError
        for error in (RuntimeError('PRIVATE'), RunArtifactError('PRIVATE'), RunArtifactError('WORKBOOK_DECODE_FAILURE')):
            with self.subTest(error=type(error)), patch('api.services.finance_runs.build_run_artifact', side_effect=error):
                response = self.upload()
                self.assertEqual(response.status_code, 500)
                self.assertFalse(FinanceRun.objects.exists())

    def test_permission_before_bytes_and_unsupported_methods(self):
        from api.views.finance_runs import FinanceRunList
        self.client.force_authenticate(actor('staff', 'STAFF'))
        with patch('api.services.finance_runs.preflight', side_effect=AssertionError('bytes read')):
            self.assertEqual(self.upload().status_code, 403)
        self.client.force_authenticate(self.user)
        for method in ('put', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)

    def test_mutation_metadata_rejected(self):
        for field in ('uploaded_by', 'uploaded_at', 'status', 'manifest', 'payload', 'producer_version', 'approved_by'):
            with self.subTest(field=field):
                response = self.upload(suffix='&' + field + '=private')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {'code': 'UPLOAD_METADATA_INVALID'})
        self.assertFalse(FinanceRun.objects.exists())

    def test_no_temporary_files_or_storage_and_large_http_body(self):
        import os
        data = rewrite(self.data, extra=[('padding.bin', os.urandom(2700000))])
        with patch('tempfile.TemporaryFile', side_effect=AssertionError('temp')), \
             patch('tempfile.NamedTemporaryFile', side_effect=AssertionError('temp')), \
             patch('django.core.files.storage.Storage.save', side_effect=AssertionError('storage')):
            self.assertEqual(self.upload(data).status_code, 201)

    def test_http_request_body_property_is_never_read(self):
        from django.core.handlers.wsgi import WSGIRequest
        from api.views.finance_runs import FinanceRunList
        request = APIRequestFactory().post(self.url, self.data, content_type=MIME)
        force_authenticate(request, self.user)
        with patch.object(WSGIRequest, 'body', property(lambda s: (_ for _ in ()).throw(AssertionError('body')))):
            self.assertEqual(FinanceRunList.as_view()(request).status_code, 201)

    def test_http_missing_and_lying_length_reads_actual_stream(self):
        from api.views.finance_runs import FinanceRunList
        from api.parsers import finance_workbook
        for length in (None, '1'):
            with self.subTest(length=length):
                request = APIRequestFactory().post(self.url, self.data, content_type=MIME)
                # A WSGI server supplies the framed stream independently of the
                # header. Model both chunked input and a false declared length.
                request.environ['wsgi.input'] = BytesIO(self.data)
                if length is None:
                    request.META.pop('CONTENT_LENGTH', None)
                else:
                    request.META['CONTENT_LENGTH'] = length
                force_authenticate(request, self.user)
                with patch.object(finance_workbook, 'MAX_COMPRESSED', 1024):
                    response = FinanceRunList.as_view()(request)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {'code': 'UPLOAD_TOO_LARGE'})
                self.assertEqual(request.environ['wsgi.input'].tell(), 1025)
        self.assertFalse(FinanceRun.objects.exists())

    def test_lock_conflict_does_not_scan_or_produce(self):
        from api.services.finance_runs import FinanceRunError
        with patch('api.services.finance_runs.acquire_tuple_lock', side_effect=FinanceRunError('UPLOAD_IN_PROGRESS')), \
             patch('api.services.finance_runs.scan_workbook') as scan, \
             patch('api.services.finance_runs.build_run_artifact') as producer:
            response = self.upload()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data, {'code': 'UPLOAD_IN_PROGRESS'})
        scan.assert_not_called()
        producer.assert_not_called()

    def test_exact_version_pair_failure_is_internal_rollback(self):
        artifact = build_run_artifact(self.data, source_name=NAME, accounting_year=2026)
        artifact['manifest']['producer']['version'] = '0.3.0'
        with patch('api.services.finance_runs.build_run_artifact', return_value=artifact):
            self.assertEqual(self.upload().status_code, 500)
        self.assertFalse(FinanceRun.objects.exists())

    def test_client_timestamp_accepts_rfc3339_and_rejects_other_metadata(self):
        for stamp in ('2026-09-01T12:30:00Z', '2026-09-01T12:30:00.123-04:00'):
            with self.subTest(stamp=stamp):
                self.assertIn(self.upload(suffix='&' + urlencode({'client_modified_at': stamp})).status_code, (200, 201))
        self.assertEqual(self.upload(suffix='&client_modified_at=private').status_code, 400)

    def test_benchmark_full_path_and_replay_marked(self):
        import json
        from io import StringIO
        from django.core.management import call_command
        from pathlib import Path
        original_open = Path.open
        def open_input(path, *args, **kwargs):
            return BytesIO(self.data) if str(path) == NAME else original_open(path, *args, **kwargs)
        with patch('pathlib.Path.open', autospec=True, side_effect=open_input):
            output = StringIO()
            call_command('benchmark_finance_upload', NAME, actor_user_id=self.user.pk, year=2026, stdout=output)
        record = json.loads(output.getvalue())
        self.assertEqual((record['status'], record['row_count'], record['allocation_count']), ('candidate', 1, 1))
        self.assertEqual(record['measurement'], 'new_run')
        self.assertGreater(record['process_peak_rss_bytes'], 0)
        from django.db import connection
        self.assertEqual(record['database_engine'], connection.settings_dict['ENGINE'])

    def test_mutation_negative_roles_and_service_guard(self):
        from django.contrib.auth.models import Permission
        from api.services.finance_runs import upload_workbook, FinanceRunError
        for name, role in [('pm', 'PROJECT MANAGER'), ('plain', 'STAFF'), ('reader', 'STAFF')]:
            user = actor(name, role)
            if name == 'reader':
                user.user_permissions.add(Permission.objects.get(codename='read_finance', content_type__model='financerun'))
            self.client.force_authenticate(user)
            with patch('api.services.finance_runs.preflight', side_effect=AssertionError('read')):
                self.assertEqual(self.upload().status_code, 403)
                with self.assertRaises(FinanceRunError) as caught:
                    upload_workbook(BytesIO(self.data), user, kind='funders', year=2026, source_name=NAME, content_type=MIME)
                self.assertEqual(caught.exception.code, 'PUBLISH_FORBIDDEN')

    def test_unsafe_xml_returns_400_without_history(self):
        data = rewrite(self.data, {'xl/workbook.xml': lambda x: b'<!DOCTYPE x [<!ENTITY secret "private">]>' + x})
        response = self.upload(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'code': 'XML_INVALID'})
        self.assertFalse(FinanceRun.objects.exists())
