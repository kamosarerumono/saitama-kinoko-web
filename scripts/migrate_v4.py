"""V4 migration: global dedup + robust species table extraction.

Key improvement over v3:
- pass1: GLOBAL seen-set dedup (not just consecutive) eliminates multi-column duplicates
- pass2: scan all cells across all rows (not just row-by-row) for species tables
- Image paths: spaces → underscores in references
- Protect 2025-2026 manually crafted files
"""
import os, re, sys, shutil
from pathlib import Path
from bs4 import BeautifulSoup, Comment

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')

# Files to protect (not overwrite) — manually crafted 2025-2026 reports
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

PLACE_MAP = {
    'kawagoe': '川越観察会', 'minoyama': '美の山公園観察会', 'ogawa': '小川観察会',
    'akigase': '秋ヶ瀬公園観察会', 'tumagoi': '嬬恋観察会', 'soukai': '定期総会',
    'sinnenkai': '新年会', 'sinnennkai': '新年会', 'kouenkai': '講演会',
    'kouennkai': '講演会', 'projecter': 'プロジェクター発表会',
    'projector': 'プロジェクター発表会', 'suraido': 'スライド発表会',
    'saibai': 'きのこ栽培勉強会', 'syokkinn': '植菌勉強会', 'syokukin': '植菌勉強会',
    'syotukin': '植菌勉強会', 'benkyoukai': '勉強会', 'benkyouk': '勉強会',
    'kennbikyou': '顕微鏡勉強会', 'happyoub': '発表・勉強会', 'hapyoube': '発表・勉強会',
    'kansatu': '観察会', 'nasu': '那須観察会', 'siga': '志賀高原観察会',
    'fuji': '富士山観察会', 'fujisan': '富士山観察会', 'myokou': '妙高高原観察会',
    'nozawa': '野沢温泉観察会', 'hotaka': '穂高観察会', 'hodaka': '穂高観察会',
    'gunma': '群馬の森観察会', 'gunnma': '群馬の森観察会',
    'saitamafore': '埼玉フォレスト観察会', 'sinnrinnkouenn': '森林公園観察会',
    'okushiga': '奥志賀観察会', 'shirakaba': '白樺湖観察会',
    'chichibu': '秩父観察会', 'mizugaki': '瑞牆山観察会', 'kurumayama': '車山観察会',
    'kakisyukuhaku': '夏期宿泊観察会', 'sarugakyou': '猿ヶ京観察会',
    'ryourikyousitu': '料理教室', 'kawagoetiku': '川越地区観察会',
    'asamayama': '浅間山観察会', 'tatesina': '蓼科観察会', 'asiyasu': '芦安観察会',
}

# Species-related keywords to strip from body text (handled via species table)
SPECIES_KW = {
    '五分類群', '新目名', '新科名', '種名', '科名',
    'ハラタケ目', 'タマチョレイタケ目', 'ベニタケ目', 'スッポンタケ目',
    'キクラゲ目', 'タバコウロコタケ目', 'ヒメツチグリ目', 'クロサイワイタケ目',
    'チャワンタケ目', 'イボタケ目', 'ヒダナシタケ類', 'ハラタケ類', '子嚢菌類',
    'キクラゲ類', '腹菌類',
}

# Navigation / junk to skip
SKIP_LINES = {
    'HOME', 'もどる', 'a', 'CONTENTS', 'TOP', 'トップ',
    '2025年度例会報告一覧へ', '2024年度例会報告一覧へ',
    '前のページへ', '次のページへ', '印刷',
}


def detect_encoding(fp):
    with open(fp, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        open(fp, 'rb').read().decode('utf-8')
        return 'utf-8'
    except Exception:
        return 'cp932'


def read_html(fp):
    enc = detect_encoding(fp)
    with open(fp, 'rb') as f:
        return f.read().decode(enc, errors='replace')


def clean_soup(soup):
    for tag in soup.find_all(['style', 'script']):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for tag in soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k not in ('style', 'class', 'id', 'width', 'height', 'bgcolor', 'align', 'valign', 'cellpadding', 'cellspacing', 'border')}


