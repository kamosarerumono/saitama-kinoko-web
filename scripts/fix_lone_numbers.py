"""
単独行の数字を前後のテキストと結合するスクリプト。

元のHTMLで <b>30</b>周年 のようなフォント装飾が
変換時に 30\n周年 になってしまったケースを修正する。

ルール:
- 数字のみの行（\d+）の前後が本文テキスト行である場合、
  数字を前の行に結合する（スペースなし）
- ただし数字がテーブル行・画像行・見出し行の隣にある場合はスキップ
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

# テーブル・画像・見出し等の非テキスト行
NON_TEXT = re.compile(r'^(\||\!|#+|<|---|\*\*|《|》|$)')


def is_text_line(line):
    s = line.strip()
    if not s:
        return False
    return not NON_TEXT.match(s)


def fix_lone_numbers(text):
    lines = text.split('\n')
    result = []
    i = 0
    changes = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 数字のみの行か？
        if re.match(r'^\d+$', stripped) and stripped:
            prev_line = result[-1] if result else ''
            next_line = lines[i + 1] if i + 1 < len(lines) else ''

            prev_text = is_text_line(prev_line)
            next_text = is_text_line(next_line)

            # 前の行がテキストで、次の行もテキストかつ数字で始まらない場合
            if prev_text and next_text:
                # 前の行の末尾に数字と次行を付ける（30\n周年 → 30周年）
                result[-1] = result[-1].rstrip() + stripped + next_line.strip()
                changes += 1
                i += 2  # skip number line AND next line
                continue
            # 前の行がテキストで次が空行の場合（数字が文末の一部）
            elif prev_text and not next_line.strip():
                result[-1] = result[-1].rstrip() + stripped
                changes += 1
                i += 1
                continue

        # パターン2: 行末が数字で終わり、次行が日本語テキストで継続している場合
        # 例: 「今回の30\n周年記念講座」→「今回の30周年記念講座」
        if (is_text_line(line) and re.search(r'\d+$', stripped) and
                i + 1 < len(lines) and is_text_line(lines[i + 1])):
            next_s = lines[i + 1].strip()
            # 次行が文章の継続（句読点や括弧で始まらない日本語）
            if (next_s and
                    not next_s[0] in '。、！？」』）】」…' and
                    not re.match(r'^[①-⑩A-Za-z\d【《]', next_s)):
                result.append(line.rstrip() + next_s)
                changes += 1
                i += 2
                continue

        result.append(line)
        i += 1

    return '\n'.join(result), changes


def main():
    updated = 0
    for md in sorted(CONTENT.glob('*.md')):
        if md.stem in PROTECTED:
            continue

        text = md.read_text(encoding='utf-8')
        new_text, changes = fix_lone_numbers(text)

        if changes > 0:
            md.write_text(new_text, encoding='utf-8')
            updated += 1
            print(f'  Updated: {md.name} ({changes} merges)')

    print(f'\nUpdated: {updated}')


if __name__ == '__main__':
    main()
