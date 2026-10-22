from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import legacy_verify_unchanged as live
from tests import test_legacy_live_verification as live_fixtures


class ConnectionDiagnosticsTests(unittest.TestCase):
    # Reuse only synthetic fixture helpers, without inheriting/rerunning old tests.
    setUp = live_fixtures.LiveVerificationTests.setUp
    verify = live_fixtures.LiveVerificationTests.verify

    def test_eof_identifies_attempted_call_and_existing_command_verb_only(self):
        stages = (
            ('connect', None, 'ftps_connect_banner'),
            ('auth', 'AUTH', 'ftps_auth_tls'),
            ('login', 'USER', 'ftps_login'),
            ('login', 'PASS', 'ftps_login'),
            ('login', 'ACCT', 'ftps_login'),
            ('prot_p', 'PBSZ', 'ftps_prot_p'),
            ('prot_p', 'PROT', 'ftps_prot_p'),
            ('cwd', 'CWD', 'ftps_cwd'),
        )
        calls = ('connect', 'auth', 'login', 'prot_p', 'set_pasv', 'cwd')
        original = {name: getattr(self.client, name) for name in calls}
        for index, (failing_call, verb, phase) in enumerate(stages):
            observed = []

            def track(name):
                def invoke(*args, **kwargs):
                    observed.append(name)
                    if name == failing_call:
                        self.client.last_command = verb
                        raise EOFError('DO-NOT-RETAIN synthetic-secret response/arguments')
                    return original[name](*args, **kwargs)
                return invoke

            for name in calls:
                setattr(self.client, name, track(name))
            self.report = self.fixture.root / ('eof-' + str(index) + '.json')
            output = io.StringIO()
            with self.subTest(call=failing_call, verb=verb), redirect_stdout(output), redirect_stderr(output):
                result = self.verify()
                self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
                self.assertEqual(result['phase'], phase)
                self.assertEqual(result['error_type'], 'EOFError')
                self.assertEqual(result['last_ftp_command'], verb)
                self.assertEqual(observed, list(calls[:calls.index(failing_call) + 1]))
                self.assertEqual(result['https_reads'], 27)
                self.assertEqual(result['ftp_listings'], 0)
                self.assertEqual(result['ftp_reads'], 0)
                self.assertEqual(result['uploaded_count'], 0)
                self.assertFalse(result['remote_writes_permitted'])
                self.assertEqual(self.client.writes, [])
                self.assertNotIn('verified_count', result)
                self.assertNotIn('skipped_count', result)
                self.assertNotIn('synthetic-secret', self.report.read_text() + output.getvalue())
                self.assertNotIn('DO-NOT-RETAIN', self.report.read_text() + output.getvalue())

    def test_command_arguments_unknown_values_and_missing_verb_are_not_retained(self):
        for index, value in enumerate(('PASS synthetic-secret', 'AUTH TLS', 'unrecognized', 123, None)):
            def fail(*args):
                self.client.last_command = value
                raise EOFError('DO-NOT-RETAIN synthetic-secret')

            self.client.auth = fail
            self.report = self.fixture.root / ('filtered-' + str(index) + '.json')
            with self.subTest(value=value):
                result = self.verify()
                self.assertIsNone(result['last_ftp_command'])
                self.assertEqual(result['phase'], 'ftps_auth_tls')
                self.assertNotIn('synthetic-secret', self.report.read_text())
                self.assertNotIn('DO-NOT-RETAIN', self.report.read_text())
                self.assertEqual(self.client.writes, [])

    def test_success_keeps_connection_order_and_noop_result(self):
        order = []
        for name in ('set_debuglevel', 'connect', 'auth', 'login', 'prot_p', 'set_pasv', 'cwd'):
            original = getattr(self.client, name)

            def track(*args, _name=name, _original=original, **kwargs):
                order.append(_name)
                return _original(*args, **kwargs)

            setattr(self.client, name, track)
        result = self.verify()
        self.assertEqual(order, ['set_debuglevel', 'connect', 'auth', 'login', 'prot_p', 'set_pasv', 'cwd'])
        self.assertEqual(result['status'], 'UNCHANGED_VERIFIED')
        self.assertEqual(result['verified_count'], 27)
        self.assertEqual(result['skipped_count'], 27)
        self.assertEqual(result['uploaded_count'], 0)
        self.assertEqual((result['https_reads'], result['ftp_reads'], result['ftp_listings']), (81, 54, 112))
        self.assertEqual(self.client.writes, [])

    def test_close_failure_uses_the_same_sanitized_command_field(self):
        self.client.last_command = 'CWD'
        self.client.close = Mock(side_effect=OSError('DO-NOT-RETAIN synthetic-secret'))
        result = self.verify()
        self.assertEqual(result['phase'], 'ftps_close')
        self.assertEqual(result['status'], 'STOPPED_UNCONFIRMED')
        self.assertEqual(result['last_ftp_command'], 'CWD')
        self.assertNotIn('synthetic-secret', self.report.read_text())
        self.assertNotIn('DO-NOT-RETAIN', self.report.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
