"""Migrate reikai (meeting reports) from old HTML to Markdown + copy images."""
import os
import re
import sys
import shutil
from pathlib import Path
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.in_script = False
        self.in_style = False
        self.current_tag = None
        self.images = []
        self.skip_tags = {'script', 'style', 'head'}

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in self.skip_tags:
            self.in_script = True
        d = dict(attrs)
        if tag == 'img' and 'src' in d:
            alt = d.get('alt', '')
            self.images.append(d['src'])
            self.parts.append(f'\n![{alt}]({d["src"]})\n')
        if tag == 'br':
            self.parts.append('\n')
        if tag in ('h1', 'h2', 'h3'):
            level = int(tag[1])
            self.parts.append(f'\n{"#" * level} ')
        if tag == 'p':
            self.parts.append('\n\n')
        if tag == 'b' or tag == 'strong':
            self.parts.append('**')

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.in_script = False
        if tag in ('h1', 'h2', 'h3'):
            self.parts.append('\n')
        if tag == 'b' or tag == 'strong':
            self.parts.append('**')
        if tag == 'p':
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.in_script:
            self.parts.append(data)

    def get_text(self):
        text = ''.join(self.parts)
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        return text.strip()


def detect_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    if b'charset=Shift_JIS' in raw or b'charset=SHIFT_JIS' in raw or b'charset=shift_jis' in raw:
        return 'shift_jis'
    # Try UTF-8 first
    try:
        raw_all = open(filepath, 'rb').read()
        raw_all.decode('utf-8')
        return 'utf-8'
    except:
        return 'shift_jis'


def read_html(filepath):
    enc = detect_encoding(filepath)
    with open(filepath, 'rb') as f:
        return f.read().decode(enc, errors='replace')


def extract_meta(html, filename):
    """Extract title, date, location, reporter from HTML."""
    meta = {}

    # Title from <TITLE> or <H2> or <H3>
    m = re.search(r'<(?:TITLE|title)>(.*?)</(?:TITLE|title)>', html)
    if m:
        meta['raw_title'] = m.group(1).strip()

    m = re.search(r'<[Hh][23][^>]*>(.*?)</[Hh][23]>', html, re.DOTALL)
    if m:
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if title:
            meta['title'] = title

    if 'title' not in meta:
        meta['title'] = meta.get('raw_title', filename)

    # Reporter
    m = re.search(r'報告者[：:＞</b>\s]*([^<\n]+)', html)
    if m:
        meta['reporter'] = m.group(1).strip().rstrip('　 ')

    # Location
    m = re.search(r'(?:開催場所|観察地域|集合場所)[：:＞</b>\s]*([^<\n]+)', html)
    if m:
        meta['location'] = m.group(1).strip().rstrip('　 ')

    # Date from filename or content
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', html)
    if m:
        meta['date'] = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

    # Participants
    m = re.search(r'参加者[：:＞</b>\s]*(\d+)', html)
    if m:
        meta['participants'] = int(m.group(1))

    return meta


def html_to_markdown(html):
    """Convert HTML body to markdown."""
    # Remove everything before body content
    m = re.search(r'<(?:BODY|body)[^>]*>(.*)</(?:BODY|body)>', html, re.DOTALL)
    if m:
        body = m.group(1)
    else:
        body = html

    # Remove navigation links at bottom
    body = re.sub(r'<HR[^>]*>.*$', '', body, flags=re.DOTALL | re.IGNORECASE)

    extractor = HTMLTextExtractor()
    try:
        extractor.feed(body)
    except:
        pass

    return extractor.get_text(), extractor.images


def process_report(html_path, year_dir):
    """Process a single report HTML file."""
    html = read_html(html_path)
    meta = extract_meta(html, html_path.stem)
    text, images = html_to_markdown(html)

    if not meta.get('date'):
        # Try to extract from filename
        m = re.search(r'(\d{2})(\d{2})(\d{2})', html_path.stem)
        if m:
            y, mo, d = m.groups()
            yr = int(y)
            if yr < 50:
                yr += 2000
            else:
                yr += 1900
            meta['date'] = f'{yr}-{int(mo):02d}-{int(d):02d}'

    if not meta.get('date'):
        return None  # Skip files without dates

    if not meta.get('reporter'):
        meta['reporter'] = '不明'

    # Clean title
    title = meta['title']
    title = re.sub(r'[\r\n]+', ' ', title)
    title = title.strip()
    if not title or title == html_path.stem:
        title = f'{meta["date"]} 報告'

    # Build frontmatter
    fm = f'---\ntitle: "{title}"\ndate: {meta["date"]}\nreporter: "{meta["reporter"]}"'
    if meta.get('location'):
        loc = meta['location'].replace('"', '\\"')
        fm += f'\nlocation: "{loc}"'
    if meta.get('participants'):
        fm += f'\nparticipants: {meta["participants"]}'
    fm += '\n---\n\n'

    # Fix image paths in text
    img_dir = f'/reikai/{year_dir}'
    for img_src in images:
        basename = os.path.basename(img_src)
        text = text.replace(img_src, f'{img_dir}/{basename}')

    # Create slug from date
    slug = meta['date'] + '-' + re.sub(r'[^\w]', '', html_path.stem)[:20]

    return {
        'slug': slug,
        'content': fm + text,
        'images': images,
        'source': str(html_path),
        'date': meta['date'],
    }


