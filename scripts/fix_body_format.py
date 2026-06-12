"""
本文フォーマット修正スクリプト

Phase 1: 本文の段落区切り修正
  - 「。」「！」「？」「」」「）」で終わる行の後に連続するテキスト行がある場合、
    空行（\n\n）を挿入する

Phase 2: 《フォトギャラリー》後の重複キャプション削除
  - 保護ファイルも含めて処理（保護ファイルの《フォトギャラリー》内のduplicateを削除）

対象: mojibakeのないファイルのみ（'\ufffd' を含まないファイル）
除外: 確認種/採集種/観察種セクション内のテキスト
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

# 保護ファイル（手動作成 - Phase 1 の段落修正は除外するが Phase 2 は適用）
PROTECTED = {
    '2025-04-06-250406syotukinbenkyo',
    '2025-05-18-250518_soukai',
    '2025-06-29-25629_kawagoe',
    '2025-07-21-25721_ogawa',
    '2025-09-15-25915_gunmanomori',
    '2025-10-12-251012_minoyama',
    '2025-11-03-251103_akigase',
    '2025-12-07-251207_happyoukai',
    '2026-03-15-260315_saibai',
}

# 確認種セクションのマーカー
SPECIES_MARKERS = re.compile(
    r'^(#{1,3}\s*[《【]?(確認種|採集種|観察種)[^#]*$|《確認種|《採集種|《観察種)',
    re.MULTILINE
)

# 文末文字（これで終わる行の後に空行を追加）
SENTENCE_END = re.compile(r'[。！？」』）\]）]$')

# 行の開始が「次の段落らしい」パターン
PARAGRAPH_START = re.compile(
    r'^[ぁ-ん゛゜ァ-ヴーｦ-ｯｱ-ﾟ一-龯々〆〤ヽヾゝゞ]|'  # 日本語
    r'^[A-Za-z\d]'  # 英数字
)

# テーブル/画像/見出し/HTMLなど（本文でない行）
NON_TEXT = re.compile(r'^(\|[^-]|\!\[|#+\s|<div|</div|^\s*$|\*\*|《|》|\[|---)')


def find_body_range(lines):
    """本文の開始・終了インデックスを返す（テーブル後〜確認種前）"""
    # メタデータテーブル終端を探す
    body_start = 0
    in_table = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('| 項目') or s.startswith('|---'):
            in_table = True
        elif in_table and s.startswith('|'):
            pass  # still in table
        elif in_table and not s.startswith('|'):
            body_start = i
            break
        elif not in_table and i > 0:
            # No table found, start from first non-empty after grid
            if s and not s.startswith('<') and not s.startswith('|'):
                body_start = i
                break

    # 確認種セクション開始を探す
    body_end = len(lines)
    for i, line in enumerate(lines[body_start:], body_start):
        if SPECIES_MARKERS.match(line.strip()):
            body_end = i
            break

    return body_start, body_end


def fix_paragraph_breaks(lines, body_start, body_end):
    """本文内で段落区切りが欠けている箇所に空行を挿入"""
    result = list(lines)
    inserts = []  # (index, blank_lines_count)

    for i in range(body_start, body_end - 1):
        line = result[i]
        next_line = result[i + 1]

        # 現在行が文末で終わっているか
        stripped = line.rstrip()
        if not SENTENCE_END.search(stripped):
            continue

        # 現在行がテーブル/画像/見出しでないか
        if NON_TEXT.match(line.strip()):
            continue

        # 次の行が空行でないか
        if not next_line.strip():
            continue

        # 次の行がテーブル/画像/見出しでないか
        if NON_TEXT.match(next_line.strip()):
            continue

        # 次の行が本文らしいか
        if PARAGRAPH_START.match(next_line.strip()):
            inserts.append(i + 1)

    # 後ろから挿入（インデックスがずれないように）
    for idx in reversed(inserts):
        result.insert(idx, '')

    return result, len(inserts)


def fix_gallery_duplicates(lines, grid_images):
    """《フォトギャラリー》後の重複キャプション削除"""
    result = []
    in_gallery = False
    removed = 0

    for line in lines:
        s = line.strip()

        if s == '《フォトギャラリー》':
            in_gallery = True
            result.append(line)
            continue

        if in_gallery:
            if not s:
                result.append(line)
                continue
            if s in grid_images or s == '〃':
                removed += 1
                continue
            elif (s.startswith('《') or s.startswith('#') or
                  s.startswith('|') or s.startswith('!') or
                  '。' in s or (len(s) > 4 and s not in grid_images)):
                in_gallery = False

        result.append(line)

    return result, removed


def extract_grid_images(lines):
    """画像グリッド内のaltテキスト集合を返す"""
    alts = set()
    in_grid = False
    depth = 0
    for line in lines:
        if '<div' in line:
            in_grid = True
            depth += line.count('<div') - line.count('</div>')
        elif in_grid:
            depth += line.count('<div') - line.count('</div>')
            m = re.match(r'!\[([^\]]*)\]', line)
            if m and m.group(1):
                alts.add(m.group(1).strip())
            if depth <= 0:
                in_grid = False
    return alts


def process_file(md_path, is_protected):
    text = md_path.read_text(encoding='utf-8')

    # mojibake チェック
    if '\ufffd' in text:
        return text, False, 'mojibake'

    # frontmatter 終端
    fm_end_idx = text.find('---', 3)
    if fm_end_idx < 0:
        return text, False, 'no_fm'
    fm_end_idx = text.find('\n', fm_end_idx) + 1

    fm = text[:fm_end_idx]
    body = text[fm_end_idx:]
    lines = body.split('\n')

    changed = False
    total_breaks = 0
    total_gallery = 0

    # グリッド画像を抽出（Phase 2用）
    grid_images = extract_grid_images(lines)

    # Phase 1: 段落区切り修正（保護ファイルは除外）
    if not is_protected:
        body_start, body_end = find_body_range(lines)
        lines, n_breaks = fix_paragraph_breaks(lines, body_start, body_end)
        total_breaks = n_breaks
        if n_breaks > 0:
            changed = True

    # Phase 2: 《フォトギャラリー》後の重複キャプション削除
    if grid_images and '《フォトギャラリー》' in '\n'.join(lines):
        lines, n_gallery = fix_gallery_duplicates(lines, grid_images)
        total_gallery = n_gallery
        if n_gallery > 0:
            changed = True

    if not changed:
        return text, False, 'no_change'

    new_body = '\n'.join(lines)
    # 連続空行を3つまでに制限
    new_body = re.sub(r'\n{4,}', '\n\n\n', new_body)

    return fm + new_body, True, f'+{total_breaks}breaks +{total_gallery}gallery'


def main():
    updated = 0
    skipped = 0
    errors = 0
    mojibake = 0

    for md in sorted(CONTENT.glob('*.md')):
        is_protected = md.stem in PROTECTED
        try:
            new_text, changed, info = process_file(md, is_protected)
            if info == 'mojibake':
                mojibake += 1
                continue
            if changed:
                md.write_text(new_text, encoding='utf-8')
                updated += 1
                flag = '[P]' if is_protected else '   '
                print(f'{flag} Updated: {md.name} ({info})')
            else:
                skipped += 1
        except Exception as e:
            print(f'  ERROR {md.name}: {e}')
            errors += 1

    print(f'\nUpdated: {updated}, Skipped: {skipped}, Errors: {errors}, Mojibake(skipped): {mojibake}')


if __name__ == '__main__':
    main()
