"""
全ページのフォーマット統一スクリプト
1. メタデータを完全なテーブルに変換（既存テーブルへの追加も含む）
2. 《フォトギャラリー》の画像名重複を削除
3. タイトル行の重複を削除
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

# 保護ファイル（手動作成）
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

# メタデータキーワード（この行が来たらメタデータ）
META_KEYS = {
    '開催日', '開催場所', '集合場所', '集合時間', '観察場所', '参加者',
    '世話人', '報告者', '報告', '鑑定人', '撮影', '観察会日時', '開催日時',
    '開催月日', '観察地', '世話人（幹事）', '幹事', '担当幹事', '参加人数',
    '主催', '講師', '昼食', '同定', '司会', '会場', '行程', '受付',
    '担当', '担当者', '問合せ', '参加費', '持参品',
}

# 確認種セクション、フォトギャラリー等のマーカー
SECTION_MARKERS = {
    '《確認種一覧》', '《フォトギャラリー》', '《採集種一覧》', '《観察種一覧》',
    '採集種一覧', '確認種一覧', '確認種', '採集種',
}


def get_frontmatter_title(text):
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    return m.group(1).strip() if m else ''


def is_title_duplicate(line, fm_title):
    if not fm_title or not line.strip():
        return False
    l = re.sub(r'[（）「」『』\s報告]', '', line.strip())
    t = re.sub(r'[（）「」『』\s報告]', '', fm_title)
    return (l == t or (len(l) > 6 and l in t) or (len(t) > 6 and t in l))


def extract_grid_block(lines, start):
    """<div class="grid..."> ブロックを探してend indexを返す"""
    if start >= len(lines) or not lines[start].startswith('<div'):
        return start
    depth = 0
    for i in range(start, len(lines)):
        line = lines[i]
        depth += line.count('<div') - line.count('</div>')
        if depth <= 0:
            return i + 1
    return len(lines)


def is_photo_alt_text(lines, start, images_in_grid):
    """
    《フォトギャラリー》の後に続く画像キャプション行かどうか判定
    images_in_grid: グリッドdivに含まれる画像のaltテキスト集合
    """
    s = lines[start].strip()
    if not s:
        return False
    # グリッド内の画像のaltテキストと一致するか
    if s in images_in_grid:
        return True
    # 〃 など
    if s in ('〃',):
        return True
    return False


def extract_grid_images(lines, grid_start, grid_end):
    """グリッドdiv内の画像altテキスト集合を返す"""
    alts = set()
    for i in range(grid_start, grid_end):
        m = re.match(r'!\[([^\]]*)\]', lines[i])
        if m and m.group(1):
            alts.add(m.group(1).strip())
    return alts


def process_file(md_path):
    text = md_path.read_text(encoding='utf-8')

    # frontmatter 終端
    fm_end_idx = text.find('---', 3)
    if fm_end_idx < 0:
        return text, False
    fm_end_idx = text.find('\n', fm_end_idx) + 1
    fm_title = get_frontmatter_title(text)

    body = text[fm_end_idx:]
    lines = body.split('\n')

    # ── Step 1: 画像グリッドの位置特定 ──────────────────────
    # 先頭空行スキップ
    cur = 0
    while cur < len(lines) and not lines[cur].strip():
        cur += 1

    grid_start = grid_end = cur
    if cur < len(lines) and lines[cur].startswith('<div'):
        grid_end = extract_grid_block(lines, cur)
        grid_images = extract_grid_images(lines, grid_start, grid_end)
    else:
        grid_images = set()

    after_grid = grid_end
    while after_grid < len(lines) and not lines[after_grid].strip():
        after_grid += 1

    # ── Step 2: 既存テーブル（メタデータ）の確認 ─────────────
    # 既にテーブルがあるか確認
    existing_table_end = after_grid
    existing_meta_keys = set()
    if after_grid < len(lines) and lines[after_grid].strip().startswith('| 項目'):
        # 既存テーブルを読み込み
        i = after_grid
        while i < len(lines) and lines[i].strip().startswith('|'):
            row = lines[i].strip()
            if not row.startswith('|---'):
                # キーを抽出
                parts = [p.strip() for p in row.strip('|').split('|')]
                if len(parts) >= 1 and parts[0] != '項目':
                    existing_meta_keys.add(parts[0])
            i += 1
        existing_table_end = i
    elif after_grid < len(lines) and lines[after_grid].strip().startswith('| ') and '|---' in '\n'.join(lines[after_grid:after_grid+3]):
        # ヘッダーなし既存テーブルもチェック
        pass

    # ── Step 3: タイトル重複行の検出・スキップ ────────────────
    cur = existing_table_end
    while cur < len(lines) and not lines[cur].strip():
        cur += 1

    # タイトル行
    title_end = cur
    if cur < len(lines) and is_title_duplicate(lines[cur], fm_title):
        title_end = cur + 1
        cur += 1
        while cur < len(lines) and not lines[cur].strip():
            cur += 1

    # ── Step 4: 追加メタデータ収集 ───────────────────────────
    additional_meta = []
    meta_scan_start = cur

    i = cur
    while i < len(lines):
        s = lines[i].strip()
        if s in META_KEYS and s not in existing_meta_keys:
            # 次の行が値
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                val = lines[j].strip()
                # 値が別のメタキーでなく、かつセクションマーカーでない
                if val not in META_KEYS and val not in SECTION_MARKERS and not val.startswith('|') and not val.startswith('#'):
                    # 値が複数行にわたる場合（次行も値の延長か確認）
                    full_val = val
                    k = j + 1
                    while k < len(lines):
                        nxt = lines[k].strip()
                        if not nxt:
                            break
                        if nxt in META_KEYS or nxt in SECTION_MARKERS or nxt.startswith('|') or nxt.startswith('#'):
                            break
                        # 次も同じ種の値（例: "9:30 受付・概要説明・園内観察"）
                        # ただし明らかに本文（句読点あり）はしない
                        if '。' in nxt or '、' in nxt and len(nxt) > 30:
                            break
                        full_val += '、' + nxt
                        k += 1
                    additional_meta.append((s, full_val))
                    existing_meta_keys.add(s)
                    i = k
                    continue
        elif s in META_KEYS and s in existing_meta_keys:
            # 既にテーブルにある → 次の値行もスキップ
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip() not in META_KEYS:
                i = j + 1
                continue
        elif not s or s.startswith('|') or s.startswith('#') or s.startswith('!') or s.startswith('<') or s.startswith('*') or s.startswith('《') or s.startswith('》') or '。' in s or ('、' in s and len(s) > 20):
            # 本文開始
            break
        i += 1

    meta_scan_end = i

    # ── Step 5: 《フォトギャラリー》後の重複画像名削除 ─────────
    # 本文内の《フォトギャラリー》マーカーを探す
    new_lines = list(lines)

    # 削除対象行を記録
    lines_to_remove = set()

    # タイトル重複行を削除
    if title_end > cur - 1:
        for li in range(cur - 1, min(title_end, len(lines))):
            if is_title_duplicate(lines[li], fm_title):
                lines_to_remove.add(li)

    # 追加メタデータ行を削除（テーブルに移動するので）
    for li in range(meta_scan_start, meta_scan_end):
        lines_to_remove.add(li)

    # 《フォトギャラリー》後の画像alt重複を削除
    in_gallery = False
    for li, line in enumerate(lines):
        s = line.strip()
        if s == '《フォトギャラリー》':
            in_gallery = True
            continue
        if in_gallery:
            if not s:
                continue
            # 画像altテキストか判定
            if s in grid_images or s == '〃':
                lines_to_remove.add(li)
            elif s.startswith('《') or s.startswith('#') or s.startswith('|') or '。' in s or (len(s) > 2 and s not in grid_images):
                in_gallery = False

    # ── Step 6: 新しいテーブル行を生成 ─────────────────────────
    if not additional_meta:
        # メタデータ追加なし、削除もなし
        if not lines_to_remove:
            return text, False

        # 削除のみ
        out = []
        for li, line in enumerate(lines):
            if li not in lines_to_remove:
                out.append(line)
        new_body = '\n'.join(out)
        new_body = re.sub(r'\n{4,}', '\n\n\n', new_body)
        return text[:fm_end_idx] + new_body, True

    # 追加メタデータをテーブルに組み込む
    # 既存テーブルがあれば末尾に追加行を挿入
    if existing_table_end > after_grid:
        # 既存テーブルの最後の行を見つけて追加
        insert_at = existing_table_end - 1
        # 空行の前の最後のテーブル行
        while insert_at > after_grid and not lines[insert_at].strip().startswith('|'):
            insert_at -= 1
        new_rows = [f'| {k} | {v} |' for k, v in additional_meta]
        lines = lines[:insert_at + 1] + new_rows + lines[insert_at + 1:]
        # 削除対象のインデックスも再調整（挿入行数分ずれる）
        shift = len(new_rows)
        lines_to_remove = {li + shift if li > insert_at else li for li in lines_to_remove}
    else:
        # 既存テーブルなし：新規テーブル作成
        table_rows = ['| 項目 | 内容 |', '|------|------|']
        table_rows += [f'| {k} | {v} |' for k, v in additional_meta]
        # after_grid 位置に挿入
        lines = lines[:after_grid] + table_rows + [''] + lines[after_grid:]
        shift = len(table_rows) + 1
        lines_to_remove = {li + shift if li >= after_grid else li for li in lines_to_remove}

    # 削除対象を除いた行でbodyを再構築
    out = []
    for li, line in enumerate(lines):
        if li not in lines_to_remove:
            out.append(line)

    new_body = '\n'.join(out)
    new_body = re.sub(r'\n{4,}', '\n\n\n', new_body)
    return text[:fm_end_idx] + new_body, True


def main():
    updated = 0
    skipped = 0
    errors = 0

    for md in sorted(CONTENT.glob('*.md')):
        if md.stem in PROTECTED:
            continue
        text = md.read_text(encoding='utf-8')

        # 処理対象: メタデータキーワードか フォトギャラリーがある
        needs_processing = any(f'\n{k}\n' in text for k in META_KEYS) or '《フォトギャラリー》' in text
        if not needs_processing:
            continue

        try:
            new_text, changed = process_file(md)
            if changed:
                md.write_text(new_text, encoding='utf-8')
                updated += 1
                print(f'  Updated: {md.name}')
            else:
                skipped += 1
        except Exception as e:
            print(f'  ERROR {md.name}: {e}')
            errors += 1

    print(f'\nUpdated: {updated}, Skipped: {skipped}, Errors: {errors}')


if __name__ == '__main__':
    main()
