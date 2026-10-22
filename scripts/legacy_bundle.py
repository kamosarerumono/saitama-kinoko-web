"""Prepare a new report only. No network, credentials, site edits, or publication."""
from __future__ import annotations
import argparse
import datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from mail_draft import sha, encoded, readback

HOST = 'ippon.sakura.ne.jp'
MAX_BYTES = 16 * 1024 * 1024

def relative_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('relative path required')
    parts = name.split('/')
    if any(p in ('', '.', '..') for p in parts) or name.startswith('/'):
        raise ValueError('unsafe relative path')
    root = Path(root).resolve(strict=True)
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink(): raise ValueError('symlink is not supported')
    if not path.resolve().is_relative_to(root): raise ValueError('path escapes root')
    return path

def bounded(path):
    if path.stat().st_size > MAX_BYTES: raise ValueError('file too large')
    return path.read_bytes()

class SafeBody(HTMLParser):
    """Preserve ordinary report HTML, rejecting active content and unknown assets."""
    tags = set('p br div span h2 h3 h4 table thead tbody tr th td ul ol li strong em b i blockquote hr a img figure figcaption code pre'.split())
    attrs = set('class id style title alt width height loading colspan rowspan scope src href'.split())
    def __init__(self, image_dir):
        super().__init__(convert_charrefs=False)
        self.image_dir = image_dir
        self.images = {}
        self.output = []
        self.in_figcaption = 0
        self.row_buffer = None
        self.row_headers = []
        self.cell_kind = None
        self.cell_text = []
    def emit(self, fragment):
        (self.row_buffer if self.row_buffer is not None else self.output).append(fragment)
    def image(self, url):
        if not re.fullmatch(r'/reikai/[0-9]{4}/[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png)', url):
            raise ValueError('only reviewed local JPEG/PNG paths are supported')
        self.images[url] = self.image_dir + '/' + PurePosixPath(url).name
        return self.images[url]
    def handle_starttag(self, tag, attrs):
        if tag not in self.tags: raise ValueError('unsupported active/structural HTML tag')
        if tag == 'tr' and self.row_buffer is None:
            self.row_buffer = []
            self.row_headers = []
        if tag in ('th', 'td') and self.row_buffer is not None:
            self.cell_kind = tag
            self.cell_text = []
        clean = []
        if len({k for k, _ in attrs}) != len(attrs): raise ValueError('duplicate HTML attribute')
        for key, value in attrs:
            if key not in self.attrs or value is None: raise ValueError('unsupported HTML attribute')
            if key == 'style' and re.search(r'url|expression|@|[\\<>]', value, re.I):
                raise ValueError('active CSS is not supported')
            if key == 'src':
                if tag != 'img': raise ValueError('unsupported source')
                value = self.image(value)
            if tag == 'img' and key == 'alt':
                value = without_photographer(value).strip()
            if key == 'href':
                if value.startswith('/reikai/') and value.endswith(('.jpg', '.jpeg', '.png')):
                    value = self.image(value)
                elif not (value.startswith('#') or re.fullmatch(r'https://[^\s<>"\x00-\x1f]+', value)):
                    raise ValueError('unsupported link')
            clean.append((key, value))
        if tag == 'img' and not any(k == 'src' for k, _ in clean): raise ValueError('image source required')
        self.emit('<' + tag + ''.join(' '+k+'="'+html.escape(v, quote=True)+'"' for k,v in clean) + '>')
        if tag == 'figcaption': self.in_figcaption += 1
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs)
    def handle_endtag(self, tag):
        if tag not in self.tags: raise ValueError('unsupported closing tag')
        if tag in ('th', 'td') and self.cell_kind == tag:
            if tag == 'th': self.row_headers.append(''.join(self.cell_text))
            self.cell_kind = None
            self.cell_text = []
        self.emit('</'+tag+'>')
        if tag == 'tr' and self.row_buffer is not None:
            labels = {re.sub(r'[\s:：()（）【】\[\]]', '', html.unescape(x)) for x in self.row_headers}
            photographer_labels = {'写真', '撮影', '撮影者', '写真撮影', '写真提供', '撮影者氏名'}
            if not labels.intersection(photographer_labels): self.output.append(''.join(self.row_buffer))
            self.row_buffer = None
            self.row_headers = []
        if tag == 'figcaption': self.in_figcaption = max(0, self.in_figcaption - 1)
    def handle_data(self, data):
        data = without_photographer(data)
        if self.cell_kind is not None: self.cell_text.append(data)
        self.emit(html.escape(data, quote=False))
    def handle_entityref(self, name):
        fragment = '&'+name+';'
        if self.cell_kind is not None: self.cell_text.append(html.unescape(fragment))
        self.emit(fragment)
    def handle_charref(self, name):
        fragment = '&#'+name+';'
        if self.cell_kind is not None: self.cell_text.append(html.unescape(fragment))
        self.emit(fragment)
    def handle_comment(self, data): raise ValueError('review/remove source HTML comments first')
    def handle_decl(self, decl): raise ValueError('document declarations are not article content')

