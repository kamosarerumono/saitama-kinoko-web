import base64
import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mail_intake import digest
from mail_source_adapter import connector_message, local_part_files, transferred_files_manifest
from test_mail_intake import META, eml
from test_mail_source_adapter import source


class TransferIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.message = source('complete-attachment-a')
        self.mid = self.message['message_id']
        self.jpeg = b'\xff\xd8\xfftransferred-original\xff\xd9'
        self.originals = self.root / 'originals'
        self.originals.mkdir()
        (self.originals / 'original.bin').write_bytes(self.jpeg)
        self.transfers = {'account': 'synthetic', 'message_id': self.mid, 'files': [{
            'message_id': self.mid, 'attachment_id': 'complete-attachment-a',
            'attachment_id_complete': True, 'filename': 'photo.jpg', 'part_id': '1',
            'source_kind': 'original', 'relative_path': 'original.bin', 'sha256': digest(self.jpeg),
        }]}
        self.db = self.root / 'private/db.sqlite'
        script = Path(__file__).resolve().parents[1] / 'scripts/mail_intake.py'
        self.command = [sys.executable, str(script), '--db', str(self.db), 'receive',
                        '--account', 'synthetic', '--message-id', self.mid,
                        '--format', 'gmail-connector', '--input', str(self.root / 'message.json'),
                        '--metadata', str(self.root / 'meta.json')]
        (self.root / 'meta.json').write_text(json.dumps(META), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, message=None, transfers=None):
        return transferred_files_manifest(connector_message(message or self.message), transfers or self.transfers, 'synthetic', self.mid)

    def cli(self, message=None, transfers=None, attach=True):
        (self.root / 'message.json').write_text(json.dumps(message or self.message), encoding='utf-8')
        (self.root / 'transfers.json').write_text(json.dumps(transfers or self.transfers), encoding='utf-8')
        extra = ['--transferred-files', str(self.root / 'transfers.json'), '--asset-root', str(self.originals)] if attach else []
        return subprocess.run(self.command + extra, capture_output=True, text=True)

    def snapshot(self):
        with sqlite3.connect(self.db) as db:
            return {name: db.execute(f'SELECT * FROM {name} ORDER BY 1,2').fetchall()
                    for name in ('messages', 'attachments', 'source_snapshots')}

    def test_cli_transfer_manifest_is_consumed_and_retry_is_idempotent(self):
        before = (self.originals / 'original.bin').read_bytes()
        for replay in (False, True):
            process = self.cli()
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result['duplicate'], replay)
            self.assertFalse(result['auto_publish'])
            self.assertNotIn('missing_part_data', result['holds'])
            self.assertIn('connector_decoded_text_requires_original', result['holds'])
            self.assertEqual(result['attachment_manifest'], self.manifest())
            with sqlite3.connect(self.db) as db:
                self.assertEqual(db.execute('SELECT part_id,sha256,content FROM attachments').fetchall(), [('1', digest(self.jpeg), self.jpeg)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM source_snapshots').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT source FROM messages').fetchone()[0], (self.root / 'message.json').read_bytes())
        self.assertEqual((self.originals / 'original.bin').read_bytes(), before)

    def test_exact_filename_fallback_and_ambiguous_names(self):
        records = copy.deepcopy(self.transfers)
        records['files'][0].pop('attachment_id')
        records['files'][0].pop('attachment_id_complete')
        self.assertEqual(self.manifest(transfers=records)['files'][0]['part_id'], '1')
        message = copy.deepcopy(self.message)
        other = copy.deepcopy(message['payload']['parts'][1])
        other['part_id'] = '2'
        other['body']['attachment_id'] = 'complete-attachment-b'
        message['payload']['parts'].append(other)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.manifest(message, records)
        exact = copy.deepcopy(self.transfers)
        exact['files'].append({**exact['files'][0], 'attachment_id': 'complete-attachment-b', 'part_id': '2', 'relative_path': 'second.bin'})
        self.assertEqual([r['part_id'] for r in self.manifest(message, exact)['files']], ['1', '2'])
        with self.assertRaisesRegex(ValueError, 'missing transferred original'):
            self.manifest(message, self.transfers)
        exact['files'][1]['relative_path'] = 'original.bin'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.manifest(message, exact)

    def test_transfer_contract_rejects_wrong_missing_duplicate_and_preview(self):
        cases = []
        for key, value in [('account', 'other'), ('message_id', 'another-message'), ('files', [])]:
            modified = copy.deepcopy(self.transfers)
            modified[key] = value
            cases.append(modified)
        for key, value in [('message_id', 'other'), ('attachment_id', 'unknown'), ('attachment_id', 'truncated...'),
                           ('attachment_id_complete', False), ('part_id', '9'), ('filename', 'different.jpg'),
                           ('sha256', None), ('sha256', 'bad-hash'), ('source_kind', 'extraction_preview'),
                           ('relative_path', '../outside.bin'), ('relative_path', 'C:\\outside.bin'),
                           ('relative_path', '/absolute.bin')]:
            modified = copy.deepcopy(self.transfers)
            modified['files'][0][key] = value
            cases.append(modified)
        duplicate = copy.deepcopy(self.transfers)
        duplicate['files'].append(dict(duplicate['files'][0]))
        cases.append(duplicate)
        for index, modified in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.manifest(transfers=modified)
        missing = copy.deepcopy(self.message)
        missing['payload']['parts'][1].pop('part_id')
        with self.assertRaisesRegex(ValueError, 'part_id required'):
            self.manifest(missing)
        duplicate = copy.deepcopy(self.message)
        duplicate['payload']['parts'].append(copy.deepcopy(duplicate['payload']['parts'][1]))
        with self.assertRaisesRegex(ValueError, 'duplicate MIME part_id'):
            self.manifest(duplicate)

    def test_cli_tamper_missing_file_and_sha_mismatch_preserve_receipt(self):
        accepted = self.cli()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        original_snapshot = self.snapshot()
        path = self.originals / 'original.bin'
        path.write_bytes(b'changed after authorized transfer')
        mismatch = self.cli()
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn('SHA256 mismatch', mismatch.stderr)
        self.assertEqual(self.snapshot(), original_snapshot)
        path.unlink()
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual(self.snapshot(), original_snapshot)
        path.write_bytes(self.jpeg)
        wrong_sha = copy.deepcopy(self.transfers)
        wrong_sha['files'][0]['sha256'] = '0' * 64
        self.assertNotEqual(self.cli(transfers=wrong_sha).returncode, 0)
        self.assertEqual(self.snapshot(), original_snapshot)
        wrong_message = copy.deepcopy(self.transfers)
        wrong_message['files'][0]['message_id'] = 'different-message'
        self.assertNotEqual(self.cli(transfers=wrong_message).returncode, 0)
        self.assertEqual(self.snapshot(), original_snapshot)

    def test_inline_original_cannot_be_replaced_and_raw_identity_stays_separate(self):
        message = copy.deepcopy(self.message)
        message['payload']['parts'][1]['body']['base64_url_content'] = base64.urlsafe_b64encode(b'different inline original').decode()
        with self.assertRaisesRegex(ValueError, 'conflicts with inline'):
            self.manifest(message)
        accepted = self.cli()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        original_snapshot = self.snapshot()
        raw = {'id': self.mid, 'raw': base64.urlsafe_b64encode(eml()).decode()}
        self.assertIn('raw identity is separate', self.cli(raw).stderr)
        raw_only = self.cli(raw, attach=False)
        self.assertNotEqual(raw_only.returncode, 0)
        self.assertIn('different source', raw_only.stderr)
        self.assertEqual(self.snapshot(), original_snapshot)

    def test_generated_manifest_retains_sha_check_when_consumed(self):
        manifest = self.manifest()
        self.assertEqual(local_part_files(manifest, self.originals, self.mid)['1'], self.jpeg)
        (self.originals / 'original.bin').write_bytes(b'changed between mapping and ingestion')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            local_part_files(manifest, self.originals, self.mid)

    def test_standard_full_cli_and_conflicting_attachment_options(self):
        self.command[self.command.index('gmail-connector')] = 'gmail'
        process = self.cli(message=connector_message(self.message))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['attachment_manifest']['files'][0]['part_id'], '1')
        snapshot = self.snapshot()
        self.command += ['--attachment-files', str(self.root / 'unused.json')]
        process = self.cli(message=connector_message(self.message))
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('cannot be combined', process.stderr)
        self.assertEqual(self.snapshot(), snapshot)

    def test_cli_rejects_missing_inline_part_id_without_partial_updates(self):
        self.assertEqual(self.cli().returncode, 0)
        before = self.snapshot()
        original = (self.originals / 'original.bin').read_bytes()
        message = copy.deepcopy(self.message)
        message['payload']['parts'].append({
            'mime_type': 'image/jpeg', 'filename': 'inline.jpg',
            'body': {'base64_url_content': base64.urlsafe_b64encode(self.jpeg).decode()},
        })
        for missing in (None, '', '   '):
            with self.subTest(part_id=missing):
                if missing is not None:
                    message['payload']['parts'][-1]['part_id'] = missing
                self.command[self.command.index('--message-id') + 1] = message['message_id'] = f'invalid-inline-{missing!r}'
                transfers = copy.deepcopy(self.transfers)
                transfers['message_id'] = transfers['files'][0]['message_id'] = message['message_id']
                process = self.cli(message, transfers)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn('MIME part_id required', process.stderr)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual((self.originals / 'original.bin').read_bytes(), original)

    def test_cli_rejects_duplicate_inline_part_ids_without_partial_updates(self):
        accepted = self.cli()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        before = self.snapshot()
        original = (self.originals / 'original.bin').read_bytes()
        message = copy.deepcopy(self.message)
        for filename in ('inline-one.jpg', 'inline-two.jpg'):
            message['payload']['parts'].append({
                'part_id': '2', 'mime_type': 'image/jpeg', 'filename': filename,
                'body': {'base64_url_content': base64.urlsafe_b64encode(self.jpeg).decode()},
            })
        self.command[self.command.index('--message-id') + 1] = message['message_id'] = 'invalid-duplicate-inline'
        transfers = copy.deepcopy(self.transfers)
        transfers['message_id'] = transfers['files'][0]['message_id'] = message['message_id']
        process = self.cli(message, transfers)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('duplicate MIME part_id', process.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.originals / 'original.bin').read_bytes(), original)

    def test_cli_rejects_inline_fallback_collision_without_partial_updates(self):
        self.assertEqual(self.cli().returncode, 0)
        before = self.snapshot()
        message = copy.deepcopy(self.message)
        transfers = copy.deepcopy(self.transfers)
        self.command[self.command.index('--message-id') + 1] = message['message_id'] = 'invalid-fallback-collision'
        transfers['message_id'] = transfers['files'][0]['message_id'] = message['message_id']
        message['payload']['parts'][1]['part_id'] = transfers['files'][0]['part_id'] = '0.2'
        message['payload']['parts'].append({
            'mime_type': 'image/jpeg', 'filename': 'inline.jpg',
            'body': {'base64_url_content': base64.urlsafe_b64encode(b'\xff\xd8\xffINLINE\xff\xd9').decode()},
        })
        process = self.cli(message, transfers)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('MIME part_id required', process.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.originals / 'original.bin').read_bytes(), self.jpeg)


if __name__ == '__main__':
    unittest.main()
