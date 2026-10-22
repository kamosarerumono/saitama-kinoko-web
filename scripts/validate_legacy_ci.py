"""Run only synthetic offline preparation tests and retain a minimal result."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_NAMES = (
    'tests.test_legacy_static_bundle.StaticBundleTests',
    'tests.test_legacy_git_candidate.GitCandidateTests',
    'tests.test_legacy_git_candidate.GitReadContractTests',
)
EXPECTED_TEST_COUNT = 27


def checked_head(expected: str) -> str:
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', expected):
        raise ValueError('A fixed full source commit is required')
    result = subprocess.run(
        ['git', '--no-lazy-fetch', '--no-optional-locks', '--no-replace-objects',
         '-C', str(ROOT), 'rev-parse', '--verify', 'HEAD'],
        capture_output=True, text=True, timeout=20)
    if result.returncode or result.stdout.strip() != expected:
        raise ValueError('Checked-out source does not match the expected commit')
    return result.stdout.strip()


def validate(expected: str, report: Path) -> dict:
    head = checked_head(expected)
    if report.exists() or report.is_symlink() or report.resolve().is_relative_to(ROOT):
        raise ValueError('Report must be new and outside the checkout')
    sys.path.insert(0, str(ROOT))
    with tempfile.TemporaryDirectory(prefix='legacy-ci-synthetic-') as scratch, \
            patch.object(tempfile, 'tempdir', scratch), \
            patch.dict('os.environ', {
                'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.allow',
                'GIT_CONFIG_VALUE_0': 'never', 'GIT_TERMINAL_PROMPT': '0',
            }), \
            patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \
            patch('socket.socket.connect_ex', side_effect=AssertionError('Network forbidden')):
        suite = unittest.defaultTestLoader.loadTestsFromNames(TEST_NAMES)
        if suite.countTestCases() != EXPECTED_TEST_COUNT:
            raise ValueError('The fixed synthetic suite changed or did not load')
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    passed = (result.wasSuccessful() and result.testsRun == EXPECTED_TEST_COUNT
              and not result.skipped)
    summary = {
        'schema_version': 1, 'scope': 'synthetic-offline-minoyama',
        'source_head': expected, 'checked_out_head': head,
        'status': 'PASS' if passed else 'FAIL', 'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped),
        'failed_test_ids': [test.id() for test, _ in result.failures + result.errors],
        'python_socket_connections': 'denied', 'git_transports': 'denied',
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, sort_keys=True)
        stream.write('\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = validate(args.expected_head, args.report)
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(2, 'Stopped: fixed source or synthetic validation contract failed.\n')
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if summary['status'] == 'PASS' else 1)
