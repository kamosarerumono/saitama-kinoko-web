"""
cp932特殊文字の文字化けを修正するスクリプト。
\ufffd + ASCII文字 のパターンを対応するcp932文字に置換する。
"""
import sys, re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

# \ufffd + 次の文字 → cp932の本来の文字
# 0x87 + 0x40〜 の範囲のcp932特殊文字
def build_mapping():
    mapping = {}
    for byte2 in range(0x40, 0xFE):
        try:
            c = bytes([0x87, byte2]).decode('cp932')
            key = '\ufffd' + chr(byte2)
            mapping[key] = c
        except Exception:
            pass
    return mapping

CHAR_MAP = build_mapping()


def fix_file(md_path):
    text = md_path.read_text(encoding='utf-8')
    if '\ufffd' not in text:
        return False

    new_text = text
    for pattern, replacement in CHAR_MAP.items():
        if pattern in new_text:
            new_text = new_text.replace(pattern, replacement)

    if new_text != text:
        md_path.write_text(new_text, encoding='utf-8')
        return True
    return False


def main():
    updated = 0
    for md in sorted(CONTENT.glob('*.md')):
        if fix_file(md):
            updated += 1
            print(f'  Fixed: {md.name}')

    print(f'\nUpdated: {updated}')


if __name__ == '__main__':
    main()
