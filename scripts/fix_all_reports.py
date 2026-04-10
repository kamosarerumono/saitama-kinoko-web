"""Fix all report markdown files: metadata, image layout, empty files, typos."""
import os, re, sys
from pathlib import Path

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


def find_html(md_name):
    """Find original HTML for a markdown file."""
    stem = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', md_name.replace('.md', ''))
    for root, _, files in os.walk(BACKUP):
        for f in files:
            if f.endswith(('.html', '.htm')):
                f_stem = f.replace('.html', '').replace('.htm', '')
                if stem == f_stem or stem in f_stem or f_stem in stem:
                    return Path(root) / f
    return None


def extract_meta_from_html(html_path):
    """Extract reporter, location, participants from HTML."""
    enc = detect_encoding(html_path)
    with open(html_path, 'rb') as f:
        html = f.read().decode(enc, errors='replace')

    meta = {}
    patterns = {
        'reporter': [
            r'報告者[）)：:＞</b></TD>\s]*</?[^>]*>*\s*([^<\n]{2,20})',
            r'報告[）)：:＞</b>\s]+([^<\n]{2,15})',
            r'文責[　\s：:]+([^<\n]{2,15})',
        ],
        'location': [
            r'(?:開催場所|観察地域)[）)：:＞</b></TD>\s]*</?[^>]*>*\s*([^<\n]{2,40})',
            r'集合場所[）)：:＞</b></TD>\s]*</?[^>]*>*\s*([^<\n]{2,40})',
        ],
        'participants': [
            r'参加者[）)：:＞</b></TD>\s]*</?[^>]*>*\s*(\d+)',
        ],
        'organizer': [
            r'世話人[）)：:＞</b></TD>\s]*</?[^>]*>*\s*([^<\n]{2,30})',
        ],
    }

    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, html)
            if m:
                val = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                val = val.rstrip('　 ')
                if val and len(val) > 1:
                    meta[key] = val
                    break

    return meta


def format_image_grid(body):
    """Convert 3+ consecutive images into grid blocks."""
    lines = body.split('\n')
    result = []
    img_buffer = []

    def flush_images():
        if len(img_buffer) >= 2:
            result.append('')
            result.append('<div class="grid grid-cols-2 gap-2 my-4">')
            for img_line in img_buffer:
                result.append(f'  {img_line}')
            result.append('</div>')
            result.append('')
        else:
            result.extend(img_buffer)

    for line in lines:
        stripped = line.strip()
        if re.match(r'^!\[', stripped):
            img_buffer.append(stripped)
        else:
            if img_buffer:
                flush_images()
                img_buffer = []
            result.append(line)

    if img_buffer:
        flush_images()

    return '\n'.join(result)


TYPO_FIXES = [
    (r'おおがくず', 'おがくず'),
    (r'觀察', '観察'),
    (r'きのこの鑑定を行いまた。', 'きのこの鑑定を行いました。'),
    (r'参加しまた。', '参加しました。'),
    (r'行いまた。', '行いました。'),
    (r'開催しまた。', '開催しました。'),
    (r'實施', '実施'),
]


def fix_typos(text):
    for pattern, replacement in TYPO_FIXES:
        text = re.sub(pattern, replacement, text)
    return text


def main():
    stats = {'meta_fixed': 0, 'grid_fixed': 0, 'typo_fixed': 0, 'removed': 0}

    # Remove empty sub-page files
    for md in sorted(CONTENT.glob('*.md')):
        with open(md, 'r', encoding='utf-8') as f:
            content = f.read()
        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        body = content[fm_match.end():].strip()
        text_only = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body).strip()

        # If body has only 1 image and no text, it's a sub-page thumbnail
        img_count = len(re.findall(r'!\[', body))
        if len(text_only) < 10 and img_count <= 1:
            md.unlink()
            stats['removed'] += 1
            continue

    # Fix remaining files
    for md in sorted(CONTENT.glob('*.md')):
        with open(md, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content
        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        body = content[fm_match.end():]

        # 1. Fix metadata from HTML
        if 'reporter: "不明"' in fm or 'location:' not in fm:
            html_path = find_html(md.name)
            if html_path:
                meta = extract_meta_from_html(html_path)
                if meta.get('reporter') and 'reporter: "不明"' in fm:
                    r = meta['reporter'].replace('"', '')
                    fm = fm.replace('reporter: "不明"', f'reporter: "{r}"')
                if meta.get('location') and 'location:' not in fm:
                    loc = meta['location'].replace('"', '')
                    fm += f'\nlocation: "{loc}"'
                if meta.get('participants') and 'participants:' not in fm:
                    fm += f'\nparticipants: {meta["participants"]}'
                if meta.get('organizer') and 'organizer:' not in fm:
                    org = meta['organizer'].replace('"', '')
                    fm += f'\norganizer: "{org}"'

        # 2. Format consecutive images as grid
        new_body = format_image_grid(body)
        if new_body != body:
            stats['grid_fixed'] += 1

        # 3. Fix typos
        fixed_body = fix_typos(new_body)
        if fixed_body != new_body:
            stats['typo_fixed'] += 1

        new_content = f'---\n{fm}\n---{fixed_body}'

        if new_content != original:
            with open(md, 'w', encoding='utf-8') as f:
                f.write(new_content)
            stats['meta_fixed'] += 1

    print(f"=== 完了 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  remaining files: {len(list(CONTENT.glob('*.md')))}")


if __name__ == '__main__':
    main()
