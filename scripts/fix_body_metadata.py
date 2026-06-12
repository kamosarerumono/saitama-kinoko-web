"""
本文冒頭の重複メタデータ行を削除するスクリプト。

Astroテンプレートが開催日・場所・参加者・報告者をfrontmatterから
自動表示するため、本文中の同じ情報は冗長。

削除対象:
- 日時：、場所：、参加者：、報告者：、開催日：、集合場所：、
  開催場所：、世話人：、担当 などで始まる行
- 画像ファイルサイズ表記 （XX.XKB）
"""
import re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

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

# メタデータラベルで始まる行パターン
META_LINE = re.compile(
    r'^(日時|場所|参加者|報告者|開催日|開催場所|集合場所|世話人|担当|'
    r'野草・樹木観察指導|鑑定|指導者|写真撮影|写真|記録|幹事|主催)\s*[：:・]'
)

# 画像サイズ表記 （XX.XKB） や （XXKB）
SIZE_LABEL = re.compile(r'^（\d+[\.\d]*[KMkm]?[Bb]?）$')


def fix_file(md_path):
    text = md_path.read_text(encoding='utf-8')

    # frontmatter と本文を分割
    if not text.startswith('---'):
        return False, 0
    parts = text.split('---', 2)
    if len(parts) < 3:
        return False, 0

    frontmatter = parts[1]
    body = parts[2]

    lines = body.split('\n')
    result = []
    removed = 0

    for line in lines:
        s = line.strip()

        # メタデータ行を削除
        if META_LINE.match(s):
            removed += 1
            continue

        # 画像サイズ表記を削除
        if SIZE_LABEL.match(s):
            removed += 1
            continue

        result.append(line)

    if removed == 0:
        return False, 0

    new_body = '\n'.join(result)
    new_text = f'---{frontmatter}---{new_body}'

    # 連続空行を2行に正規化
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)

    md_path.write_text(new_text, encoding='utf-8')
    return True, removed


def main():
    updated = 0
    for md in sorted(CONTENT.glob('*.md')):
        if md.stem in PROTECTED:
            continue

        changed, count = fix_file(md)
        if changed:
            updated += 1
            print(f'  Updated: {md.name} ({count} lines removed)')

    print(f'\nUpdated: {updated}')


if __name__ == '__main__':
    main()
