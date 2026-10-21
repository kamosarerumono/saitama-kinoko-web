"""Build the fixed-scope Minoyama photographer correction bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from mail_draft import encoded, readback

SLUG = '261004_minoyama'
ARTICLE = 'reikai/2026/261004_minoyama.html'
OLD_ARTICLE_SHA256 = 'f0b2c26c10ef2bbe9e709abfea9920bfe19f99b8ad7e4ba0a59c297ca5851a1a'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_paths() -> list[str]:
    images = [f'reikai/2026/images_261004/261004_minoyama-{n:02d}.{"jpg" if n == 1 else "png"}'
              for n in range(1, 25)]
    return images + [ARTICLE, 'reikai/2026reikaihoukoku.html', 'index.htm']


def corrected_article(original: bytes) -> bytes:
    if digest(original) != OLD_ARTICLE_SHA256:
        raise ValueError('Original article differs from the reviewed October 19 copy')
    text = original.decode('utf-8')
    figures = list(re.finditer(r'<figure\b.*?</figure>', text, re.S))
    if len(figures) != 24:
        raise ValueError('Expected exactly 24 image figures')
    pieces = []
    offset = 0
    seen = []
    for match in figures:
        figure = match.group()
        image = re.search(r'<img\b[^>]*\bsrc="images_261004/261004_minoyama-(\d{2})\.(?:jpg|png)"[^>]*>', figure)
        if not image:
            raise ValueError('Unexpected image filename or figure structure')
        number = int(image.group(1))
        seen.append(number)
        photographer = '栗原' if number in (1, 5, 7, 11) else '松村' if number in (22, 23, 24) else '近藤'
        alt = re.search(r'\balt="([^"]+)"', image.group())
        caption = re.search(r'<figcaption>(.*?)</figcaption>', figure, re.S)
        if not alt or not caption or alt.group(1) != caption.group(1):
            raise ValueError('Image alt text and caption must match before correction')
        old_credit = re.search(r'（撮影 [^）]+）$', alt.group(1))
        if not old_credit:
            raise ValueError('Expected an existing photographer credit in alt and caption')
        new_text = alt.group(1)[:old_credit.start()] + f'（撮影 {photographer}）'
        updated = figure.replace(alt.group(1), new_text, 1).replace(caption.group(1), new_text, 1)
        if updated.count(new_text) < 2:
            raise ValueError('Could not update matching alt text and caption')
        pieces.extend((text[offset:match.start()], updated))
        offset = match.end()
    if seen != list(range(1, 25)):
        raise ValueError('Image set is not the reviewed 01–24 sequence')
    pieces.append(text[offset:])
    result = ''.join(pieces).encode('utf-8')
    if result == original:
        raise ValueError('Correction made no changes')
    return result


def prepare(stage_root: Path, output: Path) -> dict:
    expected = expected_paths()
    files = {}
    source_root = stage_root.resolve(strict=True)
    for rel in expected:
        path = source_root.joinpath(*PurePosixPath(rel).parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source_root):
            raise ValueError('Missing or unsafe original staged file: ' + rel)
        files[rel] = path.read_bytes()
    actual = {p.relative_to(source_root).as_posix() for p in source_root.rglob('*') if p.is_file()}
    if actual != set(expected):
        raise ValueError('Original stage does not contain exactly the reviewed 27 files')
    if digest(files[ARTICLE]) != OLD_ARTICLE_SHA256:
        raise ValueError('Original article differs from the reviewed October 19 copy')
    files[ARTICLE] = corrected_article(files[ARTICLE])
    rows = []
    for rel in expected:
        role = 'image' if '/images_261004/' in rel else 'article' if rel == ARTICLE else 'annual' if rel.endswith('2026reikaihoukoku.html') else 'top'
        before = OLD_ARTICLE_SHA256 if role == 'article' else digest(files[rel])
        rows.append({'path': rel, 'role': role, 'before_sha256': before,
                     'sha256': digest(files[rel]), 'bytes': len(files[rel])})
    manifest = {'schema_version': 1, 'operation': 'correction', 'host': 'ippon.sakura.ne.jp',
                'remote_root': '/home/ippon/www', 'title': '美の山キノコ観察会（2026年10月4日）報告',
                'date': '2026-10-04', 'legacy_year': 2026, 'legacy_slug': SLUG,
                'auto_publish': False, 'files': rows}
    all_files = {'stage/' + rel: data for rel, data in files.items()}
    for rel in expected[-2:]:
        all_files['baseline/' + rel] = files[rel]
    manifest_bytes = encoded(manifest)
    all_files['manifest.json'] = manifest_bytes
    all_files['PUBLISH_MINOYAMA_CORRECTION.cmd'] = (
        '@echo off\r\nchcp 65001 >nul\r\n'
        'set "PYTHONIOENCODING=utf-8"\r\n'
        '"C:\\Users\\kamos\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
        '"%~dp0..\\..\\..\\integration-worktree\\scripts\\legacy_publish.py" '
        '--bundle "%~dp0." --manifest-sha ' + digest(manifest_bytes) + ' --publish\r\n'
        'set "publish_exit=%ERRORLEVEL%"\r\necho.\r\necho Exit code: %publish_exit%\r\npause\r\nexit /b %publish_exit%\r\n'
    ).encode('utf-8')
    if output.exists():
        readback(output, all_files)
    else:
        output.mkdir(parents=True, exist_ok=False)
        for rel, data in all_files.items():
            out = output.joinpath(*PurePosixPath(rel).parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open('xb') as stream:
                stream.write(data)
        readback(output, all_files)
    return {'bundle': str(output.resolve()), 'manifest_sha256': digest(manifest_bytes),
            'target_count': len(rows), 'changed_targets': [ARTICLE], 'auto_publish': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.stage_root, args.output), ensure_ascii=False))
