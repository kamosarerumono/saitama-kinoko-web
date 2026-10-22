import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_legacy_ci as validation


class ValidationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='legacy-ci-contract-')
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / 'report.json'
        self.head = 'a' * 40

    def invoke(self, test):
        suite = unittest.TestSuite([unittest.FunctionTestCase(test)])
        with patch.object(validation, 'checked_head', return_value=self.head), \
                patch.object(validation, 'EXPECTED_TEST_COUNT', 1), \
                patch.object(validation.unittest.defaultTestLoader, 'loadTestsFromNames',
                             return_value=suite):
            return validation.validate(self.head, self.report)

    def test_network_guards_source_identity_and_minimal_report(self):
        old_count = os.environ.get('GIT_CONFIG_COUNT')

        def guarded():
            self.assertEqual(os.environ['GIT_CONFIG_VALUE_0'], 'never')
            self.assertEqual(os.environ['GIT_CONFIG_KEY_0'], 'protocol.allow')
            self.assertEqual(os.environ['GIT_CONFIG_COUNT'], '1')
            with socket.socket() as connection, self.assertRaisesRegex(AssertionError, 'Network forbidden'):
                connection.connect(('127.0.0.1', 1))

        summary = self.invoke(guarded)
        self.assertEqual(summary['status'], 'PASS')
        self.assertEqual(summary['source_head'], self.head)
        self.assertEqual(summary['checked_out_head'], self.head)
        self.assertEqual(json.loads(self.report.read_text()), summary)
        self.assertEqual(os.environ.get('GIT_CONFIG_COUNT'), old_count)

    def test_failure_report_does_not_retain_exception_text(self):
        def failing():
            raise AssertionError('DO-NOT-RETAIN-synthetic-exception')

        summary = self.invoke(failing)
        self.assertEqual(summary['status'], 'FAIL')
        self.assertEqual(summary['failures'], 1)
        self.assertNotIn('DO-NOT-RETAIN', self.report.read_text())
        self.assertNotIn(self.temp.name, self.report.read_text())

    def test_missing_tests_stop_without_a_report(self):
        with patch.object(validation, 'checked_head', return_value=self.head), \
                patch.object(validation.unittest.defaultTestLoader, 'loadTestsFromNames',
                             return_value=unittest.TestSuite()), \
                self.assertRaisesRegex(ValueError, 'suite changed'):
            validation.validate(self.head, self.report)
        self.assertFalse(self.report.exists())

    def test_wrong_source_and_git_errors_stop_without_retry(self):
        with patch.object(validation.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                validation.checked_head('HEAD')
            run.assert_not_called()
            for code, stdout in ((0, 'b' * 40), (128, self.head), (129, '')):
                run.reset_mock()
                run.return_value = subprocess.CompletedProcess([], code, stdout, 'synthetic error')
                with self.assertRaises(ValueError):
                    validation.checked_head(self.head)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][1:4],
                                 ['--no-lazy-fetch', '--no-optional-locks', '--no-replace-objects'])

    def test_existing_or_checkout_report_is_not_overwritten(self):
        self.report.write_text('preserved')
        with patch.object(validation, 'checked_head', return_value=self.head):
            for report in (self.report, validation.ROOT / 'synthetic-report-forbidden.json'):
                with self.subTest(report=report), self.assertRaises(ValueError):
                    validation.validate(self.head, report)
        self.assertEqual(self.report.read_text(), 'preserved')

    def test_workflow_is_pr_only_read_only_and_has_no_publication_job(self):
        workflow = json.loads((validation.ROOT / '.github/workflows/legacy-validate.yml').read_text())
        self.assertEqual(set(workflow['on']), {'pull_request'})
        self.assertEqual(workflow['on']['pull_request']['branches'], ['master'])
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(set(workflow['jobs']), {'synthetic'})
        job = workflow['jobs']['synthetic']
        self.assertEqual(job['runs-on'], 'ubuntu-24.04')
        self.assertLessEqual(job['timeout-minutes'], 5)
        self.assertIn('pull_request.number == 12', job['if'])
        self.assertNotIn('environment', job)
        checkout, run, artifact = job['steps']
        self.assertEqual(checkout['with']['ref'], '${{ github.event.pull_request.head.sha }}')
        self.assertIs(checkout['with']['persist-credentials'], False)
        self.assertIn('scripts/validate_legacy_ci.py', run['run'])
        self.assertEqual(artifact['with']['path'], '${{ runner.temp }}/legacy-validation/report.json')
        self.assertEqual(artifact['with']['retention-days'], 1)
        for forbidden in ('secrets.', 'publish-actions', 'workflow_dispatch', 'pull_request_target',
                          'legacy-publish.yml', 'legacy-publication/bundles', 'pip install', 'npm '):
            self.assertNotIn(forbidden, json.dumps(workflow))


if __name__ == '__main__':
    unittest.main(verbosity=2)
