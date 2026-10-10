import base64
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mail_intake import Intake, gmail_identity, parse_gmail
from mail_source_adapter import connector_message, local_part_files


def source(aid='volatile-attachment'):
    return {'message_id': 'synthetic-connector-1', 'snippet': 'not a full body', 'payload': {
        'mime_type': 'multipart/mixed', 'headers': [{'name': 'From', 'value': 'writer@example.test'}],
        'parts': [
            {'part_id': '0', 'mime_type': 'text/plain', 'headers': [{'name': 'Content-Type', 'value': 'text/plain; charset=iso-2022-jp'}], 'body': {'content': '原稿全文'}},
            {'part_id': '1', 'mime_type': 'image/jpeg', 'filename': 'photo.jpg', 'body': {'attachment_id': aid}},
        ],
    }}


class SourceAdapterTests(unittest.TestCase):
    def test_documented_connector_content_and_binary_fields(self):
        value = source()
        jpeg = b'\xff\xd8\xffsynthetic\xff\xd9'
        value['payload']['parts'][1]['body']['base64_url_content'] = base64.urlsafe_b64encode(jpeg).decode()
        normalized = connector_message(value)
        parsed = parse_gmail(normalized)
        self.assertEqual(parsed['body'], '原稿全文')
        self.assertEqual(parsed['attachments'][0]['data'], jpeg)
        self.assertEqual(parsed['attachments'][0]['part_id'], '1')
        self.assertIn('connector_decoded_text_requires_original', parsed['holds'])
        self.assertNotIn('body_decode_failed', parsed['holds'])

    def test_mcp_text_structured_and_api_content_envelopes(self):
        direct = connector_message(source())
        for wrapped in [{'structuredContent': source()}, {'content': [{'type': 'text', 'text': json.dumps(source())}]}, {'api_content': source()}]:
            self.assertEqual(connector_message(wrapped), direct)
        with self.assertRaises(ValueError):
            connector_message({'isError': True, 'structuredContent': source()})

    def test_summary_preview_and_unknown_export_are_not_full_originals(self):
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            connector_message({'id': 'x', 'snippet': 'preview', 'body': 'summary'})
        value = source()
        value['payload']['parts'][0]['body']['content_truncated'] = True
        parsed = parse_gmail(connector_message(value))
        self.assertEqual(parsed['body'], '')
        self.assertIn('body_content_truncated', parsed['holds'])
        value['payload']['parts'][0]['body']['content'] = '\x1b$Bgarbled'
        value['payload']['parts'][0]['body']['content_truncated'] = False
        self.assertIn('body_mojibake', parse_gmail(connector_message(value))['holds'])

    def test_local_originals_use_part_id_and_are_path_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'originals'
            root.mkdir()
            jpeg = b'\xff\xd8\xfforiginal\xff\xd9'
            (root / 'one.bin').write_bytes(jpeg)
            manifest = {'message_id': 'synthetic-connector-1', 'files': [{'part_id': '1', 'relative_path': 'one.bin'}]}
            parts = local_part_files(manifest, root, 'synthetic-connector-1')
            normalized = connector_message(source())
            parsed = parse_gmail(normalized, part_data=parts)
            self.assertEqual(parsed['attachments'][0]['data'], jpeg)
            self.assertNotIn('missing_part_data', parsed['holds'])
            for relative in ['../outside.bin', str(root / 'one.bin')]:
                (Path(tmp) / 'outside.bin').write_bytes(b'outside')
                with self.assertRaises(ValueError):
                    local_part_files({'message_id': 'synthetic-connector-1', 'files': [{'part_id': '1', 'relative_path': relative}]}, root, 'synthetic-connector-1')
            with self.assertRaises(ValueError):
                local_part_files(manifest, root, 'another-message')
            (root / 'escape.bin').symlink_to(Path(tmp) / 'outside.bin')
            with self.assertRaises(ValueError):
                local_part_files({'message_id': 'synthetic-connector-1', 'files': [{'part_id': '1', 'relative_path': 'escape.bin'}]}, root, 'synthetic-connector-1')
            with self.assertRaises(ValueError):
                parse_gmail(normalized, part_data={'missing': jpeg})
            with self.assertRaises(ValueError):
                parse_gmail(normalized, part_data={'0': jpeg})

    def test_file_uri_and_extracted_preview_require_prior_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'file_uri'):
                local_part_files({'message_id': 'x', 'files': [{'part_id': '1', 'file_uri': 'private-provider-file-reference'}]}, Path(tmp), 'x')
            normalized = connector_message(source())
            self.assertIn('missing_part_data', parse_gmail(normalized)['holds'])

    def test_hydration_does_not_duplicate_connector_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Intake(Path(tmp) / 'private/db.sqlite')
            metadata = {'event_name': '合成観察会', 'event_date': '2026-09-15', 'event_verified': True}
            one, two = connector_message(source('a')), connector_message(source('b'))
            self.assertEqual(gmail_identity(one), gmail_identity(two))
            store.receive('synthetic-account', one['id'], json.dumps(source('a')).encode(), parse_gmail(one), metadata, gmail_identity(one))
            asset = {'1': b'\xff\xd8\xffdownloaded\xff\xd9'}
            result = store.receive('synthetic-account', two['id'], json.dumps(source('b')).encode(), parse_gmail(two, part_data=asset), metadata, gmail_identity(two))
            self.assertTrue(result['duplicate'])
            self.assertFalse(result['auto_publish'])
            self.assertEqual(len(store.summary()['events'][0]['receipts'][0]['assets']), 1)
            store.close()

    def test_cli_connector_full_and_raw_entrypoints(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            source_path = p / 'source.json'
            source_path.write_text(json.dumps({'structuredContent': source()}))
            command = [sys.executable, str(root / 'scripts/mail_intake.py'), '--db', str(p / 'private/db.sqlite'), 'receive', '--account', 'synthetic-account', '--message-id', 'synthetic-connector-1', '--format', 'gmail-connector', '--input', str(source_path)]
            result = json.loads(subprocess.check_output(command, text=True))
            self.assertIn('connector_decoded_text_requires_original', result['holds'])
            self.assertFalse(result['auto_publish'])
            (p / 'originals').mkdir()
            (p / 'originals' / 'photo.bin').write_bytes(b'\xff\xd8\xfflocal\xff\xd9')
            (p / 'files.json').write_text(json.dumps({'message_id': 'synthetic-connector-1', 'files': [{'part_id': '1', 'relative_path': 'photo.bin'}]}))
            hydrated = json.loads(subprocess.check_output(command + ['--attachment-files', str(p / 'files.json'), '--asset-root', str(p / 'originals')], text=True))
            self.assertTrue(hydrated['duplicate'])
            self.assertNotIn('missing_part_data', hydrated['holds'])
            self.assertFalse(hydrated['auto_publish'])
            raw = b'From: writer@example.test\nContent-Type: text/plain; charset=iso-2022-jp\n\n' + '原稿原本'.encode('iso-2022-jp')
            source_path.write_text(json.dumps({'id': 'raw-2', 'raw': base64.urlsafe_b64encode(raw).decode()}))
            command[command.index('synthetic-connector-1')] = 'raw-2'
            result = json.loads(subprocess.check_output(command, text=True))
            self.assertNotIn('connector_decoded_text_requires_original', result['holds'])
            self.assertFalse(result['auto_publish'])


    def test_cli_conflict_survives_unhydrated_replay(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            db = p / 'private/db.sqlite'
            source_path = p / 'source.json'
            command = [sys.executable, str(root / 'scripts/mail_intake.py'), '--db', str(db)]
            receive = command + ['receive', '--account', 'synthetic-account', '--message-id', 'synthetic-connector-1', '--format', 'gmail-connector', '--input', str(source_path)]
            originals = [b'\xff\xd8\xffa\xff\xd9', b'\xff\xd8\xffb\xff\xd9']
            snapshots = []
            for index, data in enumerate([*originals, None, None, originals[0]]):
                value = source()
                if data is not None:
                    value['payload']['parts'][1]['body']['base64_url_content'] = base64.urlsafe_b64encode(data).decode()
                raw = json.dumps(value).encode()
                snapshots.append(raw)
                source_path.write_bytes(raw)
                result = json.loads(subprocess.check_output(receive, text=True))
                self.assertEqual(result['duplicate'], index > 0)
                self.assertFalse(result['auto_publish'])
                if index > 0:
                    self.assertIn('attachment_content_conflict', result['holds'])
                    summary = json.loads(subprocess.check_output(command + ['summary'], text=True))
                    self.assertEqual(summary['unassigned'][0]['holds'], result['holds'])
            with sqlite3.connect(db) as saved:
                self.assertEqual(saved.execute('SELECT source FROM messages').fetchall(), [(snapshots[0],)])
                self.assertEqual({r[0] for r in saved.execute('SELECT content FROM attachments')}, set(originals))
                self.assertEqual({r[0] for r in saved.execute('SELECT source FROM source_snapshots')}, set(snapshots))
                self.assertEqual(saved.execute('SELECT COUNT(*) FROM attachments').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
