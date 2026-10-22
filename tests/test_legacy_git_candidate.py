import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import legacy_git_candidate as candidate
from tests import test_legacy_static_bundle as fixtures


class GitCandidateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StaticBundleTests('test_unchanged_static_source_is_noop_without_output')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo = self.fixture.root / 'git-repo'
        self.repo.mkdir()
        self.git('init', '--quiet')
        self.write(candidate.SOURCE, self.fixture.article)
        self.base = self.commit('verified static baseline')
        self.head = self.base

    def git(self, *args, data=None):
        result = subprocess.run(['git', '--no-optional-locks', '-C', str(self.repo), *args],
                                input=data, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def commit(self, message, stage=True):
        if stage:
            self.git('add', '-A')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=fixture@example.test',
                 'commit', '--no-gpg-sign', '--quiet', '-m', message)
        return self.git('rev-parse', 'HEAD').decode().strip()

    def change(self):
        data = self.fixture.article.replace(b'Current', b'Reviewed')
        self.write(candidate.SOURCE, data)
        self.head = self.commit('reviewed body edit')
        return data

    def prepare(self, **kwargs):
        f = self.fixture
        return candidate.prepare(self.repo, kwargs.get('base', self.base),
                                 kwargs.get('head', self.head), f.baseline, f.sha, f.run,
                                 kwargs.get('output', f.output),
                                 kwargs.get('review_reference', 'synthetic review'))

    def test_fixed_git_blobs_prepare_bundle_and_preserve_uncommitted_work(self):
        expected = self.change()
        self.write(candidate.SOURCE, b'UNSAVED WORKTREE CONTENT')
        before = self.git('status', '--porcelain')
        result = self.prepare()
        self.assertEqual(result['status'], 'PREPARED_OFFLINE')
        self.assertEqual(result['source_base'], self.base)
        self.assertEqual(result['source_head'], self.head)
        output = self.fixture.output
        self.assertEqual((output / 'stage' / candidate.ARTICLE).read_bytes(), expected)
        plan = candidate.static.checked_plan(output, result['manifest_sha256'])
        self.assertIn(self.base + '..' + self.head, plan['review_reference'])
        self.assertEqual((self.repo / candidate.SOURCE).read_bytes(), b'UNSAVED WORKTREE CONTENT')
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_old_archive_and_unrelated_edits_do_not_select_a_route(self):
        self.write('docs/plans/minoyama2026/261004_minoyama.html', b'old archived article')
        self.write('README.md', b'synthetic documentation')
        self.head = self.commit('unrelated and archive only')
        result = self.prepare()
        self.assertEqual(result['status'], 'NO_RELEVANT_CHANGE')
        self.assertEqual(result['ignored_change_count'], 2)
        self.assertFalse(self.fixture.output.exists())

    def adopt(self, data):
        (self.repo / candidate.SOURCE).unlink()
        self.write('README.md', b'no static article yet')
        self.base = self.commit('before static adoption')
        self.write(candidate.SOURCE, data)
        self.head = self.commit('static adoption candidate')

    def test_first_git_adoption_must_be_exact_published_bytes_and_is_noop(self):
        self.adopt(self.fixture.article)
        self.assertEqual(self.prepare()['status'], 'NO_CHANGE')
        self.assertFalse(self.fixture.output.exists())

    def test_first_adoption_cannot_also_edit_the_published_article(self):
        self.adopt(self.fixture.article.replace(b'Current', b'Reviewed'))
        with self.assertRaisesRegex(ValueError, 'First Git adoption'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_superseded_base_cannot_be_used_for_an_edit(self):
        self.write(candidate.SOURCE, b'old article')
        self.base = self.commit('superseded Git contents')
        self.change()
        with self.assertRaisesRegex(ValueError, 'Base Git blob'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_candidate_cannot_restore_known_prepublication_bytes(self):
        self.write(candidate.SOURCE, b'old article')
        self.head = self.commit('rollback attempt')
        with self.assertRaisesRegex(ValueError, 'superseded'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_protected_wire_and_flat_asset_or_navigation_changes_stop(self):
        paths = ['public/index.htm', 'public/' + self.fixture.paths[0],
                 'public/reikai/2026/' + Path(self.fixture.paths[0]).name]
        for path in paths:
            self.base = self.head
            self.write(path, b'synthetic protected edit')
            self.head = self.commit('protected change')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'fixed images or navigation'):
                self.prepare()
            self.assertFalse(self.fixture.output.exists())

    def test_article_deletion_or_rename_stops(self):
        source = self.repo / candidate.SOURCE
        source.rename(source.with_name('new-route.html'))
        self.head = self.commit('renamed article')
        with self.assertRaisesRegex(ValueError, 'Deletion, rename, or type'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_git_symlink_type_change_stops_without_creating_host_symlinks(self):
        sha = self.git('hash-object', '-w', '--stdin', data=b'../../other').decode().strip()
        self.git('update-index', '--cacheinfo', '120000,' + sha + ',' + candidate.SOURCE)
        self.head = self.commit('Git symlink object', stage=False)
        with self.assertRaisesRegex(ValueError, 'Deletion, rename, or type'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_invalid_revisions_review_and_receipt_cannot_prepare(self):
        self.change()
        for kwargs in ({'base': 'HEAD'}, {'head': '--help'}, {'base': '0' * 40},
                       {'base': self.head, 'head': self.base}, {'review_reference': ' '}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.prepare(**kwargs)
        self.fixture.receipt['verified_count'] = 26
        self.fixture.write_receipt()
        with self.assertRaisesRegex(ValueError, 'saved receipt'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_bounded_git_blob_read_stops_before_preparation(self):
        self.change()
        with patch.object(candidate, 'MAX_BYTES', 8), self.assertRaisesRegex(ValueError, 'bounded size'):
            self.prepare()
        self.assertFalse(self.fixture.output.exists())

    def test_missing_promisor_object_stops_without_lazy_fetch(self):
        # Describe an absent blob from the outset; never remove an existing object.
        sha = self.git('hash-object', '--stdin', data=b'absent synthetic body').decode().strip()
        object_path = self.repo / '.git/objects' / sha[:2] / sha[2:]
        self.assertFalse(object_path.exists())
        self.git('update-index', '--cacheinfo', '100644,' + sha + ',' + candidate.SOURCE)
        tree = self.git('write-tree', '--missing-ok').decode().strip()
        self.head = self.git('-c', 'user.name=Synthetic', '-c', 'user.email=fixture@example.test',
                             'commit-tree', tree, '-p', self.base,
                             data=b'synthetic missing blob\n').decode().strip()
        self.git('config', 'extensions.partialClone', 'origin')
        self.git('config', 'remote.origin.promisor', 'true')
        self.git('config', 'remote.origin.url', (self.fixture.root / 'absent-local-remote').as_uri())
        self.git('config', 'protocol.allow', 'never')
        trace = self.fixture.root / 'git-trace.jsonl'
        real_run = subprocess.run
        calls = []

        def guarded_run(command, **kwargs):
            # Reject an unsafe regression before launching any real Git process.
            self.assertEqual(command[:4], ['git', '--no-lazy-fetch', '--no-optional-locks',
                                          '--no-replace-objects'])
            self.assertNotIn('fetch', command)
            result = real_run(command, **kwargs)
            calls.append((command, result.returncode))
            return result

        with patch.dict('os.environ', {'GIT_TRACE2_EVENT': str(trace)}), \
                patch.object(candidate.subprocess, 'run', side_effect=guarded_run):
            with self.assertRaisesRegex(ValueError, 'Local Git read failed'):
                self.prepare()
        self.assertTrue(calls)
        self.assertEqual(calls[-1][0][-3:], ['cat-file', '-s', self.head + ':' + candidate.SOURCE])
        self.assertNotEqual(calls[-1][1], 0)
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        self.assertTrue(events)
        self.assertFalse([event for event in events if event.get('event') == 'child_start'])
        self.assertFalse(object_path.exists())
        self.assertFalse(self.fixture.output.exists())

    def test_cli_has_no_publication_mode(self):
        f = self.fixture
        command = [sys.executable, '-B', candidate.__file__, '--repo', str(self.repo),
                   '--base', self.base, '--head', self.head, '--baseline-bundle', str(f.baseline),
                   '--baseline-manifest-sha', f.sha, '--receipt-run', str(f.run),
                   '--output', str(f.output), '--review-reference', 'synthetic review']
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'NO_RELEVANT_CHANGE')
        denied = subprocess.run(command + ['--publish'], capture_output=True, timeout=20)
        self.assertEqual(denied.returncode, 2)
        self.assertFalse(f.output.exists())


class GitReadContractTests(unittest.TestCase):
    def test_git_failures_stop_after_one_guarded_call(self):
        for args, code in ((('cat-file', '-s', 'absent'), 128),
                           (('rev-parse', '--show-toplevel'), 129)):
            with self.subTest(args=args), patch.object(candidate.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], code, b'', b'failure')) as run:
                with self.assertRaisesRegex(ValueError, 'Local Git read failed'):
                    candidate.git_read(Path('unused-synthetic-repo'), *args)
                run.assert_called_once_with(
                    ['git', '--no-lazy-fetch', '--no-optional-locks', '--no-replace-objects',
                     '-C', 'unused-synthetic-repo', *args], capture_output=True, timeout=20)

    def test_launch_failures_do_not_retry_or_fall_back(self):
        for error in (FileNotFoundError('synthetic missing Git'),
                      subprocess.TimeoutExpired('synthetic Git', 20)):
            with self.subTest(error=type(error).__name__), \
                    patch.object(candidate.subprocess, 'run', side_effect=error) as run:
                with self.assertRaises(type(error)):
                    candidate.git_read(Path('unused-synthetic-repo'), 'rev-parse', 'HEAD')
                self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
