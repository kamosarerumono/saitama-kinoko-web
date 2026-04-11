"""V3 migration: 2-pass approach to eliminate text duplication.
Pass 1: get_text() + line-level dedup for body text
Pass 2: direct table extraction for species lists
"""
import os, re, sys, shutil
from pathlib import Path
from bs4 import BeautifulSoup, Comment

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')

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


def detect_encoding(fp):
    with open(fp, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        open(fp, 'rb').read().decode('utf-8')
        return 'utf-8'
    except:
        return 'shift_jis'


def read_html(fp):
    enc = detect_encoding(fp)
    with open(fp, 'rb') as f:
        return f.read().decode(enc, errors='replace')


def clean_soup(soup):
    """Remove scripts, styles, comments."""
    for tag in soup.find_all(['style', 'script']):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    # Remove style attributes
    for tag in soup.find_all(True):
        if tag.has_attr('style'):
            del tag['style']


def extract_meta(soup, filename):
    meta = {'reporter': '不明', 'title': ''}
    body_text = soup.get_text()

    # Title
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

    # Reporter, location, participants from text
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
    """Pass 1: Extract body text with line-level deduplication."""
    body = soup.find('body')
    if not body:
        return ''

    # Get raw text with newlines as separators
    raw = body.get_text(separator='\n')

    # Line-level dedup: remove consecutive duplicate lines
    lines = raw.split('\n')
    deduped = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == 'a':
            continue
        # Skip navigation
        if stripped in ('HOME', 'もどる', '2025年度例会報告一覧へ'):
            continue
        # Skip if same as previous line
        if deduped and stripped == deduped[-1]:
            continue
        deduped.append(stripped)

    # Join and clean
    text = '\n'.join(deduped)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove MSO artifacts
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\*\*\s*\*\*', '', text)
    return text.strip()


def pass2_extract_tables(soup, year_str):
    """Pass 2: Extract species tables as markdown."""
    body = soup.find('body')
    if not body:
        return []

    tables_md = []
    for table in body.find_all('table'):
        rows = table.find_all('tr')
        if len(rows) < 5:
            continue

        # Check if this is a species table
        first_cells = [c.get_text(strip=True) for c in rows[0].find_all(['td', 'th'])]
        first_cells = [c for c in first_cells if c]

        is_species = (
            any(c in ('五分類群', '科名') for c in first_cells) or
            (len(first_cells) >= 1 and any(kw in first_cells[0] for kw in ['ハラタケ類', 'ヒダナシタケ', '腹菌', 'キクラゲ', '子嚢菌']))
        )

        if not is_species:
            continue

        md_lines = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            vals = [c.get_text(strip=True) for c in cells]
            vals = [v for v in vals if v and v != 'a']

            if not vals:
                continue
            if len(vals) == 1:
                md_lines.append(f'\n**{vals[0]}**\n')
                md_lines.append('| 科名 | 種名 |')
                md_lines.append('|------|------|')
            elif len(vals) >= 2:
                if vals[0] in ('科名', '五分類群', '新目名', '新科名'):
                    continue
                md_lines.append(f'| {vals[0]} | {"、".join(vals[1:])} |')

        if len(md_lines) > 3:
            tables_md.append('\n'.join(md_lines))

    return tables_md


def pass3_extract_images(soup, year_str):
    """Pass 3: Extract unique images."""
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
        basename = basename.replace('.jpg.jpg', '.jpg').replace('.JPG.JPG', '.JPG')
        if basename in seen or not basename:
            continue
        seen.add(basename)
        alt = img.get('alt', '')
        md_imgs.append(f'![{alt}](/reikai/{year_str}/{basename})')
        raw_srcs.append(src)

    return md_imgs, raw_srcs


def pass4_assemble(meta, body_text, images_md, tables_md):
    """Pass 4: Assemble final markdown."""
    # Frontmatter
    fm_lines = [f'title: "{meta.get("title", "報告").replace(chr(34), "")}"']
    if meta.get('date'):
        fm_lines.append(f'date: {meta["date"]}')
    fm_lines.append(f'reporter: "{meta.get("reporter", "不明").replace(chr(34), "")}"')
    if meta.get('location'):
        fm_lines.append(f'location: "{meta["location"].replace(chr(34), "")}"')
    if meta.get('participants'):
        fm_lines.append(f'participants: {meta["participants"]}')

    fm = '---\n' + '\n'.join(fm_lines) + '\n---'

    # Remove species data from body text (it will be in tables_md)
    # Remove lines that look like table headers/data that will be in the species table
    species_keywords = ['五分類群', '新目名', '新科名', 'ハラタケ目', 'タマチョレイタケ目',
                       'ベニタケ目', 'スッポンタケ目', 'キクラゲ目', 'タバコウロコタケ目',
                       'ヒメツチグリ目']
    body_lines = body_text.split('\n')
    clean_body = []
    for line in body_lines:
        # Skip lines that are species table data
        if any(kw in line for kw in species_keywords) and len(line) < 200:
            continue
        # Skip 'もどる' and navigation
        if line.strip() in ('もどる', 'HOME'):
            continue
        clean_body.append(line)

    body_text = '\n'.join(clean_body).strip()

    # Build images section (grid layout for 2+ images)
    img_section = ''
    if images_md:
        if len(images_md) >= 2:
            img_section = '\n<div class="grid grid-cols-2 gap-2 my-4">\n\n'
            img_section += '\n\n'.join(images_md)
            img_section += '\n\n</div>\n'
        else:
            img_section = '\n' + images_md[0] + '\n'

    # Build species table section
    table_section = ''
    if tables_md:
        table_section = '\n\n## 確認種一覧\n\n' + '\n\n'.join(tables_md)

    return f'{fm}\n\n{img_section}\n{body_text}{table_section}\n'


def process_file(html_path, year_str):
    """Process one HTML file with 4-pass approach."""
    html = read_html(html_path)
    soup = BeautifulSoup(html, 'html.parser')
    clean_soup(soup)

    meta = extract_meta(soup, html_path.stem)

    # Date fallback
    if 'date' not in meta:
        m = re.search(r'(\d{2})(\d{2})(\d{2})', html_path.stem)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = y + 2000 if y < 50 else y + 1900
            if 1 <= mo <= 12 and 1 <= d <= 31:
                meta['date'] = f'{y}-{mo:02d}-{d:02d}'
    if 'date' not in meta:
        return None

    # Title fallback
    if not meta.get('title') or len(meta['title']) < 3:
        for key, ja in PLACE_MAP.items():
            if key in html_path.stem.lower():
                meta['title'] = ja
                break
        else:
            meta['title'] = f'{meta["date"]} 行事報告'
    meta['title'] = re.sub(r'[\r\n]+', ' ', meta['title']).strip()[:60]

    # 4 passes
    body_text = pass1_extract_text(soup)

    # Re-parse for tables/images (pass1 doesn't modify soup)
    soup2 = BeautifulSoup(html, 'html.parser')
    clean_soup(soup2)
    tables_md = pass2_extract_tables(soup2, year_str)
    images_md, raw_srcs = pass3_extract_images(soup2, year_str)

    # Skip empty
    if len(body_text) < 20 and not images_md:
        return None

    content = pass4_assemble(meta, body_text, images_md, tables_md)

    # Full-width digit fix
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
            dest = dest_dir / basename
            if not dest.exists():
                shutil.copy2(img_path, dest)
                copied += 1
    return copied


def main():
    # Clear existing
    for f in OUT_CONTENT.glob('*.md'):
        # Keep manually created files (2025-11-03, 2025-12-07, 2025-03-15-saibai)
        if '251103_akigase' in f.name or '251207_happyoukai' in f.name or '2025-03-15-saibai' in f.name:
            continue
        f.unlink()

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

    # Copy remaining images
    print('\nCopying remaining images...')
    for year_dir in years:
        dest = OUT_IMAGES / year_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        for img in year_dir.iterdir():
            if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                d = dest / img.name
                if not d.exists():
                    shutil.copy2(img, d)
                    total_img += 1
        # Subdirectories
        for sub in year_dir.iterdir():
            if sub.is_dir():
                for img in sub.iterdir():
                    if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                        d = dest / img.name
                        if not d.exists():
                            shutil.copy2(img, d)
                            total_img += 1

    print(f'\n=== Complete ===')
    print(f'Markdown: {total_md}')
    print(f'Images: {total_img}')


if __name__ == '__main__':
    main()