def extract_meta(soup, filename):
    meta = {'reporter': '不明', 'title': ''}
    body_text = soup.get_text()

    for h in soup.find_all(['h2', 'h3', 'h1']):
        t = h.get_text(strip=True)
        if t and len(t) > 3 and t not in ('CONTENTS', 'HOME', 'a'):
            meta['title'] = t
            break
    if not meta['title']:
        tt = soup.find('title')
        if tt:
            t = tt.get_text(strip=True)
            if t and len(t) > 3 and not re.match(r'^[\da-z_]+$', t, re.I):
                meta['title'] = t

    for pat in [r'報告者[）)：:　\s</b>]+([^\s<]{2,15})', r'報告[）)：:　\s]+([^\s<]{2,15})', r'文責[：:　\s]+([^\s<]{2,15})']:
        m = re.search(pat, body_text)
        if m:
            meta['reporter'] = m.group(1).strip()
            break

    for pat in [r'(?:開催場所|観察地域|集合場所)[）)：:　\s</b>]+([^\n]{2,40})']:
        m = re.search(pat, body_text)
        if m:
            meta['location'] = m.group(1).strip()[:50]
            break

    m = re.search(r'参加者[）)：:　\s</b>]+(\d+)', body_text)
    if m:
        meta['participants'] = int(m.group(1))

    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', body_text)
    if m:
        meta['date'] = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

    return meta


def pass1_extract_text(soup):
    """Pass 1: Extract body text with GLOBAL deduplication.

    Key fix over v3: uses a seen SET for all lines, not just consecutive.
    This eliminates the multi-column TABLE layout duplication where the same
    text appears in 2+ columns of the same row.
    """
    body = soup.find('body')
    if not body:
        return ''

    raw = body.get_text(separator='\n')
    lines = raw.split('\n')

    seen = set()
    deduped = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in SKIP_LINES:
            continue
        # Skip very short strings (1 char, likely nav artifacts)
        if len(stripped) <= 1:
            continue

        # GLOBAL dedup: skip if already seen
        # Exception: allow short labels like "開催日" etc. to repeat if meaningful
        # Only globally dedup lines with 5+ chars (species names, prose sentences)
        if len(stripped) >= 5 and stripped in seen:
            continue

        seen.add(stripped)
        deduped.append(stripped)

    text = '\n'.join(deduped)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\*\*\s*\*\*', '', text)
    return text.strip()


def pass2_extract_tables(soup, year_str):
    """Pass 2: Extract species tables as markdown.

    Key fix over v3: scans ALL cells (not just row-per-row structure)
    to handle HTML where entire table is in one row with 200+ cells.
    """
    body = soup.find('body')
    if not body:
        return []

    tables_md = []

    for table in body.find_all('table'):
        # Collect all cell texts from this table
        all_cells = []
        for td in table.find_all(['td', 'th']):
            t = td.get_text(strip=True)
            if t and t not in ('a', '\xa0', ''):
                all_cells.append(t)

        if not all_cells:
            continue

        # Skip tables where any cell is a huge blob (entire article in one cell)
        # These are the layout tables, not the species tables
        if any(len(c) > 200 for c in all_cells):
            continue

        # Check if this table has species data
        cell_set = set(all_cells)
        has_species_header = any(h in cell_set for h in ('五分類群', '科名', '新目名', '新科名'))
        has_species_data = any(kw in cell_set for kw in ('ハラタケ目', 'タマチョレイタケ目', 'ベニタケ目', 'キクラゲ目'))

        if not (has_species_header or has_species_data):
            continue

        # Try to extract as structured table
        # First attempt: standard multi-row structure
        rows = table.find_all('tr')
        structured_rows = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            vals = [c.get_text(strip=True) for c in cells]
            vals = [v for v in vals if v and v not in ('a', '\xa0')]
            if vals:
                structured_rows.append(vals)

        # If the table looks like a proper 4-col or 2-col table
        # (not the 225-cell-per-row mess), use structured approach
        proper_structure = all(len(r) <= 10 for r in structured_rows) if structured_rows else False

        if proper_structure and len(structured_rows) >= 5:
            md_lines = _build_species_md_structured(structured_rows)
        else:
            # Flat cell scan approach for complex/broken table structure
            md_lines = _build_species_md_flat(all_cells)

        if len(md_lines) > 3:
            tables_md.append('\n'.join(md_lines))

    return tables_md


