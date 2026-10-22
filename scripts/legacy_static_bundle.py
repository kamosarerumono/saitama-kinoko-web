"""Prepare an offline Minoyama correction from a verified static baseline."""
from __future__ import annotations

import argparse
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from legacy_bundle import bounded, relative_file
from legacy_correction_bundle import ARTICLE
import legacy_publish as publisher
from mail_draft import encoded, readback


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_plan(bundle: Path, manifest_sha: str) -> dict:
    """Use only the publisher's local manifest checks; restore its globals."""
    if not re.fullmatch(r'[0-9a-f]{64}', manifest_sha):
        raise ValueError('A fixed baseline manifest SHA-256 is required')
    previous = publisher.ROOT, publisher.MANIFEST_SHA
    try:
        publisher.ROOT, publisher.MANIFEST_SHA = bundle, manifest_sha
        plan = publisher.load_plan()
    finally:
        publisher.ROOT, publisher.MANIFEST_SHA = previous
    if plan.get('operation') != 'correction':
        raise ValueError('Only the existing fixed Minoyama correction is supported')
    return plan


def verified_receipt(run: Path, manifest_sha: str, paths: set[str]) -> None:
    identity = bounded(relative_file(run, 'manifest.sha256')).decode('ascii').strip()
    receipt = json.loads(bounded(relative_file(run, 'receipt.json')))
    verified = receipt.get('verified', [])
    uploaded, skipped = receipt.get('uploaded', []), receipt.get('skipped', [])
    if (identity != manifest_sha or receipt.get('status') != 'PUBLICATION_VERIFIED'
            or receipt.get('verified_count') != len(paths)
            or len(verified) != len(paths) or set(verified) != paths
            or len(uploaded) + len(skipped) != len(paths)
            or set(uploaded) & set(skipped) or set(uploaded + skipped) != paths):
        raise ValueError('The saved receipt does not verify this complete manifest')


class StaticStructure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []
        self.protected_tag = None

    def handle_starttag(self, tag, attrs):
        self.values.append(('start', tag, tuple(attrs)))
        if tag in {'style', 'script'}:
            self.protected_tag = tag

    def handle_startendtag(self, tag, attrs):
        self.values.append(('empty', tag, tuple(attrs)))

    def handle_endtag(self, tag):
        self.values.append(('end', tag))
        if tag == self.protected_tag:
            self.protected_tag = None

    def handle_data(self, data):
        if self.protected_tag:
            self.values.append(('protected', self.protected_tag, data))

    def handle_comment(self, data):
        self.values.append(('comment', data))

    def handle_decl(self, decl):
        self.values.append(('declaration', decl))

    def handle_pi(self, data):
        self.values.append(('processing', data))


def structure(data: bytes) -> list[tuple]:
    parser = StaticStructure()
    parser.feed(data.decode('utf-8'))
    parser.close()
    return parser.values


def prepare(baseline: Path, manifest_sha: str, run: Path, source: Path,
            output: Path, review_reference: str) -> dict:
    if not review_reference.strip():
        raise ValueError('An explicit reviewed change reference is required')
    for root in (baseline, run, source):
        if root.is_symlink() or not root.is_dir():
            raise ValueError('An existing regular input directory is required')
    if output.exists() or output.is_symlink():
        raise ValueError('Output must be new; existing files are never overwritten')
    output_path = output.resolve()
    if any(output_path.is_relative_to(root.resolve()) for root in (baseline, run, source)):
        raise ValueError('Output must be outside all input directories')
    plan = checked_plan(baseline, manifest_sha)
    paths = {row['path'] for row in plan['files']}
    verified_receipt(run, manifest_sha, paths)
    result = copy.deepcopy(plan)
    result['review_reference'] = review_reference
    result['baseline_manifest_sha256'] = manifest_sha
    files = {}
    changed = []
    for row in result['files']:
        path = row['path']
        original = bounded(relative_file(baseline, 'stage/' + path))
        candidate = bounded(relative_file(source, path))
        if row['role'] != 'article' and candidate != original:
            raise ValueError('Static correction cannot change images or navigation')
        if row['role'] == 'article' and structure(candidate) != structure(original):
            raise ValueError('Article structure, attributes, and active content must remain unchanged')
        if candidate != original:
            changed.append(path)
        row.update(before_sha256=digest(original), sha256=digest(candidate), bytes=len(candidate))
        files['stage/' + path] = candidate
        if row['role'] in ('annual', 'top'):
            files['baseline/' + path] = original
    if not changed:
        return {'status': 'NO_CHANGE', 'changed_targets': [], 'auto_publish': False}
    if changed != [ARTICLE]:
        raise ValueError('Only the fixed existing article may change')
    manifest_bytes = encoded(result)
    files['manifest.json'] = manifest_bytes
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = relative_file(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    readback(output, files)
    checked_plan(output, digest(manifest_bytes))
    return {'status': 'PREPARED_OFFLINE', 'manifest_sha256': digest(manifest_bytes),
            'target_count': len(paths), 'changed_targets': changed, 'auto_publish': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-bundle', type=Path, required=True)
    parser.add_argument('--baseline-manifest-sha', required=True)
    parser.add_argument('--receipt-run', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-reference', required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.baseline_bundle, args.baseline_manifest_sha, args.receipt_run,
                         args.source_root, args.output, args.review_reference)
    except (ValueError, OSError, publisher.Stop, KeyError, TypeError, UnicodeError):
        parser.exit(2, 'Stopped: local baseline, receipt, scope, or candidate did not validate.\n')
    print(json.dumps(result, ensure_ascii=False))
