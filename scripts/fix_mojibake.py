"""
mojibakeファイルを個別にバックアップHTMLから再変換するスクリプト。
migrate_v4.pyのロジックを再利用し、対象ファイルのみ上書きする。
"""
import sys, re, shutil
from pathlib import Path
from bs4 import BeautifulSoup, Comment

sys.stdout.reconfigure(encoding='utf-8')

# migrate_v4.py をインポート（同じロジックを使う）
sys.path.insert(0, str(Path(__file__).parent))

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')


def detect_encoding(fp):
    with open(fp, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        with open(fp, 'rb') as f:
            f.read().decode('utf-8')
        return 'utf-8'
    except Exception:
        return 'shift_jis'


def find_html_for_md(md_stem):
    """MDファイルに対応するバックアップHTMLを探す"""
    year = md_stem[:4]
    year_dir = BACKUP / year
    if not year_dir.exists():
        return None

    parts = md_stem.split('-', 3)
    tail = parts[3] if len(parts) >= 4 else md_stem
    tail_clean = re.sub(r'[^\w]', '', tail).lower()

    html_files = sorted(
        list(year_dir.glob('*.html')) + list(year_dir.glob('*.htm')),
        key=lambda f: f.stem
    )

    def norm(s):
        return re.sub(r'[^\w]', '', s).lower()

    # 完全一致
    for hf in html_files:
        if norm(hf.stem) == tail_clean:
            return hf
    # 部分一致
    for hf in html_files:
        h = norm(hf.stem)
        if tail_clean in h or h in tail_clean:
            return hf
    # 先頭8文字
    short = tail_clean[:8]
    for hf in html_files:
        if short in norm(hf.stem):
            return hf
    return None


def get_mojibake_files():
    """mojibakeを含むMDファイルの一覧を返す"""
    result = []
    for f in sorted(OUT_CONTENT.glob('*.md')):
        text = f.read_text(encoding='utf-8')
        if '\ufffd' in text:
            result.append(f)
    return result


def reconvert_from_html(html_path, md_path):
    """HTMLから再変換してMDを上書きする（migrate_v4.pyのprocess_fileを呼び出す）"""
    # migrate_v4.pyのprocess_file関数を動的にインポート
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migrate_v4",
        Path(__file__).parent / "migrate_v4.py"
    )
    v4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v4)

    year = html_path.parent.name
    result = v4.process_file(html_path, year)
    if not result:
        return False, 'process_file returned None'

    # Verify the result has readable content (no mojibake)
    if '\ufffd' in result['content']:
        return False, 'Still has mojibake after reconversion'

    md_path.write_text(result['content'], encoding='utf-8')
    return True, f'OK ({len(result["content"])} chars)'


def main():
    mojibake_files = get_mojibake_files()
    print(f'Found {len(mojibake_files)} mojibake files')
    print()

    success = 0
    failed = 0
    not_found = 0

    # Import migrate_v4 once
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migrate_v4",
        Path(__file__).parent / "migrate_v4.py"
    )
    v4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v4)

    for md_path in mojibake_files:
        stem = md_path.stem
        html_path = find_html_for_md(stem)

        if not html_path:
            print(f'  [NO HTML] {md_path.name}')
            not_found += 1
            continue

        year = html_path.parent.name
        try:
            result = v4.process_file(html_path, year)
            if not result:
                print(f'  [FAIL]    {md_path.name} → {html_path.name} (process returned None)')
                failed += 1
                continue

            if '\ufffd' in result['content']:
                print(f'  [STILL]   {md_path.name} → {html_path.name} (still mojibake)')
                failed += 1
                continue

            # Check slug matches (prevent wrong file overwrite)
            expected_prefix = stem[:10]  # YYYY-MM-DD
            if not result['slug'].startswith(expected_prefix):
                print(f'  [MISMATCH] {md_path.name} → slug={result["slug"]}')
                # Still write if content is clean

            md_path.write_text(result['content'], encoding='utf-8')

            # Copy images
            img_dest = OUT_IMAGES / year
            img_dest.mkdir(parents=True, exist_ok=True)
            copied = v4.copy_images(html_path.parent, result['raw_srcs'], img_dest)

            print(f'  [OK]      {md_path.name} → {html_path.name} (+{copied}imgs)')
            success += 1

        except Exception as e:
            print(f'  [ERROR]   {md_path.name}: {e}')
            failed += 1

    print(f'\nSuccess: {success}, Failed: {failed}, Not found: {not_found}')


if __name__ == '__main__':
    main()