GROUP_MARKERS = {'ハラタケ類', 'ヒダナシタケ類', '腹菌類', 'キクラゲ類', '子嚢菌類'}


def _build_species_md_structured(rows):
    """Build species markdown table from properly structured rows.

    Handles two main formats:
    - 4-col: 五分類群(group), 新目名(order), 新科名(family), 種名(species)
    - 3-col: 新目名(order), 新科名(family), 種名(species)  [group merged/absent]
    - 2-col: 科名(family), 種名(species)
    - 1-col: group header or species name
    """
    md_lines = []
    current_group = None

    for vals in rows:
        if not vals:
            continue
        # Skip header rows
        if vals[0] in ('五分類群', '科名', '新目名', '新科名', '種名'):
            continue

        if len(vals) >= 4 and vals[0] in GROUP_MARKERS:
            # 4-col: group, order, family, species
            group, order, family = vals[0], vals[1], vals[2]
            species = '、'.join(vals[3:]) if len(vals) > 3 else ''
            if current_group != group:
                current_group = group
                md_lines.append(f'\n**{group}**\n')
                md_lines.append('| 目名 | 科名 | 種名 |')
                md_lines.append('|------|------|------|')
            md_lines.append(f'| {order} | {family} | {species} |')

        elif len(vals) == 3:
            # 3-col: order, family, species
            order, family, species = vals[0], vals[1], vals[2]
            if current_group is None:
                current_group = '_started'
                md_lines.append('| 目名 | 科名 | 種名 |')
                md_lines.append('|------|------|------|')
            md_lines.append(f'| {order} | {family} | {species} |')

        elif len(vals) == 2:
            # 2-col: family, species
            family, species = vals[0], vals[1]
            if current_group is None:
                md_lines.append('| 科名 | 種名 |')
                md_lines.append('|------|------|')
                current_group = '_started'
            md_lines.append(f'| {family} | {species} |')

        elif len(vals) == 1:
            v = vals[0]
            if v in GROUP_MARKERS:
                current_group = v
                md_lines.append(f'\n**{v}**\n')
                md_lines.append('| 目名 | 科名 | 種名 |')
                md_lines.append('|------|------|------|')

    return md_lines


def _build_species_md_flat(cells):
    """Build species markdown from flat cell list (handles 225-cell-per-row HTML)."""
    # Identify group markers and species rows by scanning cells sequentially
    ORDER_MARKERS = {'ハラタケ目', 'タマチョレイタケ目', 'ベニタケ目', 'スッポンタケ目',
                     'キクラゲ目', 'タバコウロコタケ目', 'ヒメツチグリ目', 'クロサイワイタケ目',
                     'チャワンタケ目', 'イボタケ目'}

    md_lines = []
    # Remove header cells
    skip = {'五分類群', '新目名', '新科名', '種名', '科名', '\xa0', 'a'}
    filtered = [c for c in cells if c not in skip]

    current_group = None
    i = 0
    while i < len(filtered):
        c = filtered[i]
        if c in GROUP_MARKERS:
            if current_group != c:
                current_group = c
                md_lines.append(f'\n**{c}**\n')
                md_lines.append('| 目名 | 科名 | 種名 |')
                md_lines.append('|------|------|------|')
            i += 1
            continue

        if c in ORDER_MARKERS:
            # Next cells should be: 科名, 種名, (optional)
            order = c
            i += 1
            if i < len(filtered) and filtered[i] not in ORDER_MARKERS and filtered[i] not in GROUP_MARKERS:
                family = filtered[i]
                i += 1
                if i < len(filtered) and filtered[i] not in ORDER_MARKERS and filtered[i] not in GROUP_MARKERS:
                    species = filtered[i]
                    i += 1
                    md_lines.append(f'| {order} | {family} | {species} |')
                else:
                    md_lines.append(f'| {order} | {family} | |')
            else:
                md_lines.append(f'| {order} | | |')
            continue

        i += 1

    return md_lines


