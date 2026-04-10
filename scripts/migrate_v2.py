"""V2 migration: BeautifulSoup-based HTML->Markdown converter for all reikai reports."""
import os, re, sys, shutil
from pathlib import Path
from bs4 import BeautifulSoup, Comment

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')

# Clear existing markdown (will regenerate all)
for f in OUT_CONTENT.glob('*.md'):
    f.unlink()


def detect_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read(1000)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        open(filepath, 'rb').read().decode('utf-8')
        return 'utf-8'
    except:
        return 'shift_jis'


def read_html(filepath):
    enc = detect_encoding(filepath)
    with open(filepath, 'rb') as f:
        return f.read().decode(enc, errors='replace')


def clean_soup(soup):
    """Remove MSO artifacts, scripts, styles, comments."""
    # Remove comments (including MSO conditionals)
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove style/script tags
    for tag in soup.find_all(['style', 'script']):
        tag.decompose()

    # Remove MSO-specific elements
    for tag in soup.find_all(True):
        # Remove style attributes
        if tag.has_attr('style'):
            del tag['style']
        if tag.has_attr('class'):
            classes = tag.get('class', [])
            if any('Mso' in c for c in classes):
                tag.unwrap()


def extract_meta(soup, filename):
    """Extract metadata from HTML structure."""
    meta = {'reporter': '不明', 'title': ''}

    # Title from H2/H3
    for h in soup.find_all(['h2', 'h3', 'h1']):
        text = h.get_text(strip=True)
        if text and len(text) > 3 and text not in ('CONTENTS', 'HOME', 'a'):
            meta['title'] = text
            break

    if not meta['title']:
        title_tag = soup.find('title')
        if title_tag:
            t = title_tag.get_text(strip=True)
            if t and len(t) > 3 and not re.match(r'^[\da-z_]+$', t, re.I):
                meta['title'] = t

    # Extract from table rows (common pattern: label | value)
    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            label = tds[0].get_text(strip=True)
            value = tds[1].get_text(strip=True)
            if '報告' in label and value:
                meta['reporter'] = value[:20]
            elif '場所' in label or '観察地' in label or '集合' in label:
                if value and 'location' not in meta:
                    meta['location'] = value[:50]
            elif '参加' in label:
                m = re.search(r'(\d+)', value)
                if m:
                    meta['participants'] = int(m.group(1))
            elif '世話人' in label:
                meta['organizer'] = value[:30]

    # Also search in body text
    body_text = soup.get_text()
    if meta['reporter'] == '不明':
        for pat in [r'報告者[：:　\s]+([^\s<]{2,15})', r'文責[：:　\s]+([^\s<]{2,15})']:
            m = re.search(pat, body_text)
            if m:
                meta['reporter'] = m.group(1).strip()
                break

    if 'location' not in meta:
        for pat in [r'(?:開催場所|観察地域|集合場所)[：:　\s]+([^\n]{2,40})']:
            m = re.search(pat, body_text)
            if m:
                meta['location'] = m.group(1).strip()[:50]
                break

    # Date from content
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', body_text)
    if m:
        meta['date'] = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

    return meta