def copy_images(html_dir, images, dest_dir):
    """Copy referenced images to destination."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for img_src in images:
        # Resolve relative path
        if img_src.startswith('http'):
            continue
        img_path = (html_dir / img_src).resolve()
        if not img_path.exists():
            # Try in same directory
            img_path = html_dir / os.path.basename(img_src)
        if img_path.exists():
            dest = dest_dir / img_path.name
            if not dest.exists():
                shutil.copy2(img_path, dest)
                copied += 1
    return copied


def scan_year_directory(year_path, year_str):
    """Scan a year directory for report HTML files."""
    reports = []
    html_files = list(year_path.glob('*.html')) + list(year_path.glob('*.htm'))

    for html_file in html_files:
        name = html_file.stem.lower()
        # Skip index files
        if 'index' in name or 'houkoku_reikai' in name or name.endswith('reikaihoukoku'):
            continue

        result = process_report(html_file, year_str)
        if result:
            result['html_dir'] = html_file.parent
            reports.append(result)

    return reports


def main():
    OUT_CONTENT.mkdir(parents=True, exist_ok=True)

    total_reports = 0
    total_images = 0

    # Process year directories
    year_dirs = sorted(BACKUP.iterdir())

    for item in year_dirs:
        if item.is_dir() and re.match(r'^\d{4}', item.name):
            year_str = item.name[:4]
            print(f'\n--- {year_str}年度 ---')
            reports = scan_year_directory(item, year_str)

            for r in reports:
                # Write markdown
                md_path = OUT_CONTENT / f'{r["slug"]}.md'
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(r['content'])

                # Copy images
                img_dest = OUT_IMAGES / year_str
                copied = copy_images(r['html_dir'], r['images'], img_dest)
                total_images += copied

                print(f'  {r["date"]} {md_path.name} (images: {copied})')
                total_reports += 1

        elif item.is_file() and item.suffix in ('.html', '.htm'):
            # Top-level report files (some years have reports directly in reikai/)
            name = item.stem.lower()
            if 'houkoku' in name or 'index' in name or 'reikai' in name.replace('2010', ''):
                continue
            if re.match(r'\d{6}', item.stem) or re.match(r'\d{8}', item.stem):
                result = process_report(item, 'misc')
                if result:
                    result['html_dir'] = item.parent
                    md_path = OUT_CONTENT / f'{result["slug"]}.md'
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(result['content'])
                    img_dest = OUT_IMAGES / 'misc'
                    copied = copy_images(result['html_dir'], result['images'], img_dest)
                    total_images += copied
                    print(f'  [misc] {result["date"]} {md_path.name} (images: {copied})')
                    total_reports += 1

    # Also copy all images from reikai directories (catch any not referenced in HTML)
    print('\n--- 追加画像のコピー ---')
    for year_dir in BACKUP.iterdir():
        if year_dir.is_dir() and re.match(r'^\d{4}', year_dir.name):
            year_str = year_dir.name[:4]
            dest = OUT_IMAGES / year_str
            dest.mkdir(parents=True, exist_ok=True)
            for img in year_dir.glob('*'):
                if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                    d = dest / img.name
                    if not d.exists():
                        shutil.copy2(img, d)
                        total_images += 1
            # Check subdirectories for images too
            for sub in year_dir.iterdir():
                if sub.is_dir():
                    for img in sub.glob('*'):
                        if img.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png', '.webp'):
                            d = dest / img.name
                            if not d.exists():
                                shutil.copy2(img, d)
                                total_images += 1

    print(f'\n=== 完了 ===')
    print(f'Markdown: {total_reports} files')
    print(f'Images: {total_images} files')


if __name__ == '__main__':
    main()
