import base64
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mail_intake import Intake, digest, parse_eml
from mail_draft import prepare_draft, verify_draft
from test_mail_intake import CANDIDATES, META, eml


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = self.root / 'site'
        self.site.mkdir()
        self.store = Intake(self.root / 'private/db.sqlite', copy.deepcopy(CANDIDATES))
        # The older suite mutates its shared fixture; isolate this test input.
        self.store.candidates.pop('excluded_addresses', None)
        self.raw = eml('Original body\n<script>alert(1)</script>\n![external](https://example.test/a)')
        result = self.store.receive('one', 'body', self.raw, parse_eml(self.raw), META)
        self.selection = {
            'event_id': result['event_id'],
            'target': {'slug': '2026-09-15-synthetic', 'title': 'Synthetic report'},
            'body_source': {'account': 'one', 'message_id': 'body', 'source_hash': digest(self.raw)},
            'assets': [],
        }

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def prepare(self):
        result = prepare_draft(self.store, self.selection, self.site)
        path = Path(result['bundle'])
        return result, path, json.loads((path / 'review.json').read_text())

    def photo(self, data=b'\xff\xd8\xffsynthetic\xff\xd9', filename='../../a.jpg'):
        parsed = parse_eml(eml('Photo contribution'))
        parsed['attachments'] = [{'part_id': '1', 'filename': filename, 'mime': 'image/jpeg', 'data': data}]
        raw = b'synthetic photo envelope'
        self.store.receive('one', 'photo', raw, parsed, META)
        item = {'account': 'one', 'message_id': 'photo', 'source_hash': digest(raw), 'part_id': '1', 'sha256': digest(data), 'review_reference': 'synthetic image/privacy review'}
        self.selection['assets'] = [item]
        return data

    def test_prepare_is_immutable_private_and_escapes_mail(self):
        jpeg = self.photo()
        result, path, manifest = self.prepare()
        self.assertEqual(result['file_count'], 2)
        self.assertFalse(result['auto_publish'])
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(list(self.site.iterdir()), [])
        article = (path / manifest['target_path']).read_text()
        self.assertIn('title: "Synthetic report"', article)
        self.assertNotIn('<script>', article)
        self.assertIn('<div class="mail-body">', article)
        self.assertIn('![external](https://example.test/a)', article)
        self.assertNotIn('href=', article)
        self.assertNotIn('writer@example.test', article)
        self.assertEqual((path / f'public/reikai/2026/{digest(jpeg)}.jpg').read_bytes(), jpeg)
        self.assertEqual(manifest['sources'][0]['original_sha256'], digest(self.raw))
        self.assertTrue(self.prepare()[0]['duplicate'])
        self.assertTrue(verify_draft(self.store, result['bundle_id'], self.site)['verified'])
        for record in manifest['files']:
            self.assertEqual(digest((path / record['path']).read_bytes()), record['sha256'])
            self.assertEqual((path / record['path']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        (path / manifest['target_path']).write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            self.prepare()
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            verify_draft(self.store, result['bundle_id'], self.site)

    def test_holds_and_unreviewed_or_unsupported_assets_block_artifacts(self):
        self.photo()
        self.selection['assets'][0].pop('review_reference')
        result, path, manifest = self.prepare()
        self.assertIn('selected_asset_requires_review', result['holds'])
        self.assertEqual(result['file_count'], 0)
        self.assertEqual(list(path.iterdir()), [path / 'review.json'])
        self.selection['assets'][0]['review_reference'] = 'review does not override classification'
        self.photo(b'macro fixture', 'a.docm')
        result, path, manifest = self.prepare()
        self.assertIn('attachment_content_conflict', result['holds'])
        self.assertIn('attachment_held:macro_document', result['holds'])
        self.assertIn('selected_asset_requires_manual_conversion', result['holds'])
        self.assertEqual(manifest['files'], [])

    def test_correction_invalidates_old_bundle_and_preserves_history(self):
        first, path, _ = self.prepare()
        self.store.record_publication(self.selection['event_id'], digest(b'old published content'), 'synthetic publication evidence')
        raw = eml('Corrected body', subject='correction')
        self.store.receive('one', 'correction', raw, parse_eml(raw), {**META, 'corrects_message_id': 'body'})
        with self.assertRaisesRegex(ValueError, 'stale'):
            verify_draft(self.store, first['bundle_id'], self.site)
        held, _, manifest = self.prepare()
        self.assertIn('selected_source_superseded', held['holds'])
        self.assertEqual(held['file_count'], 0)
        self.selection['body_source'] = {'account': 'one', 'message_id': 'correction', 'source_hash': digest(raw)}
        latest, latest_path, manifest = self.prepare()
        self.assertEqual(latest['file_count'], 1)
        self.assertIn('Corrected body', (latest_path / manifest['target_path']).read_text())
        self.assertEqual(manifest['publications'][0]['sha256'], digest(b'old published content'))
        self.assertEqual(manifest['sources'][1]['corrects'], ['body'])
        self.assertTrue(path.exists())
        other = eml('Other correction', subject='correction')
        self.store.receive('one', 'other', other, parse_eml(other), {**META, 'corrects_message_id': 'body'})
        self.assertIn('ambiguous_corrections', self.prepare()[0]['holds'])

    def test_update_requires_exact_current_target_and_detects_changes(self):
        article = self.site / 'src/content/reikai/2026-09-15-synthetic.md'
        article.parent.mkdir(parents=True)
        article.write_bytes(b'existing report')
        self.assertIn('target_content_changed', self.prepare()[0]['holds'])
        self.selection['target']['expected_sha256'] = digest(article.read_bytes())
        result, _, manifest = self.prepare()
        self.assertEqual(manifest['operation'], 'update')
        self.assertEqual(result['file_count'], 1)
        article.write_bytes(b'concurrent update')
        with self.assertRaisesRegex(ValueError, 'stale'):
            verify_draft(self.store, result['bundle_id'], self.site)
        self.assertEqual(article.read_bytes(), b'concurrent update')

    def test_new_input_and_unknown_sender_are_not_silent_success(self):
        result, _, _ = self.prepare()
        raw = eml('Unreviewed contribution', sender='unknown@example.test')
        self.store.receive('one', 'late', raw, parse_eml(raw), META)
        with self.assertRaisesRegex(ValueError, 'stale'):
            verify_draft(self.store, result['bundle_id'], self.site)
        self.selection['body_source'] = {'account': 'one', 'message_id': 'late', 'source_hash': digest(raw)}
        held, _, manifest = self.prepare()
        self.assertEqual(held['status'], 'held')
        self.assertIn('unknown_sender', held['holds'])
        self.assertEqual(manifest['files'], [])
        self.assertFalse(held['auto_publish'])

    def test_selection_identity_event_and_path_guards(self):
        original = copy.deepcopy(self.selection)
        for field, value in [('source_hash', '0' * 64), ('account', 'other')]:
            self.selection = copy.deepcopy(original)
            self.selection['body_source'][field] = value
            with self.assertRaises(ValueError):
                self.prepare()
        self.selection = copy.deepcopy(original)
        for slug in ['../../escape', '2026-09-16-other', '2026-09-15-A', '2026-09-15-x/..']:
            self.selection['target']['slug'] = slug
            with self.assertRaises(ValueError):
                self.prepare()
        self.selection = original
        self.selection['target']['collection'] = 'news'
        with self.assertRaisesRegex(ValueError, 'reikai'):
            self.prepare()
        self.selection['target'].pop('collection')
        self.photo()
        self.selection['assets'].append(dict(self.selection['assets'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate selected asset'):
            self.prepare()
        self.assertFalse((self.store.database.parent / 'drafts').exists())

    def test_symlink_and_in_repository_storage_guards(self):
        (self.store.database.parent / 'drafts').symlink_to(self.site, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.prepare()
        self.assertEqual(list(self.site.iterdir()), [])
        (self.store.database.parent / 'drafts').unlink()
        with self.assertRaisesRegex(ValueError, 'ignored data'):
            prepare_draft(self.store, self.selection, self.root)

    def test_cli_raw_and_full_with_local_part_to_bundle_readback(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/mail_intake.py'
        cli_db = self.root / 'cli-private/db.sqlite'
        candidates = self.root / 'candidates.json'
        candidates.write_text(json.dumps({'people': [{'id': 'writer', 'addresses': ['writer@example.test']}]}))
        meta = self.root / 'meta.json'
        meta.write_text(json.dumps(META))
        export = self.root / 'export.json'
        command = [sys.executable, str(script), '--db', str(cli_db), '--candidates', str(candidates)]

        def run(*args):
            return json.loads(subprocess.check_output(command + list(args), text=True))

        export.write_text(json.dumps({'id': 'body', 'raw': base64.urlsafe_b64encode(self.raw).decode()}))
        received = run('receive', '--account', 'one', '--message-id', 'body', '--format', 'gmail-connector', '--input', str(export), '--metadata', str(meta))
        jpeg = b'\xff\xd8\xffcli-photo\xff\xd9'
        (self.root / 'photo.bin').write_bytes(jpeg)
        files = self.root / 'files.json'
        files.write_text(json.dumps({'message_id': 'photo', 'files': [{'part_id': '1', 'relative_path': 'photo.bin'}]}))
        export.write_text(json.dumps({'id': 'photo', 'payload': {'mimeType': 'multipart/mixed', 'headers': [
            {'name': 'From', 'value': 'writer@example.test'}, {'name': 'Authentication-Results', 'value': 'mx.google.com; dmarc=pass; dkim=pass'}],
            'parts': [{'partId': '1', 'mimeType': 'image/jpeg', 'filename': 'a.jpg', 'body': {'attachmentId': 'volatile'}}]}}))
        run('receive', '--account', 'one', '--message-id', 'photo', '--format', 'gmail', '--input', str(export), '--metadata', str(meta), '--attachment-files', str(files), '--asset-root', str(self.root))
        receipts = run('summary')['events'][0]['receipts']
        selected = copy.deepcopy(self.selection)
        selected['event_id'] = received['event_id']
        selected['body_source']['source_hash'] = receipts[0]['source_hash']
        selected['assets'] = [{'account': 'one', 'message_id': 'photo', 'source_hash': receipts[1]['source_hash'], 'part_id': '1', 'sha256': digest(jpeg), 'review_reference': 'synthetic reviewed photo'}]
        plan = self.root / 'selection.json'
        plan.write_text(json.dumps(selected))
        result = run('prepare-draft', '--selection', str(plan), '--site-root', str(self.site))
        self.assertEqual(result['file_count'], 2)
        self.assertFalse(result['auto_publish'])
        directory = Path(result['bundle'])
        manifest = json.loads((directory / 'review.json').read_text())
        self.assertEqual((directory / f'public/reikai/2026/{digest(jpeg)}.jpg').read_bytes(), jpeg)
        self.assertIn('Original body', (directory / manifest['target_path']).read_text())
        self.assertEqual(list(self.site.iterdir()), [])
        self.assertTrue(run('verify-draft', '--bundle-id', result['bundle_id'], '--site-root', str(self.site))['verified'])
        self.assertTrue(run('prepare-draft', '--selection', str(plan), '--site-root', str(self.site))['duplicate'])


if __name__ == '__main__':
    unittest.main()