def soup_to_markdown(soup, year_str):
    """Convert BeautifulSoup body to clean markdown."""
    # Get body content
    body = soup.find('body')
    if not body:
        return '', []

    # Remove navigation
    nav_links = [a for a in body.find_all('a')
                 if a.get_text(strip=True) in ('HOME', 'もどる', '2025年度例会報告一覧へ')
                 or 'index.htm' in (a.attrs.get('href', '') if a.attrs else '')]
    for a in nav_links:
        a.decompose()

    for hr in body.find_all('hr'):
        hr.decompose()

    # Collect images
    images = []
    for img in body.find_all('img'):
        src = img.get('src', '')
        if src:
            images.append(src)

    # Convert to text
    parts = []
    for elem in body.descendants:
        if elem.name == 'img':
            src = elem.get('src', '')
            if src:
                basename = os.path.basename(src)
                alt = elem.get('alt', '')
                parts.append(f'\n![{alt}](/reikai/{year_str}/{basename})\n')
        elif elem.name in ('h1', 'h2', 'h3'):
            text = elem.get_text(strip=True)
            if text and text not in ('CONTENTS', 'HOME', 'a'):
                level = int(elem.name[1])
                parts.append(f'\n{"#" * level} {text}\n')
        elif elem.name == 'br':
            parts.append('\n')
        elif elem.name == 'p':
            parts.append('\n\n')
        elif elem.name in ('b', 'strong'):
            text = elem.get_text(strip=True)
            if text:
                parts.append(f'**{text}**')
        elif elem.string and not elem.parent.name in ('script', 'style', 'b', 'strong', 'h1', 'h2', 'h3'):
            text = elem.string
            # Clean whitespace
            text = text.replace('\r', '')
            if text.strip():
                parts.append(text)

    md = ''.join(parts)

    # Clean up
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'[ \t]+\n', '\n', md)  # trailing spaces
    md = re.sub(r'^\s+', '', md, flags=re.MULTILINE)  # leading spaces (prevent code blocks)
    md = re.sub(r'\*{3,}', '', md)  # leftover asterisks

    # Grid layout for consecutive images
    def gridify(match):
        imgs = re.findall(r'!\[[^\]]*\]\([^)]+\)', match.group(0))
        if len(imgs) < 2:
            return match.group(0)
        lines = ['\n<div class="grid grid-cols-2 gap-2 my-4">']
        for img in imgs:
            lines.append(f'  {img}')
        lines.append('</div>\n')
        return '\n'.join(lines)

    md = re.sub(r'(!\[[^\]]*\]\([^)]+\)\s*\n\s*){2,}', gridify, md)

    return md.strip(), images


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
    'asiyasu': '芦安観察会', 'asamayama': '浅間山観察会',
    'gunma': '群馬の森観察会', 'gunnma': '群馬の森観察会',
    'saitamafore': '埼玉フォレスト観察会', 'sinnrinnkouenn': '森林公園観察会',
    'okushiga': '奥志賀観察会', 'shirakaba': '白樺湖観察会',
    'tatesina': '蓼科観察会', 'chichibu': '秩父観察会',
    'mizugaki': '瑞牆山観察会', 'kurumayama': '車山観察会',
    'kakisyukuhaku': '夏期宿泊観察会', 'sarugakyou': '猿ヶ京観察会',
    'ryourikyousitu': '料理教室', 'kawagoetiku': '川越地区観察会',
}


def guess_title(filename):
    name = filename.lower()
    for key, ja in PLACE_MAP.items():
        if key in name:
            return ja
    return None


def process_file(html_path, year_str):
    """Process one HTML file."""
    html = read_html(html_path)
    soup = BeautifulSoup(html, 'html.parser')
    clean_soup(soup)

    meta = extract_meta(soup, html_path.stem)
    md, images = soup_to_markdown(soup, year_str)

    # Skip empty/tiny files
    text_only = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', md).strip()
    if len(text_only) < 10 and len(images) <= 1:
        return None

    # Date
    if 'date' not in meta:
        m = re.search(r'(\d{2})(\d{2})(\d{2})', html_path.stem)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = y + 2000 if y < 50 else y + 1900
            if 1 <= mo <= 12 and 1 <= d <= 31:
                meta['date'] = f'{y}-{mo:02d}-{d:02d}'
    if 'date' not in meta:
        return None

    # Title
    if not meta.get('title') or len(meta['title']) < 3:
        meta['title'] = guess_title(html_path.stem) or f'{meta["date"]} 行事報告'

    meta['title'] = re.sub(r'[\r\n]+', ' ', meta['title']).strip()[:60]

    # Build frontmatter
    fm_lines = [
        f'title: "{meta["title"].replace(chr(34), "")}"',
        f'date: {meta["date"]}',
        f'reporter: "{meta["reporter"].replace(chr(34), "")}"',
    ]
    if meta.get('location'):
        fm_lines.append(f'location: "{meta["location"].replace(chr(34), "")}"')
    if meta.get('participants'):
        fm_lines.append(f'participants: {meta["participants"]}')
    if meta.get('organizer'):
        fm_lines.append(f'organizer: "{meta["organizer"].replace(chr(34), "")}"')

    slug = meta['date'] + '-' + re.sub(r'[^\w]', '', html_path.stem)[:20]

    return {
        'slug': slug,
        'content': '---\n' + '\n'.join(fm_lines) + '\n---\n\n' + md + '\n',
        'images': images,
        'html_dir': html_path.parent,
        'year': year_str,
    }


def copy_images(html_dir, images, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in images:
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
    OUT_CONTENT.mkdir(parents=True, exist_ok=True)
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
                copied = copy_images(r['html_dir'], r['images'], img_dest)
                total_img += copied
                total_md += 1

    # Also copy all images from year directories
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

    print(f'\n=== Complete ===')
    print(f'Markdown: {total_md}')
    print(f'Images: {total_img}')


if __name__ == '__main__':
    main()
