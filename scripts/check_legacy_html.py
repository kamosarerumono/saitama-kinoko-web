"""Read-only, three-page HTML4 diagnostics; never a full SGML acceptance gate."""
from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
from typing import Callable
from urllib.parse import unquote, urlsplit


SCOPES = {
    'public/reikai/2019reikaihoukoku.html': 'reikai/2019reikaihoukoku.html',
    'public/reikai/2020reikaihoukoku.html': 'reikai/2020reikaihoukoku.html',
    'docs/plans/kawagoe2026/260628_kawagoe.html': 'reikai/2026/260628_kawagoe.html',
}
# HTML4 Transitional names, not HTML5's element/content model. Attribute checks
# below deliberately cover TABLE, IMG, and required STYLE/SCRIPT attributes only.
# Normative source: https://www.w3.org/TR/html401/sgml/loosedtd.html
ELEMENTS = set('a abbr acronym address applet area b base basefont bdo big blockquote body br button caption center cite code col colgroup dd del dfn dir div dl dt em fieldset font form h1 h2 h3 h4 h5 h6 head hr html i iframe img input ins isindex kbd label legend li link map menu meta noframes noscript object ol optgroup option p param pre q s samp script select small span strike strong style sub sup table tbody td textarea tfoot th thead title tr tt u ul var'.split())
VOID = set('area base basefont br col hr img input isindex link meta param'.split())
OPTIONAL_END = set('html head body p li dt dd option thead tfoot tbody tr th td colgroup'.split())
COMMON = set('id class style title lang dir onclick ondblclick onmousedown onmouseup onmouseover onmousemove onmouseout onkeypress onkeydown onkeyup'.split())
ATTRIBUTES = {
    'table': COMMON | set('summary width border frame rules cellspacing cellpadding align bgcolor datapagesize'.split()),
    'img': COMMON | set('src alt longdesc name height width usemap ismap align border hspace vspace'.split()),
}


def decode_document(data: bytes) -> tuple[str, str]:
    match = re.search(br'charset\s*=\s*[\"\']?([A-Za-z0-9_-]+)', data[:8192], re.I)
    if not match:
        raise ValueError('charset declaration missing; no guessed decoding')
    declared = match.group(1).decode('ascii').lower()
    codec = {'utf-8': 'utf-8-sig', 'utf8': 'utf-8-sig', 'shift_jis': 'cp932',
             'shift-jis': 'cp932', 'sjis': 'cp932', 'windows-31j': 'cp932', 'cp932': 'cp932'}.get(declared)
    if codec is None:
        raise ValueError('unsupported declared charset: ' + declared)
    return data.decode(codec, errors='strict'), declared


def css_delimiters(text: str) -> bool:
    """Lexical delimiters only; not CSS grammar, cascade or rendering validation."""
    stack, quote, comment, escaped, index = [], '', False, False, 0
    pairs = {'}': '{', ')': '(', ']': '['}
    while index < len(text):
        char = text[index]
        if comment:
            if text[index:index + 2] == '*/':
                comment = False
                index += 2
                continue
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = ''
        elif text[index:index + 2] == '/*':
            comment = True
            index += 2
            continue
        elif char in '\"\'':
            quote = char
        elif char in '{([':
            stack.append(char)
        elif char in '})]':
            if not stack or stack.pop() != pairs[char]:
                return False
        index += 1
    return not (stack or quote or comment)


