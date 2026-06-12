"""
Markdownファイルの冒頭メタデータブロックをテーブル形式に変換する。

対象パターン:
  （タイトル行）← 削除（frontmatterに既にある）
  開催日
  YYYY年MM月DD日（曜日）
  開催場所
  〇〇公園
  集合場所
  〇〇駐車場
  参加者
  XX名...
  世話人
  〇〇
  報告者
  〇〇
→ Markdownテーブルに変換
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

# メタデータキーワード（この行が来たらメタデータ行と判断）
META_KEYS = {
    '開催日', '開催場所', '集合場所', '参加者', '世話人', '報告者',
    '開催月日', '観察地', '世話人（幹事）', '幹事', '観察場所', '参加人数',
    '観察会日時', '開催日時', '主催', '担当幹事',
}


def get_frontmatter_title(text):
    """frontmatterからtitleを取得"""
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    return m.group(1).strip() if m else ''


def is_title_duplicate(line, fm_title):
    """lineがfrontmatterタイトルと実質同じか"""
    if not fm_title:
        return False
    l = re.sub(r'[（）「」\s]', '', line).strip()
    t = re.sub(r'[（）「」\s]', '', fm_title).strip()
    return l == t or l in t or t in l


def convert_meta_block(text):
    """冒頭メタデータを検出してテーブルに変換"""
    # frontmatter の終端を探す
    fm_end = text.find('---', 3)
    if fm_end < 0:
        return text, False
    fm_end = text.find('\n', fm_end) + 1
    fm_title = get_frontmatter_title(text)

    body = text[fm_end:]
    lines = body.split('\n')

    # 先頭の空行をスキップ
    start_idx = 0
    while start_idx < len(lines) and lines[start_idx].strip() == '':
        start_idx += 1

    if start_idx >= len(lines):
        return text, False

    # HTML divタグ（画像グリッドなど）をスキップ
    grid_end = start_idx
    if lines[start_idx].startswith('<div'):
        depth = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            depth += line.count('<div') - line.count('</div>')
            if depth <= 0:
                grid_end = i + 1
                break
        # 画像グリッド後の空行をスキップ
        while grid_end < len(lines) and lines[grid_end].strip() == '':
            grid_end += 1
        start_idx = grid_end

    if start_idx >= len(lines):
        return text, False

    # メタデータブロックの検出
    # 最初の行がタイトル重複の場合はスキップ
    cur = start_idx
    title_line_idx = None
    if cur < len(lines):
        first = lines[cur].strip()
        if first and is_title_duplicate(first, fm_title):
            title_line_idx = cur
            cur += 1
        # 空行スキップ
        while cur < len(lines) and lines[cur].strip() == '':
            cur += 1

    # メタデータペアを収集
    meta_pairs = []
    meta_start = cur
    meta_end = cur

    i = cur
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped in META_KEYS:
            # 次の行が値
            val_idx = i + 1
            # 空行をスキップ
            while val_idx < len(lines) and lines[val_idx].strip() == '':
                val_idx += 1
            if val_idx < len(lines) and lines[val_idx].strip() and lines[val_idx].strip() not in META_KEYS:
                # 値が複数行にわたる場合は最初の1行のみ
                val = lines[val_idx].strip()
                meta_pairs.append((stripped, val))
                meta_end = val_idx + 1
                i = val_idx + 1
            else:
                break
        elif stripped == '' and meta_pairs:
            # 空行はスキップして続行
            i += 1
        else:
            break

    if not meta_pairs:
        return text, False

    # テーブルを生成
    table_lines = ['| 項目 | 内容 |', '|------|------|']
    for key, val in meta_pairs:
        table_lines.append(f'| {key} | {val} |')
    table_md = '\n'.join(table_lines) + '\n'

    # 元の本文を再構築
    new_body_parts = []
    # 画像グリッドがあれば保持
    if grid_end > start_idx:
        new_body_parts.append('\n'.join(lines[0:grid_end]))
    else:
        # start_idx前の空行を保持
        new_body_parts.append('\n'.join(lines[0:start_idx]))

    # タイトル行は削除（frontmatterに既にある）
    # メタデータテーブル
    new_body_parts.append('')
    new_body_parts.append(table_md)

    # 残りの本文
    remaining = '\n'.join(lines[meta_end:])
    # 先頭空行を整理
    remaining = remaining.lstrip('\n')
    new_body_parts.append(remaining)

    new_body = '\n'.join(new_body_parts)
    # 連続空行を2つまでに制限
    new_body = re.sub(r'\n{4,}', '\n\n\n', new_body)

    new_text = text[:fm_end] + new_body
    return new_text, True


def main():
    updated = 0
    skipped = 0
    for md in sorted(CONTENT.glob('*.md')):
        text = md.read_text(encoding='utf-8')
        if '\n開催日\n' not in text and '開催月日' not in text and '開催日時' not in text:
            continue

        new_text, changed = convert_meta_block(text)
        if changed:
            md.write_text(new_text, encoding='utf-8')
            updated += 1
            print(f'  Updated: {md.name}')
        else:
            skipped += 1

    print(f'\nUpdated: {updated}, Skipped: {skipped}')


if __name__ == '__main__':
    main()