def pass3_extract_images(soup, year_str):
    """Pass 3: Extract unique images, normalizing spaces to underscores."""
    body = soup.find('body')
    if not body:
        return [], []

    seen = set()
    md_imgs = []
    raw_srcs = []

    for img in body.find_all('img'):
        src = img.get('src', '')
        if not src:
            continue
        basename = os.path.basename(src)
        # Normalize
        basename = basename.replace('.jpg.jpg', '.jpg').replace('.JPG.JPG', '.JPG')
        basename_norm = basename.replace(' ', '_')

        if basename_norm in seen or not basename_norm:
            continue
        seen.add(basename_norm)

        alt = img.get('alt', '') or ''
        md_imgs.append(f'![{alt}](/reikai/{year_str}/{basename_norm})')
        raw_srcs.append(src)

    return md_imgs, raw_srcs


def pass4_assemble(meta, body_text, images_md, tables_md):
    """Pass 4: Assemble final markdown."""
    fm_lines = [f'title: "{meta.get("title", "報告").replace(chr(34), "")}"']
    if meta.get('date'):
        fm_lines.append(f'date: {meta["date"]}')
    fm_lines.append(f'reporter: "{meta.get("reporter", "不明").replace(chr(34), "")}"')
    if meta.get('location'):
        fm_lines.append(f'location: "{meta["location"].replace(chr(34), "")}"')
    if meta.get('participants'):
        fm_lines.append(f'participants: {meta["participants"]}')

    fm = '---\n' + '\n'.join(fm_lines) + '\n---'

    # Remove species data lines from body text
    body_lines = body_text.split('\n')
    clean_body = []
    for line in body_lines:
        if line.strip() in SPECIES_KW:
            continue
        if any(kw in line for kw in SPECIES_KW) and len(line) < 30:
            continue
        if line.strip() in SKIP_LINES:
            continue
        clean_body.append(line)

    body_text = '\n'.join(clean_body).strip()
    body_text = re.sub(r'\n{3,}', '\n\n', body_text)

    img_section = ''
    if images_md:
        if len(images_md) >= 2:
            img_section = '\n<div class="grid grid-cols-2 gap-2 my-4">\n\n'
            img_section += '\n\n'.join(images_md)
            img_section += '\n\n</div>\n'
        else:
            img_section = '\n' + images_md[0] + '\n'

    table_section = ''
    if tables_md:
        table_section = '\n\n## 確認種一覧\n\n' + '\n\n'.join(tables_md)

    return f'{fm}\n\n{img_section}\n{body_text}{table_section}\n'


