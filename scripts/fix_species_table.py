"""
2025-06-29 の確認種一覧をMarkdownテーブルに変換
"""
from pathlib import Path
import re

MD_FILE = Path(__file__).parent.parent / 'src/content/reikai/2025-06-29-25629_kawagoe.md'

def parse_species_block(lines):
    """行リストを (目, 科, 属, 種名) のタプルリストに変換"""
    rows = []
    cur_me = ''
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.endswith('目') or line == '未定':
            cur_me = line
            i += 1
        elif line.endswith('科'):
            ka = line
            i += 1
            if i < len(lines) and (lines[i].strip().endswith('属') or lines[i].strip().endswith('属（仮）')):
                zoku = lines[i].strip()
                i += 1
                if i < len(lines) and lines[i].strip():
                    shu = lines[i].strip()
                    i += 1
                    rows.append((cur_me, ka, zoku, shu))
                else:
                    rows.append((cur_me, ka, zoku, ''))
            else:
                rows.append((cur_me, ka, '', ''))
        elif line.endswith('属') or line.endswith('属（仮）'):
            zoku = line
            i += 1
            if i < len(lines) and lines[i].strip():
                shu = lines[i].strip()
                i += 1
                rows.append((cur_me, '', zoku, shu))
            else:
                rows.append((cur_me, '', zoku, ''))
        else:
            # 種名単独（ヘッダ行 "目 科 属 種名" など）
            i += 1
    return rows


def build_md_table(rows):
    lines = ['| 目 | 科 | 属 | 種名 |', '|---|---|---|---|']
    prev_me = None
    for me, ka, zoku, shu in rows:
        display_me = me if me != prev_me else ''
        prev_me = me
        lines.append(f'| {display_me} | {ka} | {zoku} | {shu} |')
    return '\n'.join(lines)


def fix_file():
    text = MD_FILE.read_text('utf-8')

    # ===== 1) メタデータブロック修正 =====
    # 「| 項目 | 内容 |」テーブルの後の 時間/参加者/世話人/鑑定人 をテーブル行に統合
    # 現状: Markdownテーブルが終わり、その後に改行区切りのテキストがある
    # 目標: それらもMarkdownテーブルの行として組み込む

    meta_pattern = re.compile(
        r'(\| 開催場所 \| .*? \|\n)'   # 開催場所行（テーブルの最後行）
        r'(時間\n)(.*?\n)'             # 時間ラベル + 値
        r'(参加者\n)(.*?\n)'           # 参加者ラベル + 値
        r'(世話人\n)(.*?\n)'           # 世話人ラベル + 値
        r'(鑑定人\n)(.*?\n)',           # 鑑定人ラベル + 値
        re.DOTALL
    )

    def replace_meta(m):
        kaijo = m.group(1)
        jikan = m.group(3).strip()
        sankasha = m.group(5).strip()
        sewanin = m.group(7).strip()
        kanteinin = m.group(9).strip()
        return (
            kaijo +
            f'| 時間 | {jikan} |\n'
            f'| 参加者 | {sankasha} |\n'
            f'| 世話人 | {sewanin} |\n'
            f'| 鑑定人 | {kanteinin} |\n'
        )

    text2 = meta_pattern.sub(replace_meta, text)
    if text2 == text:
        print("WARNING: meta pattern not matched, trying flexible match")
        # 柔軟なパターン
        # 「時間\n」から「鑑定人\n」行までを検索
        m = re.search(r'時間\n(.+?)\n参加者\n(.+?)\n世話人\n(.+?)\n鑑定人\n(.+?)\n', text, re.DOTALL)
        if m:
            jikan = m.group(1).strip()
            sankasha = m.group(2).strip()
            sewanin = m.group(3).strip()
            kanteinin = m.group(4).strip()
            replacement = (
                f'| 時間 | {jikan} |\n'
                f'| 参加者 | {sankasha} |\n'
                f'| 世話人 | {sewanin} |\n'
                f'| 鑑定人 | {kanteinin} |\n'
            )
            text2 = text[:m.start()] + replacement + text[m.end():]
        else:
            print("ERROR: meta pattern not found at all")
            text2 = text

    # ===== 2) 確認種一覧ブロックをMarkdownテーブルに変換 =====
    species_start = text2.find('《確認種一覧')
    if species_start == -1:
        print("ERROR: 《確認種一覧 not found")
        return

    # 「目\n科\n属\n種名\n」ヘッダの後からデータ開始
    after_header = text2.find('種名\n', species_start)
    if after_header == -1:
        print("ERROR: 種名 header not found")
        return
    data_start = after_header + len('種名\n')

    # データ終端：「最後に」から始まる締めの文章の前
    data_end_match = re.search(r'\n最後に', text2[data_start:])
    if data_end_match:
        data_end = data_start + data_end_match.start()
    else:
        data_end = len(text2)

    data_block = text2[data_start:data_end]
    lines = data_block.split('\n')
    rows = parse_species_block(lines)
    print(f"Parsed {len(rows)} species rows")

    md_table = build_md_table(rows)

    # 置き換え
    new_text = (
        text2[:species_start] +
        '《確認種一覧（37種）》\n\n' +
        md_table + '\n' +
        text2[data_end:]
    )

    MD_FILE.write_text(new_text, 'utf-8')
    print(f"Done: {MD_FILE.name}")

    # 確認
    result = MD_FILE.read_text('utf-8')
    idx = result.find('《確認種一覧')
    print(result[idx:idx+400])


if __name__ == '__main__':
    fix_file()
