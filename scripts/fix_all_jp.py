"""
Fix all Japanese-related issues:
1. Rename Markdown files with full-width digits to ASCII digits
2. For each Markdown file with jp_YYYY_NNNN.jpg refs:
   - Find corresponding HTML in backup
   - Extract Japanese images in order
   - Copy with unique ASCII names (md_stem_prefix_NNN.jpg)
   - Update Markdown references
"""
import os, re, sys, shutil
from pathlib import Path
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
OUT_CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')
OUT_IMAGES = Path(r'C:\tools\saitama-kinoko-web\public\reikai')

# Full-width digit to ASCII
FULLWIDTH_MAP = str.maketrans('０１２３４５６７８９', '0123456789')

PROTECTED_STEMS = {
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


# ── Part 1: Rename garbled Markdown filenames ──────────────────────────────

def fix_md_filenames():
    renamed = 0
    for md in sorted(OUT_CONTENT.glob('*.md')):
        if not any(ord(c) > 127 for c in md.name):
            continue
        new_name = md.name.translate(FULLWIDTH_MAP)
        if not any(ord(c) > 127 for c in new_name):
            new_path = md.parent / new_name
            if not new_path.exists():
                md.rename(new_path)
                print(f'  renamed: {md.name} → {new_name}')
                renamed += 1
            else:
                print(f'  skip (exists): {new_name}')
        else:
            print(f'  still garbled: {md.name!r}')
    print(f'Renamed {renamed} MD files')
    return renamed


# ── Part 2: Fix jp_* image references ─────────────────────────────────────

def detect_encoding(fp):
    with open(fp, 'rb') as f:
        raw = f.read(500)
    if b'charset=UTF-8' in raw or b'charset=utf-8' in raw:
        return 'utf-8'
    try:
        with open(fp, 'rb') as f:
            f.read().decode('utf-8')
        return 'utf-8'
    except Exception:
        return 'shift_jis'


def has_non_ascii(s):
    return any(ord(c) > 127 for c in s)


def extract_jp_img_srcs(html_bytes, encoding):
    """Extract basenames of Japanese-named images from HTML."""
    html = html_bytes.decode(encoding, errors='replace')
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src:
            bn = os.path.basename(src)
            if has_non_ascii(bn):
                result.append(bn)
    return result


def find_html_for_md(md_stem, year):
    """Find backup HTML file corresponding to a Markdown stem."""
    year_dir = BACKUP / year
    if not year_dir.exists():
        return None

    # Extract the tail part after the date prefix (e.g., '220522soukai' from '2022-05-22-220522soukai')
    parts = md_stem.split('-', 3)
    tail = parts[3] if len(parts) >= 4 else md_stem
    tail_clean = re.sub(r'[^\w]', '', tail).lower()

    html_files = sorted(
        list(year_dir.glob('*.html')) + list(year_dir.glob('*.htm')),
        key=lambda f: f.stem
    )
    # Normalize HTML stem (remove spaces/non-alnum) for comparison
    def norm(s):
        return re.sub(r'[^\w]', '', s).lower()

    # Exact match (normalized)
    for hf in html_files:
        if norm(hf.stem) == tail_clean:
            return hf
    # Contains (normalized both sides)
    for hf in html_files:
        h = norm(hf.stem)
        if tail_clean in h or h in tail_clean:
            return hf
    # Partial (first 8 chars)
    short = tail_clean[:8]
    for hf in html_files:
        if short in norm(hf.stem):
            return hf
    return None


def fix_jp_image_refs():
    total_copied = 0
    total_updated = 0

    # Process after rename, re-glob
    for md in sorted(OUT_CONTENT.glob('*.md')):
        content = md.read_text(encoding='utf-8')

        # Find jp_* references
        jp_pattern = re.compile(r'/reikai/(\d{4})/(jp_\d{4}_\d{4}\.[a-zA-Z]+)')
        matches = jp_pattern.findall(content)
        if not matches:
            continue

        # Determine year
        year = matches[0][0]
        # All refs in this file (in order, unique by jp name)
        jp_refs_ordered = []
        seen_jp = set()
        for m in jp_pattern.finditer(content):
            jp_name = m.group(2)
            if jp_name not in seen_jp:
                seen_jp.add(jp_name)
                jp_refs_ordered.append(jp_name)

        # Check protection
        if md.stem in PROTECTED_STEMS:
            print(f'  [PROTECTED] {md.name} - skipping')
            continue

        # Find HTML in backup
        html_file = find_html_for_md(md.stem, year)
        if not html_file:
            print(f'  [WARN] HTML not found for {md.stem} (year={year})')
            continue

        # Get Japanese images from HTML
        with open(html_file, 'rb') as f:
            raw = f.read()
        enc = detect_encoding(html_file)
        jp_imgs = extract_jp_img_srcs(raw, enc)

        if not jp_imgs:
            print(f'  [WARN] No JP images in {html_file.name}')
            continue

        # Build index: actual Japanese name → backup path
        year_dir = BACKUP / year
        backup_index = {}
        for f in year_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                backup_index[f.name] = f
                backup_index[f.name.lower()] = f

        # Generate unique prefix from md stem
        parts = md.stem.split('-', 3)
        tail = parts[3] if len(parts) >= 4 else md.stem
        prefix = re.sub(r'[^\w]', '', tail)[:12]

        # Map jp_name → new_ascii_name (match by position)
        jp_mapping = {}  # jp_name → new_ascii_name
        dest_dir = OUT_IMAGES / year
        dest_dir.mkdir(parents=True, exist_ok=True)

        for i, jp_name in enumerate(jp_refs_ordered):
            # The i-th jp_* ref corresponds to the i-th Japanese image in HTML
            if i < len(jp_imgs):
                actual_name = jp_imgs[i]
                ext = Path(actual_name).suffix.lower() or '.jpg'
                new_name = f'{prefix}_{i+1:03d}{ext}'
                jp_mapping[jp_name] = new_name

                # Find backup file
                backup_path = backup_index.get(actual_name) or backup_index.get(actual_name.lower())
                if backup_path:
                    dest = dest_dir / new_name
                    if not dest.exists():
                        shutil.copy2(backup_path, dest)
                        total_copied += 1
                    print(f'    {jp_name} → {new_name} (from {actual_name[:30]})')
                else:
                    print(f'    [MISSING] {jp_name} → {new_name} ({actual_name[:30]})')
            else:
                # More refs than images — reuse last image
                if i > 0 and jp_refs_ordered[i-1] in jp_mapping:
                    jp_mapping[jp_name] = jp_mapping[jp_refs_ordered[i-1]]
                    print(f'    [OVERFLOW] {jp_name} → reuse previous')

        # Update Markdown
        new_content = content
        for jp_name, new_name in jp_mapping.items():
            old_path = f'/reikai/{year}/{jp_name}'
            new_path = f'/reikai/{year}/{new_name}'
            new_content = new_content.replace(old_path, new_path)

        if new_content != content:
            md.write_text(new_content, encoding='utf-8')
            total_updated += 1
            print(f'  Updated: {md.name}')
        else:
            print(f'  No change: {md.name}')

    print(f'\nCopied: {total_copied}, Updated: {total_updated} MD files')
    return total_copied, total_updated


def main():
    print('=== Part 1: Rename garbled MD filenames ===')
    fix_md_filenames()

    print('\n=== Part 2: Fix jp_* image references ===')
    fix_jp_image_refs()

    print('\n=== Done ===')


if __name__ == '__main__':
    main()
