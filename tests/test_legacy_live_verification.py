import json
from pathlib import Path, PurePosixPath
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import legacy_verify_unchanged as live
from tests import test_legacy_static_bundle as fixtures


class FakeClient:
    def __init__(self, files):
        self.files = files
        self.closed = False
        self.writes = []

    def set_debuglevel(self, value):
        assert value == 0

    def connect(self, host, port):
        assert (host, port) == (live.publisher.HOST, 21)

    def auth(self):
        pass

    def login(self, user, password):
        assert user == live.publisher.USER and password == 'synthetic-secret'

    def prot_p(self):
        pass

    def set_pasv(self, value):
        assert value is True

    def cwd(self, value):
        assert value == live.publisher.REMOTE_ROOT

    def close(self):
        self.closed = True

    def mlsd(self, directory):
        dirs = {'reikai', 'reikai/2026', 'reikai/2026/images_261004'}
        return ([(PurePosixPath(p).name, {'type': 'dir'}) for p in dirs
                 if str(PurePosixPath(p).parent) == directory]
                + [(PurePosixPath(p).name, {'type': 'file'}) for p in self.files
                   if str(PurePosixPath(p).parent) == directory])

    def retrbinary(self, command, callback):
        callback(self.files[command.removeprefix('RETR ')])

    def storbinary(self, *args):
        self.writes.append(args)
        raise AssertionError('An underlying writer must never be called')


class LiveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StaticBundleTests('test_unchanged_static_source_is_noop_without_output')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.files = {p: (self.fixture.source / p).read_bytes() for p in self.fixture.paths}
        self.client = FakeClient(dict(self.files))
        self.factory = Mock(return_value=self.client)
        self.head = 'a' * 40
        self.report = self.fixture.root / 'report.json'
        for patcher in (
            patch.object(live, 'checked_head', return_value=self.head),
            patch.object(live, 'MANIFEST', self.fixture.baseline / 'manifest.json'),
            patch.object(live, 'MANIFEST_SHA', self.fixture.sha),
            patch.dict('os.environ', {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/master',
                                     'GT030_PUBLISH_ENVIRONMENT': 'legacy-publish',
                                     'SAKURA_FTPS_PASSWORD': 'synthetic-secret'}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def verify(self, get=None):
        return live.verify(self.head, self.report, get=self.files.get if get is None else get,
                           ftp_factory=self.factory)

    def test_full_noop_has_27_verified_zero_writes_and_minimal_report(self):
        result = self.verify()
        self.assertEqual(result['status'], 'UNCHANGED_VERIFIED')
        self.assertEqual(result['verified_count'], 27)
        self.assertEqual(result['skipped_count'], 27)
        self.assertEqual(result['uploaded_count'], 0)
        self.assertFalse(result['remote_writes_permitted'])
        self.assertEqual(result['https_reads'], 81)
        self.assertEqual(result['ftp_reads'], 54)
        self.assertEqual(result['ftp_listings'], 112)
        self.assertEqual(self.client.writes, [])
        self.assertTrue(self.client.closed)
        self.factory.assert_called_once()
        self.assertNotIn('synthetic-secret', self.report.read_text())
        self.assertEqual(json.loads(self.report.read_text()), result)

    def test_https_mismatch_or_absence_stops_before_credentials_and_ftp(self):
        for data in (None, b'changed'):
            with self.subTest(data=data), patch.object(live.publisher, 'actions_credential') as credential:
                self.report = self.fixture.root / ('missing.json' if data is None else 'changed.json')
                result = self.verify(lambda path: data)
                self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
                self.assertEqual(result['https_reads'], 1)
                self.assertEqual(result['ftp_reads'], 0)
                credential.assert_not_called()
                self.factory.assert_not_called()

    def test_ftp_drift_stops_and_never_reaches_underlying_writer(self):
        self.client.files[self.fixture.paths[-3]] = b'changed'
        result = self.verify()
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['phase'], 'unchanged_noop')
        self.assertEqual(self.client.writes, [])
        self.assertTrue(self.client.closed)

    def test_https_change_during_apply_or_final_readback_stops(self):
        for failing_read in (28, 55):
            reads = 0

            def get(path):
                nonlocal reads
                reads += 1
                return b'changed' if reads == failing_read else self.files[path]

            with self.subTest(failing_read=failing_read):
                self.report = self.fixture.root / (str(failing_read) + '.json')
                result = self.verify(get)
                self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
                self.assertEqual(result['https_reads'], failing_read)
                self.assertEqual(result['uploaded_count'], 0)
                self.assertEqual(self.client.writes, [])

    def test_tampered_manifest_stops_before_public_or_ftp_reads(self):
        with patch.object(live, 'MANIFEST_SHA', '0' * 64):
            result = self.verify()
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['https_reads'], 0)
        self.factory.assert_not_called()

    def test_read_only_adapter_denies_writers_paths_and_overread(self):
        counts = {'ftp_reads': 0, 'ftp_listings': 0}
        adapter = live.ReadOnlyFTP(self.client, self.fixture.plan, lambda: None, counts)
        for method in ('storbinary', 'mkd', 'delete', 'rename', 'rmd'):
            with self.subTest(method=method), self.assertRaises(live.publisher.Stop):
                getattr(adapter, method)('forbidden')
        with self.assertRaises(live.publisher.Stop):
            adapter.mlsd('outside')
        with self.assertRaises(live.publisher.Stop):
            adapter.retrbinary('RETR outside', lambda data: None)
        path = self.fixture.paths[0]
        self.client.files[path] += b'oversize'
        with self.assertRaises(live.publisher.Stop):
            adapter.retrbinary('RETR ' + path, lambda data: None)
        self.assertEqual(self.client.writes, [])

    def test_wrong_runtime_existing_report_and_deadline_stop(self):
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/topic'}), \
                self.assertRaises(live.publisher.Stop):
            self.verify()
        with patch.object(live.time, 'monotonic', side_effect=[0, 421]):
            result = self.verify()
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['https_reads'], 0)
        self.factory.assert_not_called()
        with self.assertRaises(ValueError):
            self.verify()

    def test_workflow_is_manual_master_only_and_retains_only_receipt(self):
        workflow = json.loads((live.ROOT / '.github/workflows/legacy-verify-unchanged.yml').read_text())
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(workflow['concurrency']['group'], 'legacy-publication')
        job = workflow['jobs']['verify']
        self.assertEqual(job['if'], "github.ref == 'refs/heads/master'")
        self.assertEqual(job['environment'], {'name': 'legacy-publish'})
        checkout, command, artifact = job['steps']
        self.assertIs(checkout['with']['persist-credentials'], False)
        self.assertEqual(checkout['with']['ref'], '${{ github.sha }}')
        self.assertIn('scripts/legacy_verify_unchanged.py', command['run'])
        self.assertNotIn('--publish-actions', command['run'])
        self.assertEqual(artifact['with']['path'], '${{ runner.temp }}/legacy-unchanged/report.json')
        self.assertNotIn('backup', json.dumps(artifact))

    def test_close_failure_keeps_an_unconfirmed_receipt_without_exception_text(self):
        self.client.close = Mock(side_effect=OSError('DO-NOT-RETAIN-synthetic-error'))
        result = self.verify()
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['phase'], 'ftps_close')
        self.assertEqual(result['uploaded_count'], 0)
        self.assertNotIn('DO-NOT-RETAIN', self.report.read_text())

    def test_final_https_response_crossing_deadline_cannot_succeed(self):
        now = [0]
        reads = 0

        def get(path):
            nonlocal reads
            reads += 1
            if reads == 81:
                now[0] = 421
            return self.files[path]

        with patch.object(live.time, 'monotonic', side_effect=lambda: now[0]):
            result = self.verify(get)
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['https_reads'], 81)
        self.assertEqual(self.client.writes, [])

    def test_stream_reads_check_deadline_during_and_after_responses(self):
        for operation in ('listing', 'empty_listing', 'retrieve'):
            check = Mock(side_effect=[None, live.publisher.Stop('synthetic deadline')])
            adapter = live.ReadOnlyFTP(self.client, self.fixture.plan, check,
                                       {'ftp_reads': 0, 'ftp_listings': 0})
            with self.subTest(operation=operation), self.assertRaises(live.publisher.Stop):
                if operation == 'retrieve':
                    adapter.retrbinary('RETR ' + self.fixture.paths[0], lambda data: None)
                else:
                    with patch.object(self.client, 'mlsd', return_value=[] if operation == 'empty_listing'
                                      else [('synthetic', {'type': 'file'})]):
                        list(adapter.mlsd('.'))
            self.assertEqual(self.client.writes, [])