class Diagnostics(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.issues, self.references, self.stack, self.styles = [], [], [], []
        self.script_count, self.event_attributes = 0, 0
        self.feed(text)
        self.close()
        for tag in reversed(self.stack):
            if tag not in OPTIONAL_END:
                self.issue('unclosed_required_end_tag', tag)

    def issue(self, kind, detail):
        self.issues.append({'line': self.getpos()[0], 'kind': kind, 'detail': detail})

    def handle_starttag(self, tag, attrs):
        if tag not in ELEMENTS:
            self.issue('not_html4_transitional_element', tag)
        counts = Counter(name for name, value in attrs)
        for name, count in counts.items():
            if count > 1:
                self.issue('duplicate_attribute', tag + '.' + name)
            if tag in ATTRIBUTES and name not in ATTRIBUTES[tag]:
                self.issue('invalid_scoped_html4_attribute', tag + '.' + name)
        values = dict(attrs)
        for name in {'img': ['src', 'alt'], 'style': ['type'], 'script': ['type']}.get(tag, []):
            if name not in values:
                self.issue('missing_required_attribute', tag + '.' + name)
        if tag == 'a' and 'a' in self.stack:
            self.issue('nested_anchor', 'a inside a')
        # Respect optional table/list end tags. This is a limited balancing
        # diagnostic, not the SGML DTD's complete content model.
        closing = {'td': {'td', 'th'}, 'th': {'td', 'th'},
                   'tr': {'td', 'th', 'tr'},
                   'tbody': {'td', 'th', 'tr', 'tbody', 'thead', 'tfoot'},
                   'thead': {'td', 'th', 'tr', 'tbody', 'thead', 'tfoot'},
                   'tfoot': {'td', 'th', 'tr', 'tbody', 'thead', 'tfoot'},
                   'li': {'li'}, 'dt': {'dt', 'dd'}, 'dd': {'dt', 'dd'}, 'option': {'option'}}
        while self.stack and self.stack[-1] in closing.get(tag, set()):
            self.stack.pop()
        if tag not in VOID:
            self.stack.append(tag)
        for name, value in attrs:
            if name.startswith('on'):
                self.event_attributes += 1
            if name == 'style' and value is not None and not css_delimiters(value):
                self.issue('unbalanced_inline_css', tag)
            if value is not None and (name == 'src' or (tag in {'a', 'link'} and name == 'href')):
                self.references.append((tag + ':' + name, value))
        if tag == 'script':
            self.script_count += 1

    def handle_endtag(self, tag):
        if tag not in self.stack:
            self.issue('unmatched_end_tag', tag)
            return
        while self.stack:
            current = self.stack.pop()
            if current == tag:
                break
            if current not in OPTIONAL_END:
                self.issue('missing_end_before_parent', current + ' before /' + tag)

    def handle_data(self, text):
        if self.stack and self.stack[-1] == 'style':
            self.styles.append(text)
            if not css_delimiters(text):
                self.issue('unbalanced_style_css', 'style')


def analyze(data: bytes, logical_path: str, available: set[str] | Callable[[str], bool]) -> dict:
    text, charset = decode_document(data)
    parsed = Diagnostics(text)
    doctype = re.search(r'<!DOCTYPE\s+HTML\s+PUBLIC\s+[\"\']-//W3C//DTD HTML 4\.01 Transitional//EN[\"\'](?:\s+[\"\'][^\"\']+[\"\'])?\s*>', text, re.I)
    if not doctype:
        parsed.issue('unsupported_doctype', 'Expected HTML4.01 Transitional; no HTML5 conversion')
    missing, local_count, external_count = Counter(), 0, 0
    for kind, value in parsed.references:
        u = urlsplit(value)
        if u.scheme or u.netloc:
            external_count += 1
            continue
        if not u.path:
            continue  # fragment-only checks are not part of this entry
        try:
            path = unquote(u.path, errors='strict')
        except UnicodeDecodeError:
            parsed.issue('unverified_url_encoding', value)
            continue
        path = posixpath.normpath(posixpath.join(posixpath.dirname(logical_path), path)) if not path.startswith('/') else posixpath.normpath(path.lstrip('/'))
        if path == '..' or path.startswith('../') or '\\' in path:
            parsed.issue('reference_escapes_site_root', value)
            continue
        local_count += 1
        git_path = 'public/' + path
        resolved = available(git_path) if callable(available) else git_path in available
        if not resolved:
            missing[(kind, git_path)] += 1
    return {'charset': charset, 'issues': parsed.issues, 'missing': missing,
            'local_references': local_count, 'external_not_fetched': external_count,
            'js_scope': 'REQUIRES_RELATED_JS_CHECK' if parsed.script_count or parsed.event_attributes else 'NOT_APPLICABLE_NO_JS_TS',
            'doctype': 'HTML4.01 Transitional' if doctype else 'UNSUPPORTED'}


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '--no-lazy-fetch', '--no-optional-locks', '--no-replace-objects', '-C', str(root), *args], stderr=subprocess.PIPE)


