"""Fix report titles by re-reading original HTML files."""
import os, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = Path(r'C:\tools\ippon_backup\reikai')
CONTENT = Path(r'C:\tools\saitama-kinoko-web\src\content\reikai')

# Map of location keywords to Japanese place names
PLACE_MAP = {
    'kawagoe': '川越観察会', 'minoyama': '美の山公園観察会', 'ogawa': '小川観察会',
    'akigase': '秋ヶ瀬公園観察会', 'tumagoi': '嬬恋観察会', 'soukai': '定期総会',
    'sinnenkai': '新年会', 'sinnennkai': '新年会', 'kouenkai': '講演会',
    'kouennkai': '講演会', 'kinokokouenkai': 'きのこ講演会',
    'projecter': 'プロジェクター発表会', 'projector': 'プロジェクター発表会',
    'suraido': 'スライド発表会', 'saibai': 'きのこ栽培勉強会',
    'syokkinn': '植菌勉強会', 'syokukin': '植菌勉強会', 'syotukin': '植菌勉強会',
    'benkyoukai': '勉強会', 'benkyouk': '勉強会',
    'kennbikyou': '顕微鏡勉強会', 'happyoub': '発表・勉強会', 'hapyoube': '発表・勉強会',
    'kansatu': '観察会', 'kansatukai': '観察会',
    'nasu': '那須観察会', 'siga': '志賀高原観察会',
    'fuji': '富士山観察会', 'fujisan': '富士山観察会',
    'myokou': '妙高高原観察会', 'nozawa': '野沢温泉観察会',
    'hotaka': '穂高観察会', 'hodaka': '穂高観察会',
    'asiyasu': '芦安観察会', 'asamayama': '浅間山観察会',
    'gunma': '群馬の森観察会', 'gunnma': '群馬の森観察会',
    'saitamafore': '埼玉フォレスト観察会',
    'sinnrinnkouenn': '森林公園観察会',
    'okushiga': '奥志賀観察会', 'shirakaba': '白樺湖観察会',
    'tatesina': '蓼科観察会', 'chichibu': '秩父観察会',
    'mizugaki': '瑞牆山観察会', 'kurumayama': '車山観察会',
    'kakisyukuhaku': '夏期宿泊観察会', 'sarugakyou': '猿ヶ京観察会',
    'ryourikyousitu': '料理教室', 'kouen': '講演会',
    'whatsnew': 'お知らせ', 'copy': '観察会報告',
}


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


def extract_title_from_html(html_path):
    """Try to extract a proper title from the original HTML."""
    enc = detect_encoding(html_path)
    with open(html_path, 'rb') as f:
        html = f.read().decode(enc, errors='replace')

    # Try H2/H3 first
    for tag in ['[Hh]2', '[Hh]3']:
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            title = re.sub(r'\s+', ' ', title)
            if len(title) > 3 and title not in ('CONTENTS', 'HOME'):
                return title

    # Try TITLE tag
    m = re.search(r'<TITLE>(.*?)</TITLE>', html, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        if len(title) > 3 and not re.match(r'^[\da-z_]+$', title):
            return title

    return None


def guess_title_from_filename(filename):
    """Generate a readable title from the filename."""
    # Remove date prefix and extension
    name = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', filename)
    name = re.sub(r'\.md$', '', name)

    # Remove numeric prefixes like 060624, 190317
    name = re.sub(r'^\d{6}_?', '', name)

    # Find matching place name
    name_lower = name.lower()
    for key, japanese in PLACE_MAP.items():
        if key in name_lower:
            return japanese

    return None


def find_original_html(md_filename):
    """Find the original HTML file that corresponds to a markdown file."""
    # Extract the original filename hint from the md filename
    # e.g., 2010-06-20-100620kawagoe.md -> look for *100620kawagoe*.html
    name = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', md_filename.replace('.md', ''))

    # Search in backup
    for root, dirs, files in os.walk(BACKUP):
        for f in files:
            if f.endswith(('.html', '.htm')):
                f_clean = f.replace('.html', '').replace('.htm', '')
                if name in f_clean or f_clean in name:
                    return Path(root) / f

    return None


def main():
    fixed = 0
    for md_file in sorted(CONTENT.glob('*.md')):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract current title
        m = re.search(r'^title:\s*"(.+?)"', content, re.MULTILINE)
        if not m:
            continue
        current_title = m.group(1)

        # Check if title needs fixing
        needs_fix = (
            re.match(r'^\d{4}-\d{2}-\d{2}\s+報告$', current_title) or  # "2010-05-09 報告"
            re.match(r'^[\da-z_]+$', current_title, re.IGNORECASE) or    # "090510soukai"
            len(current_title) < 5
        )

        if not needs_fix:
            continue

        # Try to get title from original HTML
        new_title = None
        html_path = find_original_html(md_file.name)
        if html_path:
            new_title = extract_title_from_html(html_path)

        # Fallback: guess from filename
        if not new_title:
            new_title = guess_title_from_filename(md_file.name)

        # Fallback: extract date
        if not new_title:
            date_m = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
            if date_m:
                new_title = f'{date_m.group(1)} 行事報告'

        if new_title and new_title != current_title:
            new_title = new_title.replace('"', '\\"')
            content = content.replace(f'title: "{current_title}"', f'title: "{new_title}"')
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed += 1
            print(f'  {md_file.name}: "{current_title}" -> "{new_title}"')

    print(f'\nFixed {fixed} titles')


if __name__ == '__main__':
    main()
