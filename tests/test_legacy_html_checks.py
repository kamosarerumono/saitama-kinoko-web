import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import check_legacy_html as check


def document(body='', style=''):
    return ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">'
            '<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
            '<title>Fixture</title>' + style + '</head><body>' + body + '</body></html>').encode()


class DiagnosticTests(unittest.TestCase):
    def analyze(self, body='', style=''):
        return check.analyze(document(body, style), 'reikai/fixture.html', set())

    def test_declared_utf8_and_cp932_decode_strictly(self):
        self.assertEqual(check.decode_document(document('観察会'))[1], 'utf-8')
        cp = document('観察会').decode().replace('UTF-8', 'Shift_JIS').encode('cp932')
        self.assertIn('観察会', check.decode_document(cp)[0])

    def test_invalid_utf8_is_not_replaced_or_guessed(self):
        with self.assertRaises(UnicodeError):
            check.decode_document(document() + b'\xff')

    def test_html4_table_height_rejected_but_cell_height_and_font_allowed(self):
        result = self.analyze('<center><table height="20"><tr><td height="20"><font color="red">X</font></td></tr></table></center>')
        self.assertEqual([(x['kind'], x['detail']) for x in result['issues']],
                         [('invalid_scoped_html4_attribute', 'table.height')])

    def test_html5_element_and_duplicate_attribute_are_reported(self):
        result = self.analyze('<main><img src="x.jpg" alt="X" alt="Y"></main>')
        self.assertEqual({x['kind'] for x in result['issues']},
                         {'not_html4_transitional_element', 'duplicate_attribute'})

    def test_required_style_type_and_image_alt_are_checked(self):
        result = self.analyze('<img src="x.jpg">', '<style>body{color:red}</style>')
        self.assertEqual({x['detail'] for x in result['issues']}, {'style.type', 'img.alt'})

    def test_html4_optional_table_end_tags_are_accepted(self):
        result = self.analyze('<table><tbody><tr><td>One<td>Two</table>')
        self.assertEqual(result['issues'], [])

    def test_unclosed_required_element_and_nested_anchor_reported(self):
        result = self.analyze('<a href="x"><a href="y">Text</a>')
        self.assertIn('nested_anchor', {x['kind'] for x in result['issues']})
        self.assertIn('missing_end_before_parent', {x['kind'] for x in result['issues']})

    def test_css_quotes_comments_and_unbalanced_syntax(self):
        self.assertTrue(check.css_delimiters('/* { */ p{content:"}";width:calc(100% - 2px)}'))
        self.assertFalse(check.css_delimiters('p{color:red'))
        self.assertFalse(check.css_delimiters('/* not closed'))

    def test_local_escape_reported_and_external_not_fetched(self):
        result = self.analyze('<a href="../../../private">X</a><a href="https://example.invalid/">Y</a>')
        self.assertEqual(result['issues'][0]['kind'], 'reference_escapes_site_root')
        self.assertEqual(result['external_not_fetched'], 1)


class GitReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve(strict=True)
        if self.root.parent != Path(tempfile.gettempdir()).resolve(strict=True) or self.root.is_symlink():
            raise AssertionError('Synthetic Git fixture is outside its exact temporary parent')
        self.addCleanup(self.temp.cleanup)
        self.git('init', '-q')
        for path in check.SCOPES:
            self.write(path, document())
        first = next(iter(check.SCOPES))
        self.write(first, document('<img src="known-missing.jpg" alt="X">'))
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                 'commit', '-qm', 'Synthetic baseline')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, path, data):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def test_known_missing_is_incomplete_and_never_full_acceptance(self):
        before = {p: (self.root / p).read_bytes() for p in check.SCOPES}
        result = check.run(self.root, 'HEAD')
        self.assertEqual(result['distribution'], 'INCOMPLETE')
        self.assertEqual(result['new_missing_occurrences'], 0)
        self.assertEqual(result['strict_sgml_conformance'], 'NOT_RUN')
        self.assertEqual(result['browser_mobile'], 'NOT_RUN')
        self.assertEqual(before, {p: (self.root / p).read_bytes() for p in check.SCOPES})

    def test_same_missing_count_with_new_target_is_a_regression(self):
        first = next(iter(check.SCOPES))
        self.write(first, document('<img src="different-missing.jpg" alt="X">'))
        result = check.run(self.root, 'HEAD')
        self.assertEqual(result['missing_occurrences'], 1)
        self.assertEqual(result['new_missing_occurrences'], 1)
        self.assertEqual(result['local_regression_check'], 'FAIL')

    def test_tracked_asset_missing_from_worktree_is_not_resolved(self):
        first = next(iter(check.SCOPES))
        self.write(first, document('<img src="present.jpg" alt="X">'))
        self.write('public/reikai/present.jpg', b'synthetic bytes, not an image decode test')
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                 'commit', '-qm', 'Known synthetic asset')
        (self.root / 'public/reikai/present.jpg').unlink()
        result = check.run(self.root, 'HEAD')
        self.assertEqual(result['new_missing_occurrences'], 1)

    def test_cli_failure_is_nonzero_and_not_conformance_pass(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = check.main(['--repo', str(self.root), '--baseline', 'does-not-exist'])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())['strict_sgml_conformance'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