def process_file(html_path, year_str):
    html = read_html(html_path)
    soup = BeautifulSoup(html, 'html.parser')
    clean_soup(soup)

    meta = extract_meta(soup, html_path.stem)

    if 'date' not in meta:
        m = re.search(r'(\d{2})(\d{2})(\d{2})', html_path.stem)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = y + 2000 if y < 50 else y + 1900
            if 1 <= mo <= 12 and 1 <= d <= 31:
                meta['date'] = f'{y}-{mo:02d}-{d:02d}'
    if 'date' not in meta:
        return None

    if not meta.get('title') or len(meta['title']) < 3:
        for key, ja in PLACE_MAP.items():
            if key in html_path.stem.lower():
                meta['title'] = ja
                break
        else:
            meta['title'] = f'{meta["date"]} 行事報告'
    meta['title'] = re.sub(r'[\r\n]+', ' ', meta['title']).strip()[:60]

    body_text = pass1_extract_text(soup)

    soup2 = BeautifulSoup(html, 'html.parser')
    clean_soup(soup2)
    tables_md = pass2_extract_tables(soup2, year_str)
    images_md, raw_srcs = pass3_extract_images(soup2, year_str)

    if len(body_text) < 20 and not images_md:
        return None

    content = pass4_assemble(meta, body_text, images_md, tables_md)

    trans = str.maketrans('０１２３４５６７８９', '0123456789')
    content = content.translate(trans)

    slug = meta['date'] + '-' + re.sub(r'[^\w]', '', html_path.stem)[:20]

    return {
        'slug': slug,
        'content': content,
        'raw_srcs': raw_srcs,
        'html_dir': html_path.parent,
        'year': year_str,
    }


def copy_images(html_dir, raw_srcs, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in raw_srcs:
        if src.startswith('http'):
            continue
        basename = os.path.basename(src)
        img_path = html_dir / basename
        if not img_path.exists():
            img_path = html_dir / src
        if img_path.exists():
            # Normalize dest name: spaces → underscores
            dest_name = basename.replace(' ', '_').replace('.jpg.jpg', '.jpg')
            dest = dest_dir / dest_name
            if not dest.exists():
                shutil.copy2(img_path, dest)
                copied += 1
    return copied


def main():
    # Get currently protected slugs from existing files
    protected_slugs = set()
    for f in OUT_CONTENT.glob('*.md'):
        for p in PROTECTED:
            if p in f.stem:
                protected_slugs.add(f.stem)
                break

    print(f'Protected files: {len(protected_slugs)}')

    # Clear non-protected files
    cleared = 0
    for f in OUT_CONTENT.glob('*.md'):
        if f.stem in protected_slugs:
            continue
        f.unlink()
        cleared += 1
    print(f'Cleared: {cleared} files')

    total_md = 0
    total_img = 0

    years = sorted([d for d in BACKUP.iterdir() if d.is_dir() and re.match(r'^\d{4}$', d.name)])

    for year_dir in years:
        year = year_dir.name
        html_files = list(year_dir.glob('*.html')) + list(year_dir.glob('*.htm'))
        reports = []

        for hf in html_files:
            name = hf.stem.lower()
            if 'index' in name or 'houkoku_reikai' in name or name.endswith('reikaihoukoku') or name == 'whatsnew':
                continue

            result = process_file(hf, year)
            if result:
                # Skip if protected
                if any(p in result['slug'] for p in PROTECTED):
                    print(f'  [PROTECTED] {result["slug"]}')
                    continue
                reports.append(result)

        if reports:
            print(f'{year}: {len(reports)} reports')
            for r in reports:
                md_path = OUT_CONTENT / f'{r["slug"]}.md'
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(r['content'])
                img_dest = OUT_IMAGES / r['year']
                copied = copy_images(r['html_dir'], r['raw_srcs'], img_dest)
                total_img += copied
                total_md += 1

    # Copy all remaining images from backup
    print('\nCopying remaining images...')
    for year_dir in years:
        dest = OUT_IMAGES / year_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        for img in year_dir.iterdir():
            if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                d_name = img.name.replace(' ', '_').replace('.jpg.jpg', '.jpg')
                d = dest / d_name
                if not d.exists():
                    shutil.copy2(img, d)
                    total_img += 1
        for sub in year_dir.iterdir():
            if sub.is_dir():
                for img in sub.iterdir():
                    if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                        d_name = img.name.replace(' ', '_').replace('.jpg.jpg', '.jpg')
                        d = dest / d_name
                        if not d.exists():
                            shutil.copy2(img, d)
                            total_img += 1

    print(f'\n=== Complete ===')
    print(f'Markdown: {total_md}')
    print(f'Images: {total_img}')


if __name__ == '__main__':
    main()
