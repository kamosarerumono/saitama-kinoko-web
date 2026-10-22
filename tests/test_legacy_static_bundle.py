import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from legacy_correction_bundle import ARTICLE, expected_paths
import legacy_static_bundle as static


class StaticBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline, self.source, self.run, self.output = [self.root / name for name in
                                                         ('baseline', 'static', 'run', 'output')]
        self.run.mkdir()
        self.paths = expected_paths()
        self.article = ('<html><head><style>body{color:#222}</style></head><body><a href="../../index.htm">Home</a>'
                        '<p>Current synthetic body</p>' + ''.join(
                            '<img src="images_261004/' + Path(path).name + '" alt="Synthetic">'
                            for path in self.paths[:-3]) + '</body></html>').encode()
        rows = []
        for path in self.paths:
            role = ('article' if path == ARTICLE else 'image' if '/images_261004/' in path
                    else 'top' if path == 'index.htm' else 'annual')
            data = (self.article if role == 'article' else '既存導線'.encode('cp932')
                    if role == 'top' else ('synthetic:' + path).encode())
            sha = static.digest(data)
            rows.append({'path': path, 'role': role, 'sha256': sha, 'bytes': len(data),
                         'before_sha256': static.digest(b'old article') if role == 'article' else sha})
            for target in (self.baseline / 'stage' / path, self.source / path):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            if role in ('annual', 'top'):
                target = self.baseline / 'baseline' / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        self.plan = {'schema_version': 1, 'operation': 'correction', 'host': 'ippon.sakura.ne.jp',
                     'remote_root': '/home/ippon/www', 'title': 'Synthetic', 'date': '2026-10-04',
                     'legacy_year': 2026, 'legacy_slug': '261004_minoyama',
                     'auto_publish': False, 'files': rows}
        raw = json.dumps(self.plan).encode()
        (self.baseline / 'manifest.json').write_bytes(raw)
        self.sha = static.digest(raw)
        (self.run / 'manifest.sha256').write_text(self.sha)
        self.receipt = {'status': 'PUBLICATION_VERIFIED', 'verified_count': 27,
                        'verified': self.paths, 'uploaded': [ARTICLE],
                        'skipped': [p for p in self.paths if p != ARTICLE]}
        self.write_receipt()

    def write_receipt(self):
        (self.run / 'receipt.json').write_text(json.dumps(self.receipt))

    def prepare(self, **kwargs):
        return static.prepare(self.baseline, kwargs.get('manifest_sha', self.sha), self.run,
                              self.source, kwargs.get('output', self.output),
                              kwargs.get('review_reference', 'synthetic reviewed change'))

    def change_article(self):
        (self.source / ARTICLE).write_bytes(self.article.replace(b'Current', b'Reviewed'))

    def test_unchanged_static_source_is_noop_without_output(self):
        self.assertEqual(self.prepare(), {'status': 'NO_CHANGE', 'changed_targets': [],
                                         'auto_publish': False})
        self.assertFalse(self.output.exists())

    def test_single_article_prepares_existing_publisher_format_and_preserves_inputs(self):
        self.change_article()
        source_before = (self.source / ARTICLE).read_bytes()
        manifest_before = (self.baseline / 'manifest.json').read_bytes()
        result = self.prepare()
        self.assertEqual(result['status'], 'PREPARED_OFFLINE')
        self.assertEqual(result['changed_targets'], [ARTICLE])
        plan = static.checked_plan(self.output, result['manifest_sha256'])
        article = next(r for r in plan['files'] if r['role'] == 'article')
        self.assertEqual(article['before_sha256'], static.digest(self.article))
        self.assertEqual(article['sha256'], static.digest(source_before))
        self.assertEqual(plan['baseline_manifest_sha256'], self.sha)
        self.assertFalse(plan['auto_publish'])
        self.assertEqual((self.output / 'baseline/index.htm').read_bytes(), '既存導線'.encode('cp932'))
        self.assertEqual((self.source / ARTICLE).read_bytes(), source_before)
        self.assertEqual((self.baseline / 'manifest.json').read_bytes(), manifest_before)
        self.assertFalse(list(self.output.glob('*.cmd')))

    def test_images_and_navigation_cannot_change(self):
        for path in (self.paths[0], self.paths[-2], self.paths[-1]):
            candidate = self.source / path
            original = candidate.read_bytes()
            candidate.write_bytes(original + b'changed')
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.prepare()
            candidate.write_bytes(original)
            self.assertFalse(self.output.exists())

    def test_article_resource_and_navigation_reference_changes_stop(self):
        for old, new in ((b'images_261004/', b'https://example.test/'),
                         (b'../../index.htm', b'../../other.htm')):
            (self.source / ARTICLE).write_bytes(self.article.replace(old, new))
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.output.exists())

    def test_indirect_resource_or_active_markup_changes_stop(self):
        changes = [
            self.article.replace(b'</head>', b'<meta http-equiv="refresh" content="0;url=https://example.test/"></head>'),
            self.article.replace(b'body{color:#222}', b'body{background-image:url(https://example.test/new.png)}'),
            self.article.replace(b'<body>', b'<body onload="location.href=\'https://example.test/\'">'),
            self.article.replace(b'</body>', b'<script>location.href="https://example.test/"</script></body>'),
        ]
        for number, candidate in enumerate(changes):
            output = self.root / ('rejected-' + str(number))
            (self.source / ARTICLE).write_bytes(candidate)
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    self.prepare(output=output)
                self.assertFalse(output.exists())

    def test_incomplete_or_unbound_receipts_stop(self):
        original = copy.deepcopy(self.receipt)
        for field, value in (('status', 'STOPPED_SAFELY'), ('verified_count', 26),
                             ('verified', self.paths[:-1]), ('uploaded', []),
                             ('skipped', self.paths)):
            self.receipt = dict(original, **{field: value})
            self.write_receipt()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepare()
        self.receipt = original
        self.write_receipt()
        (self.run / 'manifest.sha256').write_text('0' * 64)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_baseline_manifest_or_stage_drift_stops(self):
        with self.assertRaises(static.publisher.Stop):
            self.prepare(manifest_sha='0' * 64)
        (self.baseline / 'stage' / ARTICLE).write_bytes(b'changed')
        with self.assertRaises(static.publisher.Stop):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_missing_input_and_missing_review_stop(self):
        with self.assertRaises(ValueError):
            self.prepare(review_reference=' ')
        (self.source / self.paths[0]).unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_existing_or_nested_output_never_overwrites_inputs(self):
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_bytes(b'preserve')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(marker.read_bytes(), b'preserve')
        for root in (self.source, self.baseline, self.run):
            with self.subTest(root=root.name), self.assertRaises(ValueError):
                self.prepare(output=root / 'nested')

    def test_unlisted_files_are_not_copied(self):
        (self.source / 'not-for-publication.txt').write_bytes(b'synthetic unrelated input')
        self.change_article()
        self.prepare()
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(actual, {'manifest.json', 'baseline/index.htm',
                                 'baseline/reikai/2026reikaihoukoku.html'} |
                         {'stage/' + path for path in self.paths})

    def test_local_validation_restores_publisher_state_on_success_and_failure(self):
        before = static.publisher.ROOT, static.publisher.MANIFEST_SHA
        static.checked_plan(self.baseline, self.sha)
        self.assertEqual((static.publisher.ROOT, static.publisher.MANIFEST_SHA), before)
        with self.assertRaises(static.publisher.Stop):
            static.checked_plan(self.baseline, '0' * 64)
        self.assertEqual((static.publisher.ROOT, static.publisher.MANIFEST_SHA), before)

    def test_cli_noop_has_no_publication_mode(self):
        script = Path(static.__file__)
        command = [sys.executable, '-B', str(script), '--baseline-bundle', str(self.baseline),
                   '--baseline-manifest-sha', self.sha, '--receipt-run', str(self.run),
                   '--source-root', str(self.source), '--output', str(self.output),
                   '--review-reference', 'synthetic review']
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'NO_CHANGE')
        self.assertFalse(self.output.exists())
        denied = subprocess.run(command + ['--publish'], capture_output=True, timeout=20)
        self.assertEqual(denied.returncode, 2)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
