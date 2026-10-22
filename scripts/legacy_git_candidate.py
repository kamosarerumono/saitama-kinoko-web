"""Select fixed Git blobs for offline Minoyama preparation; never publish."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from legacy_bundle import MAX_BYTES, bounded, relative_file
from legacy_correction_bundle import ARTICLE, expected_paths
import legacy_static_bundle as static

SOURCE = 'public/' + ARTICLE
PROTECTED = {'public/' + path for path in expected_paths() if path != ARTICLE}
PROTECTED |= {'public/reikai/2026/' + PurePosixPath(path).name
              for path in expected_paths()[:-3]}


def git_read(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '--no-lazy-fetch', '--no-optional-locks', '--no-replace-objects',
                             '-C', str(repo), *args], capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError('Local Git read failed; no alternative or retry was attempted')
    return result.stdout


def blob(repo: Path, commit: str) -> bytes:
    entry = git_read(repo, 'ls-tree', '-z', commit, '--', SOURCE)
    if not entry or entry.split(b' ', 1)[0] not in (b'100644', b'100755'):
        raise ValueError('The article must be a regular Git blob')
    object_name = commit + ':' + SOURCE
    size = int(git_read(repo, 'cat-file', '-s', object_name))
    if not 0 < size <= MAX_BYTES:
        raise ValueError('Article blob exceeds the bounded size')
    return git_read(repo, 'cat-file', 'blob', object_name)


def prepare(repo: Path, base: str, head: str, baseline: Path, manifest_sha: str,
            run: Path, output: Path, review_reference: str) -> dict:
    if any(not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', rev) for rev in (base, head)):
        raise ValueError('Base and head must be fixed full commit IDs')
    if not review_reference.strip():
        raise ValueError('A reviewed change reference is required')
    if output.exists() or output.is_symlink():
        raise ValueError('Output must be new')
    top = Path(git_read(repo, 'rev-parse', '--show-toplevel').decode().strip())
    if top.resolve() != repo.resolve():
        raise ValueError('Use the repository top-level directory')
    for rev in (base, head):
        git_read(repo, 'rev-parse', '--verify', rev + '^{commit}')
    git_read(repo, 'merge-base', '--is-ancestor', base, head)
    raw = git_read(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames',
                   '--name-status', '-z', base, head)
    fields = raw.split(b'\0')
    if fields[-1] != b'' or len(fields) % 2 != 1:
        raise ValueError('Unexpected Git diff record format')
    changes = [(fields[i].decode('ascii'), fields[i + 1].decode('utf-8'))
               for i in range(0, len(fields) - 1, 2)]
    if any(path in PROTECTED for _, path in changes):
        raise ValueError('Git changes to fixed images or navigation are outside this contract')
    selected = [status for status, path in changes if path == SOURCE]
    identity = {'source_base': base, 'source_head': head, 'auto_publish': False}
    if not selected:
        return dict(identity, status='NO_RELEVANT_CHANGE', changed_targets=[],
                    ignored_change_count=len(changes))
    if len(selected) != 1 or selected[0] not in ('A', 'M'):
        raise ValueError('Deletion, rename, or type changes of the article are not supported')
    plan = static.checked_plan(baseline, manifest_sha)
    static.verified_receipt(run, manifest_sha, {row['path'] for row in plan['files']})
    article = next(row for row in plan['files'] if row['path'] == ARTICLE)
    candidate = blob(repo, head)
    if selected[0] == 'A':
        if static.digest(candidate) != article['sha256']:
            raise ValueError('First Git adoption must match the verified published article exactly')
    elif static.digest(blob(repo, base)) != article['sha256']:
        raise ValueError('Base Git blob does not match the verified post-publication baseline')
    if static.digest(candidate) == article['before_sha256']:
        raise ValueError('Candidate restores the superseded pre-publication article')
    with tempfile.TemporaryDirectory(prefix='legacy-git-candidate-') as scratch:
        source = Path(scratch)
        for row in plan['files']:
            path = row['path']
            data = candidate if path == ARTICLE else bounded(relative_file(baseline, 'stage/' + path))
            target = relative_file(source, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
        reference = review_reference + ' [Git ' + base + '..' + head + '; ' + SOURCE + ']'
        result = static.prepare(baseline, manifest_sha, run, source, output, reference)
    return dict(result, **identity, ignored_change_count=len(changes) - 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--baseline-bundle', type=Path, required=True)
    parser.add_argument('--baseline-manifest-sha', required=True)
    parser.add_argument('--receipt-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-reference', required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.repo, args.base, args.head, args.baseline_bundle,
                         args.baseline_manifest_sha, args.receipt_run, args.output,
                         args.review_reference)
    except (ValueError, OSError, static.publisher.Stop, KeyError, TypeError,
            UnicodeError, subprocess.SubprocessError):
        parser.exit(2, 'Stopped: fixed Git input or local bundle contract did not validate.\n')
    print(json.dumps(result, ensure_ascii=False))
