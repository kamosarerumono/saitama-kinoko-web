"""Fix species tables: extract HTML tables from original HTML and inject as markdown tables into existing md files."""
import os, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')


def detect_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        open(filepath, 'rb').read().decode('utf-8')
        return 'utf-8'
    except:
        return 'shift_jis'


def extract_species_tables(html_path):
    """Extract species/identification tables from HTML as markdown."""
    enc = detect_encoding(html_path)
    with open(html_path, 'rb') as f:
        html = f.read().decode(enc, errors='replace')

    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')

    md_tables = []
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) < 5:
            continue

        # Check if this looks like a species table (has 科名/種名 or species-like data)
        table_text = table.get_text()
        is_species = any(kw in table_text for kw in ['科', '種', 'ハラタケ', 'イグチ', 'ベニタケ', 'テングタケ', 'キクラゲ', '子嚢菌', '腹菌', 'ヒダナシタケ'])
        is_recipe = any(kw in table_text for kw in ['材料', 'レシピ', '作り方', '分量'])
        is_meta = len(rows) <= 8 and any(kw in table_text for kw in ['開催日', '報告者', '集合場所'])

        if is_meta:
            continue  # Skip metadata tables

        # Build markdown table
        md_lines = []
        current_category = None

        for row in rows:
            cells = row.find_all(['td', 'th'])
            vals = [c.get_text(strip=True) for c in cells]
            vals = [v for v in vals if v and v != 'a']  # remove empty and 'a' spacers

            if not vals:
                continue

            if len(vals) == 1:
                # Category header (e.g., "ハラタケ類　76種")
                if current_category is not None:
                    md_lines.append('')
                current_category = vals[0]
                md_lines.append(f'\n**{current_category}**\n')
                if is_species:
                    md_lines.append('| 科名 | 種名 |')
                    md_lines.append('|------|------|')
                elif is_recipe:
                    md_lines.append('| 材料 | 分量 |')
                    md_lines.append('|------|------|')
            elif len(vals) >= 2:
                # Skip header rows
                if vals[0] == '科名' and vals[1] == '種名':
                    if current_category is None:
                        md_lines.append('| 科名 | 種名 |')
                        md_lines.append('|------|------|')
                    continue
                if vals[0] == '材料':
                    continue

                col1 = vals[0]
                col2 = '、'.join(vals[1:])
                md_lines.append(f'| {col1} | {col2} |')

        if len(md_lines) > 3:
            md_tables.append('\n'.join(md_lines))

    return md_tables


def find_html_for_md(md_name):
    """Find the original HTML file for a markdown file."""
    stem = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', md_name.replace('.md', ''))
    for root, _, files in os.walk(BACKUP):
        for f in files:
            if f.endswith(('.html', '.htm')):
                f_stem = f.replace('.html', '').replace('.htm', '').replace(' ', '')
                if stem in f_stem or f_stem in stem:
                    # Verify it has tables
                    path = Path(root) / f
                    with open(path, 'rb') as fh:
                        raw = fh.read()
                    if raw.lower().count(b'<tr') >= 10:
                        return path
    return None


def has_markdown_table(content):
    """Check if markdown already has proper tables."""
    return bool(re.search(r'^\|.*\|.*\|$', content, re.MULTILINE))


def main():
    fixed = 0
    skipped = 0

    for md_file in sorted(CONTENT.glob('*.md')):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip if already has tables
        if has_markdown_table(content):
            continue

        # Find original HTML
        html_path = find_html_for_md(md_file.name)
        if not html_path:
            continue

        # Extract tables
        tables = extract_species_tables(html_path)
        if not tables:
            continue

        # Replace the species list section in markdown
        fm_match = re.search(r'^(---\n.*?\n---)\n', content, re.DOTALL)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        body = content[fm_match.end():]

        # Find where species data starts (look for category headers or inline species names)
        # Common markers: 確認種, 採集種, 同定結果, 科名, ハラタケ類
        markers = ['確認種', '採集種', '同定結果', '鑑定結果']
        insert_pos = None
        for marker in markers:
            idx = body.find(marker)
            if idx >= 0:
                # Find the end of this line
                line_end = body.find('\n', idx)
                if line_end >= 0:
                    insert_pos = line_end + 1
                break

        if insert_pos is None:
            # Try to find where the garbled table data starts
            # Look for patterns like: 科名**科名** or ハラタケ類ハラタケ類
            garbled = re.search(r'(?:科名|ハラタケ類|ヌメリガサ科|キシメジ科)', body)
            if garbled:
                insert_pos = garbled.start()

        if insert_pos is None:
            skipped += 1
            continue

        # Remove old garbled table data (everything from insert_pos to end, except reporter line)
        remaining = body[insert_pos:]
        # Keep the reporter/文責 line at the end
        reporter_match = re.search(r'(\*\*報告者[：:].*?\*\*|\*\*文責.*?\*\*)', remaining)
        reporter_line = reporter_match.group(0) if reporter_match else ''

        # Rebuild body: text before table + new tables + reporter
        new_body = body[:insert_pos] + '\n' + '\n\n'.join(tables) + '\n\n' + reporter_line + '\n'

        new_content = fm + '\n\n' + new_body.strip() + '\n'

        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print(f'  Fixed: {md_file.name}')

    print(f'\nFixed: {fixed}, Skipped: {skipped}')


if __name__ == '__main__':
    main()
