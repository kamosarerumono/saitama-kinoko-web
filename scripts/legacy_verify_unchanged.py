"""Verify the fixed published Minoyama bundle through FTPS without remote writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time

from legacy_bundle import bounded, relative_file
from legacy_correction_bundle import expected_paths
import legacy_publish as publisher
import legacy_static_bundle as static
from validate_legacy_ci import ROOT, checked_head

MANIFEST = ROOT / 'legacy-publication/verification/minoyama-manifest.json'
MANIFEST_SHA = 'cc1a623611a30f6bad31c374b4f194785e7c1af35fbf65258917282b389fadd6'


def connection_verb(client):
    value = getattr(client, 'last_command', None)
    return value if isinstance(value, str) and value in (
        'AUTH', 'USER', 'PASS', 'ACCT', 'PBSZ', 'PROT', 'CWD') else None


class ReadOnlyFTP:
    def __init__(self, client, plan, check_deadline, counts):
        self.client = client
        self.rows = {row['path']: row for row in plan['files']}
        self.check_deadline = check_deadline
        self.counts = counts

    def mlsd(self, directory):
        self.check_deadline()
        if directory not in ('.', 'reikai', 'reikai/2026', 'reikai/2026/images_261004'):
            raise publisher.Stop('Directory outside the fixed scope')
        self.counts['ftp_listings'] += 1
        if self.counts['ftp_listings'] > 112:
            raise publisher.Stop('Listing bound exceeded')
        values = self.client.mlsd(directory)

        def entries():
            for entry in values:
                self.check_deadline()
                yield entry
            self.check_deadline()

        return entries()

    def retrbinary(self, command, callback):
        self.check_deadline()
        path = command.removeprefix('RETR ')
        if command != 'RETR ' + path or path not in self.rows:
            raise publisher.Stop('Read outside the fixed scope')
        self.counts['ftp_reads'] += 1
        if self.counts['ftp_reads'] > 54:
            raise publisher.Stop('Read bound exceeded')
        chunks = []
        size = 0

        def take(data):
            nonlocal size
            self.check_deadline()
            size += len(data)
            if size > self.rows[path]['bytes']:
                raise publisher.Stop('Remote content changed')
            chunks.append(data)

        self.client.retrbinary(command, take)
        self.check_deadline()
        data = b''.join(chunks)
        row = self.rows[path]
        if len(data) != row['bytes'] or publisher.digest(data) != row['sha256']:
            raise publisher.Stop('Remote content changed')
        callback(data)

    def deny_write(self, *args, **kwargs):
        raise publisher.Stop('Remote writes are forbidden during unchanged verification')

    storbinary = mkd = delete = rename = rmd = deny_write


def verify(expected_head: str, report: Path, *, get=None, ftp_factory=None) -> dict:
    head = checked_head(expected_head)
    if report.exists() or report.is_symlink() or report.resolve().is_relative_to(ROOT):
        raise ValueError('Report must be new and outside the checkout')
    if (os.environ.get('GITHUB_ACTIONS'), os.environ.get('GITHUB_REF'),
            os.environ.get('GT030_PUBLISH_ENVIRONMENT')) != ('true', 'refs/heads/master', 'legacy-publish'):
        raise publisher.Stop('Use the existing protected master Actions environment')
    get = publisher.https_get if get is None else get
    ftp_factory = publisher.AuditedFTP_TLS if ftp_factory is None else ftp_factory
    deadline = time.monotonic() + 420
    counts = {'https_reads': 0, 'ftp_reads': 0, 'ftp_listings': 0}
    phase = 'metadata'
    client = None
    summary = {'source_head': head, 'manifest_sha256': MANIFEST_SHA,
               'remote_writes_permitted': False, 'uploaded_count': 0}

    def check_deadline():
        if time.monotonic() > deadline:
            raise publisher.Stop('Verification deadline exceeded')

    try:
        raw = bounded(MANIFEST)
        if publisher.digest(raw) != MANIFEST_SHA:
            raise publisher.Stop('Fixed manifest changed')
        plan = json.loads(raw)
        if ([row['path'] for row in plan['files']] != expected_paths()
                or plan.get('operation') != 'correction'
                or plan.get('host') != publisher.HOST or plan.get('remote_root') != publisher.REMOTE_ROOT):
            raise publisher.Stop('Fixed verification scope changed')
        rows = {row['path']: row for row in plan['files']}

        def verified_https(path):
            check_deadline()
            if path not in rows or counts['https_reads'] >= 81:
                raise publisher.Stop('HTTPS verification bound exceeded')
            counts['https_reads'] += 1
            data = get(path)
            check_deadline()
            row = rows[path]
            if data is None or len(data) != row['bytes'] or publisher.digest(data) != row['sha256']:
                raise publisher.Stop('Published content differs from the fixed candidate')
            return data

        with tempfile.TemporaryDirectory(prefix='legacy-unchanged-verification-') as scratch:
            bundle = Path(scratch) / 'bundle'
            bundle.mkdir()
            (bundle / 'manifest.json').write_bytes(raw)
            phase = 'https_snapshot'
            for row in plan['files']:
                data = verified_https(row['path'])
                for name in (['stage/' + row['path'], 'baseline/' + row['path']]
                             if row['role'] in ('annual', 'top') else ['stage/' + row['path']]):
                    path = relative_file(bundle, name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            plan = static.checked_plan(bundle, MANIFEST_SHA)
            phase = 'credential'
            password = publisher.actions_credential(os.environ)
            try:
                check_deadline()
                phase = 'ftps_setup'
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                client = ftp_factory(context=context, timeout=30)
                client.set_debuglevel(0)
                phase = 'ftps_connect_banner'
                client.connect(publisher.HOST, 21)
                phase = 'ftps_auth_tls'
                client.auth()
                phase = 'ftps_login'
                client.login(publisher.USER, password)
            finally:
                del password
            phase = 'ftps_prot_p'
            client.prot_p()
            phase = 'ftps_passive_setting'
            client.set_pasv(True)
            phase = 'ftps_cwd'
            client.cwd(publisher.REMOTE_ROOT)
            phase = 'unchanged_noop'
            run = Path(scratch) / 'run'
            run.mkdir()
            result = publisher.apply(ReadOnlyFTP(client, plan, check_deadline, counts), plan,
                                     run, verified_https)
            check_deadline()
            if result['uploaded'] or len(result['skipped']) != 27 or result['verified_count'] != 27:
                raise publisher.Stop('Unchanged verification was incomplete')
            summary.update(status='UNCHANGED_VERIFIED', skipped_count=27, verified_count=27,
                           target_count=27)
    except (Exception, KeyboardInterrupt) as error:
        summary.update(status='STOPPED_UNCONFIRMED', phase=phase, error_type=type(error).__name__,
                       last_ftp_command=connection_verb(client))
    finally:
        if client is not None:
            try:
                client.close()
                check_deadline()
            except Exception as error:
                summary.update(status='STOPPED_UNCONFIRMED', phase='ftps_close',
                               error_type=type(error).__name__, last_ftp_command=connection_verb(client))
    summary.update(counts)
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
        result = verify(args.expected_head, args.report)
    except (ValueError, OSError, publisher.Stop, subprocess.SubprocessError):
        parser.exit(2, 'Stopped: fixed source or protected runtime did not validate.\n')
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'UNCHANGED_VERIFIED' else 2)
