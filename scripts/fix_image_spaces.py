"""
Fix image filenames with spaces: rename to use underscores.
Also update Markdown references to match renamed files.
Also remove .jpg.jpg double extensions.
"""
import os, re, shutil
from pathlib import Path

PUBLIC_REIKAI = Path(r'C:\tools\saitama-kinoko-web\public\reikai')
CONTENT_REIKAI = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

rename_map = {}  # old_name -> new_name (per year dir)

def fix_filenames():
    """Rename image files: spaces → underscores, .jpg.jpg → .jpg"""
    for year_dir in sorted(PUBLIC_REIKAI.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name
        for img in sorted(year_dir.iterdir()):
            if not img.is_file():
                continue
            old_name = img.name
            new_name = old_name

            # Fix double extension
            if new_name.lower().endswith('.jpg.jpg'):
                new_name = new_name[:-4]
            elif new_name.lower().endswith('.jpeg.jpeg'):
                new_name = new_name[:-5]

            # Fix spaces
            if ' ' in new_name:
                new_name = new_name.replace(' ', '_')

            if new_name != old_name:
                new_path = img.parent / new_name
                if not new_path.exists():
                    img.rename(new_path)
                    rename_map[(year, old_name)] = new_name
                    print(f'  renamed: {year}/{old_name} → {new_name}')
                else:
                    # New name already exists — just record the mapping
                    rename_map[(year, old_name)] = new_name
                    print(f'  skip (exists): {year}/{old_name} → {new_name}')


def update_markdown():
    """Update image references in all Markdown files."""
    updated_files = 0
    updated_refs = 0

    for md in sorted(CONTENT_REIKAI.glob('*.md')):
        content = md.read_text(encoding='utf-8')
        new_content = content

        # Fix double extension references
        new_content = re.sub(r'(!\[[^\]]*\]\(/reikai/\d+/[^)]+?)\.jpg\.jpg\)', r'\1.jpg)', new_content)
        new_content = re.sub(r'(!\[[^\]]*\]\(/reikai/\d+/[^)]+?)\.JPG\.JPG\)', r'\1.JPG)', new_content)

        # Fix space in paths → underscore
        def fix_img_path(m):
            full = m.group(0)
            if ' ' not in full:
                return full
            # Replace spaces only in the path part (inside the parentheses)
            alt = m.group(1)
            path = m.group(2)
            new_path = path.replace(' ', '_')
            return f'![{alt}]({new_path})'

        new_content = re.sub(r'!\[([^\]]*)\]\((/reikai/[^)]+)\)', fix_img_path, new_content)

        if new_content != content:
            md.write_text(new_content, encoding='utf-8')
            updated_files += 1
            # Count changes
            old_lines = set(content.splitlines())
            new_lines = set(new_content.splitlines())
            updated_refs += len(new_lines - old_lines)
            print(f'  updated: {md.name}')

    return updated_files, updated_refs


if __name__ == '__main__':
    print('=== Step 1: Renaming image files ===')
    fix_filenames()
    print(f'Renamed: {len(rename_map)} files')

    print('\n=== Step 2: Updating Markdown references ===')
    updated_files, updated_refs = update_markdown()
    print(f'Updated: {updated_files} markdown files')

    print('\nDone.')