def run(root: Path, baseline: str) -> dict:
    root = root.resolve(strict=True)
    revision = git(root, 'rev-parse', '--verify', '--end-of-options', baseline + '^{commit}').decode().strip()
    baseline_paths = set(git(root, 'ls-tree', '-r', '--name-only', '-z', revision).decode('utf-8', errors='surrogateescape').split('\0'))
    tracked = set(git(root, 'ls-files', '-z').decode('utf-8', errors='surrogateescape').split('\0'))
    def available(path: str) -> bool:
        # Probe only references encountered in the three selected pages, not
        # every public file. Git tree/index name lists remain metadata only.
        target = root / path
        return path in tracked and target.resolve().is_relative_to(root) and target.is_file() and not target.is_symlink()
    pages, issues, regressions = [], 0, 0
    for source, logical in SCOPES.items():
        path = root / source
        if source not in tracked or not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError('Selected source is not a regular tracked file within the checkout: ' + source)
        current = analyze(path.read_bytes(), logical, available)
        old = analyze(git(root, 'show', revision + ':' + source), logical, baseline_paths)
        added = current['missing'] - old['missing']
        removed = old['missing'] - current['missing']
        def entries(counter):
            return [{'kind': kind, 'required_git_path': p, 'occurrences': n} for (kind, p), n in sorted(counter.items())]
        pages.append({'source': source, 'logical_legacy_path': logical,
                      **{k: v for k, v in current.items() if k != 'missing'},
                      'baseline_issues': old['issues'],
                      'missing_references': entries(current['missing']),
                      'new_missing_references': entries(added),
                      'resolved_since_baseline': entries(removed),
                      'missing_occurrences': sum(current['missing'].values())})
        issues += len(current['issues'])
        regressions += sum(added.values())
    missing = sum(p['missing_occurrences'] for p in pages)
    return {'baseline_commit': revision, 'selected_pages': len(pages), 'pages': pages,
            'blocking_subset_issues': issues, 'new_missing_occurrences': regressions,
            'distribution': 'INCOMPLETE' if missing else 'REFERENCES_RESOLVED_FOR_SELECTED_PAGES_ONLY',
            'missing_occurrences': missing,
            'local_regression_check': 'FAIL' if issues or regressions else 'OK_WITH_REMAINING_GATES',
            'strict_sgml_conformance': 'NOT_RUN',
            'sgml_tool_on_path': shutil.which('onsgmls') or shutil.which('nsgmls'),
            'required_sgml_components': ['OpenSP onsgmls', 'HTML4.decl', 'loose.dtd', 'HTML4.cat local catalog', 'HTMLlat1.ent', 'HTMLsymbol.ent', 'HTMLspecial.ent', 'verified input encoding configuration'],
            'attribute_scope': 'TABLE/IMG allowed attributes; IMG/STYLE/SCRIPT required attributes; duplicates. Other attributes/content models unverified.',
            'parser_scope': 'HTML4 element names and limited required-end balancing, with optional table/list end tags; not full SGML grammar.',
            'css_scope': 'Lexical delimiters only; full CSS grammar/cascade and CSS url/import dependencies NOT_CHECKED',
            'fragments': 'NOT_CHECKED', 'browser_mobile': 'NOT_RUN', 'network_requests': 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--baseline', required=True, help='Local Git revision; normally HEAD before changes. No fetch.')
    args = parser.parse_args(argv)
    try:
        report = run(args.repo, args.baseline)
    except (ValueError, UnicodeError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'local_regression_check': 'FAIL', 'error': str(exc), 'strict_sgml_conformance': 'NOT_RUN'}, ensure_ascii=True))
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return int(report['local_regression_check'] == 'FAIL')


if __name__ == '__main__':
    raise SystemExit(main())