STYLE = 'body{max-width:1100px;margin:auto;padding:20px;font-family:sans-serif;line-height:1.8;background:#f7f6ee;color:#222}table{border-collapse:collapse;width:100%}th,td{border:1px solid #aaa;padding:8px;text-align:left;overflow-wrap:anywhere}img{max-width:100%}'

def without_photographer(value):
    """Remove supported photographer credits without trimming body whitespace."""
    value = re.sub(r'[（(]\s*(?:撮影者?|写真提供)\s*[:：]?\s*[^()（）]*[）)]', '', value)
    return value

def render_markdown(source, node='node'):
    proc = subprocess.run([node, str(Path(__file__).with_name('render_legacy_source.mjs'))],
                          input=source, capture_output=True, check=False)
    if proc.returncode: raise ValueError('Astro Markdown renderer failed; source preserved')
    return json.loads(proc.stdout)

def prepare(spec, source_root, input_root, output, node='node'):
    if spec.get('schema_version') != 1 or not spec.get('review_reference'):
        raise ValueError('explicit reviewed source reference required')
    source_name = spec['source']['path']
    if not re.fullmatch(r'src/content/reikai/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+\.md', source_name):
        raise ValueError('existing reikai Markdown source required')
    source = bounded(relative_file(source_root, source_name))
    if sha(source) != spec['source']['sha256']: raise ValueError('reviewed source changed')
    # A prepare-draft bundle is accepted only with its existing holds cleared by
    # its own review workflow. This does not alter or waive Intake holds.
    if spec.get('draft_review'):
        review = json.loads(bounded(relative_file(source_root, spec['draft_review'])))
        if review.get('holds') or review.get('status') != 'review_required' or review.get('operation') != 'create':
            raise ValueError('draft is held or is not a new report')
        if not any(x['path'] == source_name and x['sha256'] == sha(source) for x in review['files']):
            raise ValueError('draft does not bind this source')
    rendered = render_markdown(source, node)
    meta = rendered['metadata']; title = meta['title']; date = str(meta['date'])[:10]
    day = datetime.date.fromisoformat(date)
    if not isinstance(title, str) or not title.strip() or len(title)>300 or any(ord(c)<32 for c in title):
        raise ValueError('invalid title')
    if not PurePosixPath(source_name).name.startswith(date+'-'): raise ValueError('source date mismatch')
    slug = spec['legacy_slug']
    if not re.fullmatch(day.strftime('%y%m%d')+r'_[a-z0-9_-]{1,60}', slug): raise ValueError('invalid legacy slug')
    year = str(day.year-1 if day.month<4 else day.year); article = f'reikai/{year}/{slug}.html'
    image_dir = f'images_{slug}'
    parser = SafeBody(image_dir); parser.feed(rendered['html']); parser.close()
    if set(spec.get('assets',{}))!=set(parser.images): raise ValueError('reviewed asset list must match article exactly')
    files = {}; rows = []
    for src, dest in sorted(parser.images.items()):
        data = bounded(relative_file(source_root, 'public'+src))
        if sha(data)!=spec['assets'][src]: raise ValueError('reviewed image changed')
        if not (data.startswith(b'\xff\xd8\xff') if src.endswith(('.jpg','.jpeg')) else data.startswith(b'\x89PNG\r\n\x1a\n')):
            raise ValueError('image signature mismatch')
        path = f'reikai/{year}/{dest}'
        if path in files: raise ValueError('image basename collision')
        files[path] = data
        rows.append({'path':path,'role':'image','before_sha256':None,'sha256':sha(data),'bytes':len(data)})
    if len(rows)>1000: raise ValueError('too many images')
    details=[('開催日',date)]
    for key,label in [('location','場所'),('meetingPoint','集合場所'),('participants','参加者'),('organizer','世話人'),('reporter','報告者')]:
        if key in meta:
            if not isinstance(meta[key],(str,int,float)):raise ValueError('invalid report metadata')
            details.append((label,str(meta[key])))
    table='<table><tbody>'+''.join('<tr><th>'+k+'</th><td>'+html.escape(v)+'</td></tr>' for k,v in details)+'</tbody></table>'
    page = '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+STYLE+'</style></head><body><nav><a href="../../index.htm">ホーム</a> / <a href="../'+year+'reikaihoukoku.html">'+year+'年例会報告</a></nav><h1>'+html.escape(title)+'</h1>'+table+''.join(parser.output)+'</body></html>\n'
    files[article] = page.encode('utf-8')
    rows.append({'path':article,'role':'article','before_sha256':None,'sha256':sha(files[article]),'bytes':len(files[article])})
    baselines = {}
    for role, path in [('annual',f'reikai/{year}reikaihoukoku.html'),('top','index.htm')]:
        cfg = spec['navigation'][role]; data = bounded(relative_file(input_root,cfg['file']))
        if sha(data)!=cfg['sha256']: raise ValueError('navigation snapshot changed')
        enc=cfg['encoding']
        if enc not in ('utf-8','cp932'): raise ValueError('unsupported navigation encoding')
        anchor=cfg['anchor'].encode(enc)
        if not anchor or data.count(anchor)!=1: raise ValueError('navigation anchor must be unique')
        if slug.encode('ascii') in data: raise ValueError('existing report: only new reports supported')
        if role=='annual':
            addition=f'<a href="{year}/{slug}.html">■ {html.escape(title)}</a><br><br>\n'
        else:
            addition=f'&nbsp;&nbsp;&nbsp;&nbsp;・{day.month}月{day.day}日の{html.escape(title)}を掲載しました。<br>\n'
        # Byte-level insertion preserves every existing byte outside the new line.
        files[path]=data.replace(anchor,addition.encode(enc,errors='xmlcharrefreplace')+anchor,1)
        baselines[path]=data
        rows.append({'path':path,'role':role,'before_sha256':sha(data),'sha256':sha(files[path]),'bytes':len(files[path])})
    manifest={'schema_version':1,'host':HOST,'remote_root':'/home/ippon/www','title':title,'date':date,'legacy_year':int(year),
              'legacy_slug':slug,'source_sha256':sha(source),'review_reference':spec['review_reference'],
              'auto_publish':False,'files':rows}
    all_files={'stage/'+p:b for p,b in files.items()}
    all_files.update({'baseline/'+p:b for p,b in baselines.items()})
    all_files['manifest.json']=encoded(manifest)
    python=str(Path(sys.executable).resolve());publisher=str(Path(__file__).with_name('legacy_publish.py').resolve())
    if any(ch in python+publisher for ch in '%!&|<>^\r\n"'): raise ValueError('unsupported launcher path')
    launcher='@echo off\r\nchcp 65001 >nul\r\nset "PYTHONIOENCODING=utf-8"\r\n"'+python+'" "'+publisher+'" --bundle "%~dp0." --manifest-sha '+sha(all_files['manifest.json'])+' --publish\r\nset "publish_exit=%ERRORLEVEL%"\r\npause\r\nexit /b %publish_exit%\r\n'
    all_files['PUBLISH_REPORT.cmd']=launcher.encode('utf-8')
    output=Path(output)
    if output.exists():
        if output.is_symlink(): raise ValueError('output symlink')
        readback(output,all_files)
    else:
        output.mkdir(parents=True,exist_ok=False)
        for name,data in all_files.items():
            out=relative_file(output,name);out.parent.mkdir(parents=True,exist_ok=True)
            with out.open('xb') as stream:stream.write(data)
        readback(output,all_files)
    return {'bundle':str(output.resolve()),'manifest_sha256':sha(all_files['manifest.json']),
            'file_count':len(rows),'auto_publish':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',required=True);parser.add_argument('--source-root',required=True)
    parser.add_argument('--input-root',required=True);parser.add_argument('--output',required=True);parser.add_argument('--node',default='node')
    args=parser.parse_args()
    result=prepare(json.loads(Path(args.spec).read_text(encoding='utf-8')),args.source_root,args.input_root,args.output,args.node)
    print(json.dumps(result,ensure_ascii=False))
