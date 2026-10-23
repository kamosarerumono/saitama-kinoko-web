"""Bounded regressions for PR14 review 5631148385; synthetic inputs only."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from scripts import check_legacy_html as check
from tests import test_legacy_html_checks as fixtures
from tests.test_legacy_html_checks import document


class DeclarationRegressions(unittest.TestCase):
    def test_charset_lookalikes_are_not_declarations(self):
        for marker in ('<!-- charset=UTF-8 -->', '<style>p{content:"charset=UTF-8"}</style>',
                       '<script>var x="charset=UTF-8";</script>', '<title>charset=UTF-8</title>'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                check.decode_document(('<html><head>' + marker + '</head><body>X</body></html>').encode())
        for body in ('charset=UTF-8', '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                check.decode_document(('<html><head></head><body>' + body + '</body></html>').encode())

    def test_active_head_meta_and_charset_aliases(self):
        for label, codec in (('UTF-8', 'utf-8'), ('utf8', 'utf-8'), ('Shift_JIS', 'cp932'),
                             ('windows-31j', 'cp932'), ('CP932', 'cp932')):
            with self.subTest(label=label):
                raw = document('観察会').decode().replace('UTF-8', label).encode(codec)
                self.assertIn('観察会', check.decode_document(raw)[0])
        raw = document().replace(b'<head>', b'<head><!-- charset=CP932 -->')
        self.assertEqual(check.decode_document(raw)[1], 'utf-8')
        self.assertEqual(check.decode_document(b'\xef\xbb\xbf' + document())[1], 'utf-8')

    def test_invalid_duplicate_and_conflicting_charset_meta(self):
        original = b'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
        variants = [b'<meta charset="UTF-8">', b'<meta http-equiv="Content-Type" content>',
                    b'<meta http-equiv="Content-Type" content="text/plain; charset=UTF-8">',
                    b'<meta http-equiv="Content-Type" content="text/html; charset=unknown">',
                    b'<meta http-equiv="Content-Type" content="text/html; charset=">',
                    b'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8; charset=CP932">',
                    original + original.replace(b'UTF-8', b'CP932'),
                    b'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" content="text/html; charset=CP932">']
        for replacement in variants:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                check.decode_document(document().replace(original, replacement))

    def test_only_active_prolog_doctype_is_accepted(self):
        declaration = document().split(b'<html>')[0]
        for raw in (document().replace(declaration, b''),
                    document().replace(declaration, b'<!-- ' + declaration + b' -->'),
                    document().replace(declaration, b'<!DOCTYPE html>'),
                    document() + declaration, document().replace(declaration, b'') + declaration):
            with self.subTest(raw=raw):
                result = check.analyze(raw, 'reikai/fixture.html', set())
                self.assertIn('unsupported_doctype', {x['kind'] for x in result['issues']})
        self.assertEqual(check.analyze(document(), 'reikai/fixture.html', set())['doctype'], 'HTML4.01 Transitional')
        with self.assertRaises(ValueError):  # Visible pre-header text invalidates the charset meta first.
            check.analyze(b'Visible text' + document(), 'reikai/fixture.html', set())

    def test_valid_doctype_system_identifier_and_implied_head(self):
        raw = document().replace(b'//EN">', b'//EN" "https://www.w3.org/TR/html401/loose.dtd">', 1)
        self.assertEqual(check.analyze(raw, 'reikai/fixture.html', set())['doctype'], 'HTML4.01 Transitional')
        self.assertEqual(check.decode_document(document().replace(b'<head>', b''))[1], 'utf-8')

    def test_public_identifier_is_exact_while_keywords_are_case_insensitive(self):
        lower_keywords = document().replace(b'DOCTYPE HTML PUBLIC', b'doctype html public', 1)
        self.assertEqual(check.analyze(lower_keywords, 'reikai/fixture.html', set())['doctype'], 'HTML4.01 Transitional')
        wrong_fpi = document().replace(b'-//W3C//DTD HTML 4.01 Transitional//EN', b'-//w3c//dtd html 4.01 transitional//en')
        self.assertIn('unsupported_doctype', {x['kind'] for x in check.analyze(wrong_fpi, 'reikai/fixture.html', set())['issues']})

    def test_utf8_bom_conflicting_with_cp932_is_explicitly_rejected(self):
        raw = b'\xef\xbb\xbf' + document().replace(b'UTF-8', b'CP932')
        with self.assertRaisesRegex(ValueError, 'BOM.*conflict'):
            check.decode_document(raw)


class AttributeURLRegressions(unittest.TestCase):
    def analyze(self, body='', style='', available=None):
        return check.analyze(document(body, style), 'reikai/fixture.html', available or set())

    def test_valueless_required_attributes_are_rejected(self):
        result = self.analyze('<img src alt><script type></script>', '<style type>p{color:red}</style>')
        self.assertEqual({x['detail'] for x in result['issues'] if x['kind'] == 'valueless_required_attribute'},
                         {'img.src', 'img.alt', 'style.type', 'script.type'})

    def test_empty_alt_and_boolean_attribute_are_not_overrestricted(self):
        result = self.analyze('<img src="x.jpg" alt="" ismap>', available={'public/reikai/x.jpg'})
        self.assertEqual(result['issues'], [])

    def test_other_html4_url_attributes_use_exact_distribution_paths(self):
        result = self.analyze('<object data="missing.swf"></object><form action="missing.cgi"></form>'
                              '<img src="photo.jpg" alt="" longdesc="description.html">'
                              '<blockquote cite="source.html">X</blockquote><input src="button.jpg">')
        self.assertEqual({path for kind, path in result['missing']},
                         {'public/reikai/' + name for name in
                          ('missing.swf', 'missing.cgi', 'photo.jpg', 'description.html', 'source.html', 'button.jpg')})
        raw = document().replace(b'<body>', b'<body background="paper.jpg">')
        self.assertIn(('body:background', 'public/reikai/paper.jpg'),
                      check.analyze(raw, 'reikai/fixture.html', set())['missing'])

    def test_supported_uri_attributes_resolve_without_fetch(self):
        result = self.analyze('<object data="../asset.bin"></object><form action="/submit.cgi"></form>'
                              '<a href="https://example.invalid/">Web</a><a href="mailto:x@example.invalid">Mail</a>'
                              '<a href="#section">Fragment</a>',
                              available={'public/asset.bin', 'public/submit.cgi'})
        self.assertEqual(result['missing'], {})
        self.assertEqual(result['external_not_fetched'], 2)
        self.assertEqual(result['js_scope'], 'NOT_APPLICABLE_NO_JS_TS')

    def test_base_semantics_are_unverified_without_wrong_local_probes(self):
        for base in ('../assets/', '/assets/', 'https://example.invalid/assets/'):
            probed = []
            result = self.analyze('<img src="x.jpg" alt="">', '<base href="' + base + '">',
                                  available=lambda path: probed.append(path) or True)
            with self.subTest(base=base):
                self.assertTrue(result['unverified_references'])
                self.assertEqual(probed, [])

    def test_object_codebase_archive_and_param_ref_are_unverified(self):
        result = self.analyze('<object codebase="assets/" data="x.bin" archive="a.jar b.jar">'
                              '<param name="movie" valuetype="ref" value="movie.bin"></object>'
                              '<applet code="X.class" archive="a.jar,b.jar"></applet>')
        self.assertTrue(result['unverified_references'])
        self.assertEqual(result['missing'], {})

    def test_javascript_urls_are_active_and_never_executed(self):
        for uri in ('javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'java&#x09;script:alert(1)', 'vbscript:MsgBox(1)'):
            with self.subTest(uri=uri):
                result = self.analyze('<a href="' + uri + '">X</a>')
                self.assertEqual(result['js_scope'], 'REQUIRES_RELATED_JS_CHECK')
                self.assertIn('executable_url', {x['kind'] for x in result['issues']})
                self.assertEqual(result['external_not_fetched'], 0)

    def test_embedded_and_refresh_content_do_not_claim_no_script_or_resolution(self):
        result = self.analyze('<object data="data:text/html,script"></object>',
                              '<meta http-equiv="refresh" content="0; url=javascript:alert(1)">')
        self.assertTrue(result['unverified_references'])
        self.assertEqual(result['js_scope'], 'REQUIRES_RELATED_JS_CHECK')


class GitCompatibilityRegressions(unittest.TestCase):
    def test_git_243_stops_with_requirement_before_object_read(self):
        with mock.patch.object(check.subprocess, 'check_output', return_value=b'git version 2.43.0\n') as call:
            with self.assertRaisesRegex(ValueError, r'Git 2\.48'):
                check.git(Path('.'), 'show', 'HEAD:page.html')
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0], ['git', '--version'])

    def test_git_248_read_keeps_lazy_fetch_and_transport_guards(self):
        with mock.patch.object(check.subprocess, 'check_output', side_effect=[b'git version 2.48.0\n', b'local']) as call:
            self.assertEqual(check.git(Path('.'), 'show', 'HEAD:page.html'), b'local')
        command = call.call_args.args[0]
        self.assertIn('--no-lazy-fetch', command)
        self.assertIn('protocol.allow=never', command)
        self.assertEqual(call.call_args.kwargs['env']['GIT_ALLOW_PROTOCOL'], '')
        self.assertEqual(call.call_args.kwargs['env']['GIT_NO_LAZY_FETCH'], '1')

    def test_unsupported_git_cli_reports_environment_failure(self):
        output = io.StringIO()
        with mock.patch.object(check.subprocess, 'check_output', return_value=b'git version 2.43.0\n'), contextlib.redirect_stdout(output):
            code = check.main(['--baseline', 'HEAD'])
        self.assertEqual(code, 1)
        self.assertIn('Git 2.48', json.loads(output.getvalue())['error'])


class DistributionRegressions(unittest.TestCase):
    setUp = fixtures.GitReferenceTests.setUp
    git = fixtures.GitReferenceTests.git
    write = fixtures.GitReferenceTests.write

    def test_unverified_base_cannot_report_all_references_resolved(self):
        for path in check.SCOPES:
            self.write(path, document('<img src="x.jpg" alt="">', '<base href="../assets/">'))
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-qm', 'Base fixture')
        result = check.run(self.root, 'HEAD')
        self.assertEqual(result['distribution'], 'UNVERIFIED_REFERENCE_SEMANTICS')
        self.assertGreater(result['unverified_reference_occurrences'], 0)

    def test_missing_promisor_blob_fails_without_fetching(self):
        # Construct a missing-object tree; do not delete Windows read-only Git objects.
        tree = subprocess.check_output(['git', '-C', str(self.root), 'mktree', '--missing'],
                                       input=b'100644 blob ' + b'1' * 40 + b'\tmissing.html\n').decode().strip()
        self.git('config', 'remote.origin.url', 'https://example.invalid/never-contact')
        self.git('config', 'remote.origin.promisor', 'true')
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            check.git(self.root, 'show', tree + ':missing.html')
        self.assertNotIn(b'fetch', failure.exception.stderr.lower())


if __name__ == '__main__':
    unittest.main()
