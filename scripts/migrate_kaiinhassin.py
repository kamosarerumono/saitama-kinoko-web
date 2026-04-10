"""Migrate kaiinhassin (member posts) from old HTML to individual Markdown files."""
import os
import re
import sys
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\kaiinhassin')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\kaiinhassin')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\kaiinhassin')


def read_html():
    html_path = BACKUP / 'kaiinhassin.html'
    with open(html_path, 'rb') as f:
        raw = f.read()
    return raw.decode('shift_jis', errors='replace')


def extract_posts(html):
    """Extract individual posts from the member page."""
    posts = []

    # The page structure: year headers followed by contributor sections
    # Pattern: ■contributor名 (date) followed by content and images
    sections = re.split(r'<B>　?(\S+年度?|２０\d{2})', html)

    # Simpler approach: find all ■ entries with contributor info
    # Look for patterns like: ■氏名より (date)
    pattern = r'■\s*(.+?)(?:氏より|より|さんより|から)\s*(?:<[^>]+>)*\s*\(?([^)（]*)\)?'
    matches = list(re.finditer(pattern, html))

    if not matches:
        # Try alternate pattern
        pattern = r'■(.+?)(?:<[^>]+>)*\s*\(?(\d+/\d*|１/|２/|[０-９]+/)'
        matches = list(re.finditer(pattern, html))

    return matches


def main():
    OUT_CONTENT.mkdir(parents=True, exist_ok=True)
    OUT_IMAGES.mkdir(parents=True, exist_ok=True)

    html = read_html()

    # Copy all images from kaiinhassin directory
    img_count = 0
    for f in BACKUP.iterdir():
        if f.suffix.lower() in ('.jpg', '.jpeg', '.gif', '.png'):
            dest = OUT_IMAGES / f.name
            shutil.copy2(f, dest)
            img_count += 1

    # Extract the main page content sections manually
    # The page has 2019, 2017, 2012 sections
    # Let's create structured posts from each year section

    # Find year markers
    year_sections = []

    # 2019 section
    m = re.search(r'２０１９(.*?)(?=２０１７|$)', html, re.DOTALL)
    if m:
        year_sections.append(('2019', m.group(1)))

    m = re.search(r'２０１７(.*?)(?=２０１２|$)', html, re.DOTALL)
    if m:
        year_sections.append(('2017', m.group(1)))

    m = re.search(r'２０１２(.*?)$', html, re.DOTALL)
    if m:
        year_sections.append(('2012', m.group(1)))

    post_count = 0
    for year, section_html in year_sections:
        # Find contributor blocks (■name)
        blocks = re.split(r'■\s*', section_html)
        for i, block in enumerate(blocks[1:], 1):  # Skip first empty
            # Extract contributor name
            name_m = re.match(r'([^<\n]+)', block)
            if not name_m:
                continue
            raw_name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()

            # Extract images
            imgs = re.findall(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)

            # Extract text content
            text = re.sub(r'<[^>]+>', '', block)
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'\r', '', text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()

            if len(text) < 20 and not imgs:
                continue

            # Build markdown
            slug = f'{year}-post-{i:02d}'
            title_clean = raw_name[:50].replace('"', '')

            fm = f'---\ntitle: "{title_clean}"\ndate: {year}-01-01\nauthor: "{title_clean.split("（")[0].split("より")[0].strip()}"\n---\n\n'

            body = text[:200] + '\n\n' if len(text) > 200 else text + '\n\n'

            # Add remaining text
            lines = text.split('\n')
            body = '\n'.join(lines) + '\n'

            # Add images
            for img in imgs:
                basename = os.path.basename(img)
                body += f'\n![{basename}](/kaiinhassin/{basename})\n'

            md_path = OUT_CONTENT / f'{slug}.md'
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(fm + body)

            post_count += 1
            print(f'  [{year}] {slug}: {title_clean[:40]}... (images: {len(imgs)})')

    print(f'\n=== 完了 ===')
    print(f'Posts: {post_count}')
    print(f'Images: {img_count}')


if __name__ == '__main__':
    main()
