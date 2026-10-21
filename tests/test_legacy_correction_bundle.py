import json
from pathlib import Path
from pathlib import PurePosixPath
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import legacy_correction_bundle as correction
import legacy_publish as publisher


class FakeFTP:
    def __init__(self, files):
        self.files = files
        self.dirs = {'.', 'reikai', 'reikai/2026', 'reikai/2026/images_261004'}
        self.writes = []

    def mlsd(self, directory):
        dirs = [(PurePosixPath(p).name, {'type': 'dir'}) for p in self.dirs
                if p != '.' and str(PurePosixPath(p).parent) == directory]
        files = [(PurePosixPath(p).name, {'type': 'file'}) for p in self.files
                 if str(PurePosixPath(p).parent) == directory]
        return dirs + files

    def retrbinary(self, command, callback):
        callback(self.files[command[5:]])

    def storbinary(self, command, stream):
        path = command[5:]
        self.files[path] = stream.read()
        self.writes.append(path)


class CorrectionBundleTests(unittest.TestCase):
    def article(self):
        figures = []
        for n in range(1, 25):
            ext = 'jpg' if n == 1 else 'png'
            caption = f'Image {n:02d}（撮影 Before）'
            figures.append(
                f'<figure><img src="images_261004/261004_minoyama-{n:02d}.{ext}" '
                f'alt="{caption}"><figcaption>{caption}</figcaption></figure>'
            )
        return ('<html>' + ''.join(figures) + '</html>').encode('utf-8')

    def test_corrects_only_the_21_attributions_and_preserves_matching_alt(self):
        original = self.article()
        with patch.object(correction, 'OLD_ARTICLE_SHA256', correction.digest(original)):
            changed = correction.corrected_article(original).decode('utf-8')
        for n in range(1, 25):
            photographer = '栗原' if n in (1, 5, 7, 11) else '松村' if n in (22, 23, 24) else '近藤'
            self.assertIn(f'alt="Image {n:02d}（撮影 {photographer}）"', changed)
            self.assertIn(f'<figcaption>Image {n:02d}（撮影 {photographer}）</figcaption>', changed)
        self.assertEqual(changed.count('（撮影 Before）'), 0)

    def test_wrong_article_baseline_and_missing_figures_stop(self):
        self.assertRaises(ValueError, correction.corrected_article, b'<html></html>')
        article = self.article().replace(b'261004_minoyama-24.png', b'other.png')
        with patch.object(correction, 'OLD_ARTICLE_SHA256', correction.digest(article)):
            self.assertRaises(ValueError, correction.corrected_article, article)

    def test_fixed_plan_updates_article_only_and_backs_up_every_existing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / 'stage'
            baseline = root / 'baseline'
            stage.mkdir(); baseline.mkdir()
            old_article = b'old article'
            rows = []
            live = {}
            for path in correction.expected_paths():
                rel = Path(*PurePosixPath(path).parts)
                data = b'new article' if path == correction.ARTICLE else ('same:' + path).encode()
                before = publisher.digest(old_article) if path == correction.ARTICLE else publisher.digest(data)
                if path in ('index.htm', 'reikai/2026reikaihoukoku.html'):
                    out = baseline / rel; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
                out = stage / rel; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
                rows.append({'path': path, 'role': 'image' if '/images_261004/' in path else
                             'article' if path == correction.ARTICLE else
                             'annual' if path.endswith('2026reikaihoukoku.html') else 'top',
                             'before_sha256': before, 'sha256': publisher.digest(data), 'bytes': len(data)})
                live[path] = old_article if path == correction.ARTICLE else data
            manifest = {'schema_version': 1, 'operation': 'correction', 'host': publisher.HOST,
                        'remote_root': publisher.REMOTE_ROOT, 'date': '2026-10-04',
                        'legacy_year': 2026, 'legacy_slug': correction.SLUG, 'files': rows,
                        'auto_publish': False}
            raw = json.dumps(manifest, separators=(',', ':')).encode()
            (root / 'manifest.json').write_bytes(raw)
            publisher.ROOT = root
            publisher.MANIFEST_SHA = publisher.digest(raw)
            plan = publisher.load_plan()
            ftp = FakeFTP(live.copy())
            run = root / 'run'; run.mkdir()
            result = publisher.apply(ftp, plan, run, lambda path: ftp.files.get(path))
            self.assertEqual(ftp.writes, [correction.ARTICLE])
            self.assertEqual(result['uploaded'], [correction.ARTICLE])
            self.assertEqual(len(result['skipped']), 26)
            self.assertEqual(result['verified_count'], 27)
            for path, original in live.items():
                self.assertEqual((run / 'backup' / Path(*PurePosixPath(path).parts)).read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
