"""Re-migrate kaiinhassin with proper content extraction."""
import os, re, sys, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\kaiinhassin')
OUT = Path(r'C:\tools\saitama-kinoko-web\src\content\kaiinhassin')

# Clear old output
for f in OUT.glob('*.md'):
    f.unlink()

# Read and decode
with open(BACKUP / 'kaiinhassin.html', 'rb') as f:
    html = f.read().decode('shift_jis', errors='replace')

# Remove HTML tags but preserve structure
def clean_html(text):
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<img[^>]+src="([^"]+)"[^>]*>', r'\n![image](\1)\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE|re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# Split by ■ markers to find individual posts
# First, split by year sections
year_pattern = r'(２０１９|２０１７|２０１２)'
parts = re.split(year_pattern, html)

year_map = {'２０１９': '2019', '２０１７': '2017', '２０１２': '2012'}
posts = []

current_year = None
for i, part in enumerate(parts):
    if part in year_map:
        current_year = year_map[part]
        continue
    if current_year is None:
        continue

    # Split this year's content by ■
    blocks = re.split(r'■\s*', part)
    for j, block in enumerate(blocks):
        if not block.strip() or len(block.strip()) < 30:
            continue

        # Extract author from first line
        author_m = re.match(r'([^<\n（(]{2,20}?)(?:氏)?(?:より|さんより|から)', block)
        author = author_m.group(1).strip() if author_m else ''
        author = re.sub(r'<[^>]+>', '', author).strip()

        # Extract date hint
        date_m = re.search(r'\((\d{1,2})/(\d{0,2})', block)
        month = int(date_m.group(1)) if date_m else (j + 1)
        day = int(date_m.group(2)) if date_m and date_m.group(2) else 1

        # Extract images
        images = re.findall(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)

        # Clean content
        content = clean_html(block)

        # Skip very short or empty content
        if len(content) < 20 and not images:
            continue

        # Fix image paths
        for img in images:
            basename = os.path.basename(img)
            content = content.replace(f'![image]({img})', f'![{basename}](/kaiinhassin/{basename})')

        # Build title
        title_parts = content.split('\n')[0][:60]
        if author:
            title = f'{author}氏より'
            if date_m:
                title += f'（{month}月）'
        else:
            title = title_parts[:40] if title_parts else f'{current_year}年投稿{j}'

        title = title.replace('"', '')

        slug = f'{current_year}-{month:02d}-{j:02d}'
        date = f'{current_year}-{month:02d}-{day:02d}'

        posts.append({
            'slug': slug,
            'title': title,
            'date': date,
            'author': author,
            'content': content,
            'images': images,
        })

# Write posts
for p in posts:
    author_line = f'\nauthor: "{p["author"]}"' if p['author'] else ''
    md = f'''---
title: "{p['title']}"
date: {p['date']}{author_line}
---

{p['content']}
'''
    out_path = OUT / f'{p["slug"]}.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'  {p["slug"]}: {p["title"][:40]}  ({len(p["images"])} images, {len(p["content"])} chars)')

print(f'\nTotal: {len(posts)} posts')
