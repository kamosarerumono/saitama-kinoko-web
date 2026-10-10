import copy
from email.message import EmailMessage
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mail_intake import Intake, digest, parse_eml
from mail_draft import prepare_draft, verify_draft
from mail_word import extract_word, review_word
from test_mail_intake import CANDIDATES, META

FIXTURE = Path(__file__).parent / 'fixtures/simple.doc'
TEXT = '\nThis is a simple file created with Word 97-SR2.\n'


class WordDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = self.root / 'site'; self.site.mkdir()
        self.store = Intake(self.root / 'private/intake.sqlite3', copy.deepcopy(CANDIDATES))
        self.store.candidates.pop('excluded_addresses', None)
        message = EmailMessage()
        message['From'] = 'writer@example.test'
        message['Authentication-Results'] = 'mx.google.com; dmarc=pass; dkim=pass'
        message.set_content('Please use the attached report.')
        message.add_attachment(FIXTURE.read_bytes(), maintype='application', subtype='msword', filename='report.doc')
        self.raw = message.as_bytes()
        received = self.store.receive('synthetic', 'word', self.raw, parse_eml(self.raw), META)
        self.source = {'account': 'synthetic', 'message_id': 'word', 'source_hash': digest(self.raw),
                       'part_id': '0.1', 'sha256': digest(FIXTURE.read_bytes())}
        self.selection = {'event_id': received['event_id'], 'target': {'slug': '2026-09-15-synthetic-word', 'title': 'Synthetic Word report'},
                          'body_source': {k:self.source[k] for k in ('account','message_id','source_hash')}, 'assets': []}
        self.converter = self.root/'antiword'; self.converter.write_bytes(b'non-executable synthetic converter identity')

    def tearDown(self):
        self.store.close(); self.temp.cleanup()

    def extract(self, text=TEXT):
        with patch('mail_word.shutil.which', return_value=str(self.converter)), patch('mail_word.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b'')):
            return extract_word(self.store, self.source, str(self.converter))

    def review(self, extraction, **changes):
        record = {'extraction_id':extraction['extraction_id'], 'source':copy.deepcopy(self.source),
                  'text_sha256':extraction['text_sha256'], 'approved':True, 'review_reference':'synthetic human text/table review', 'disposition':'draft'}
        record.update(changes)
        return record

    def select(self, extraction):
        self.selection['body_source'] = {**self.source, 'extraction_id':extraction['extraction_id']}

    def prepare(self):
        return prepare_draft(self.store, self.selection, self.site)

    def immutable_originals(self):
        return {t:self.store.db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall() for t in ('messages','attachments','source_snapshots')}

    def test_explicit_review_and_adoption_replace_short_mail_only_in_draft(self):
        before = self.immutable_originals()
        self.assertEqual(self.prepare()['file_count'],0)
        extraction=self.extract()
        self.assertEqual(self.prepare()['file_count'],0)
        self.select(extraction)
        with self.assertRaisesRegex(ValueError,'not been approved'):self.prepare()
        review= self.review(extraction)
        self.assertFalse(review_word(self.store,review)['duplicate'])
        self.assertTrue(review_word(self.store,review)['duplicate'])
        result=self.prepare(); self.assertEqual(result['file_count'],1)
        manifest=json.loads((Path(result['bundle'])/'review.json').read_text())
        article=(Path(result['bundle'])/manifest['target_path']).read_text()
        self.assertIn(TEXT.strip(),article)
        self.assertNotIn('Please use the attached report.',article)
        self.assertEqual(manifest['body_derivation']['source'],self.source)
        self.assertEqual(manifest['body_derivation']['review'],review)
        self.assertTrue(self.prepare()['duplicate'])
        self.assertEqual(self.extract()['extraction_id'],extraction['extraction_id'])
        self.assertTrue(verify_draft(self.store,result['bundle_id'],self.site)['verified'])
        self.assertEqual(self.immutable_originals(),before)
        self.assertEqual(list(self.site.iterdir()),[])
        self.assertFalse(result['auto_publish'])
        del self.selection['body_source']['extraction_id']
        self.assertEqual(self.prepare()['file_count'],0)  # Approval alone never selects it.

    def test_unapproved_wrong_hash_wrong_document_and_review_overwrite_rejected(self):
        extraction=self.extract()
        for changes in ({'approved':False},{'review_reference':''},{'text_sha256':'0'*64},{'source':{**self.source,'part_id':'2'}},{'disposition':'automatic'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):review_word(self.store,self.review(extraction,**changes))
        review_word(self.store,self.review(extraction));self.select(extraction)
        for field in ('account','message_id','part_id','sha256','source_hash'):
            original=self.selection['body_source'][field];self.selection['body_source'][field]='wrong'
            with self.subTest(field=field),self.assertRaises(ValueError):self.prepare()
            self.selection['body_source'][field]=original
        with self.assertRaisesRegex(ValueError,'differently'):review_word(self.store,self.review(extraction,review_reference='different decision'))

    def test_changed_original_or_conflicting_version_invalidates_approval(self):
        extraction=self.extract();review_word(self.store,self.review(extraction));self.select(extraction)
        result=self.prepare()
        with self.store.db:
            self.store.db.execute('UPDATE attachments SET content=?',(b'changed bytes',))
        with self.assertRaisesRegex(ValueError,'changed'):verify_draft(self.store,result['bundle_id'],self.site)
        with self.assertRaises(ValueError):self.prepare()
        with self.store.db:
            self.store.db.execute('UPDATE attachments SET content=?',(FIXTURE.read_bytes(),))
        parsed=parse_eml(self.raw);parsed['attachments'][0]['data']+=b'new revision'
        self.store.receive('synthetic','word',self.raw,parsed,META)
        with self.assertRaisesRegex(ValueError,'conflicting'):self.prepare()

    def test_extraction_tamper_does_not_authorize_draft(self):
        extraction=self.extract();review_word(self.store,self.review(extraction));self.select(extraction)
        with self.store.db:self.store.db.execute('UPDATE word_extractions SET payload=?',(b'{}',))
        with self.assertRaisesRegex(ValueError,'changed'):self.prepare()

    def test_html_and_other_held_assets_remain_held(self):
        extraction=self.extract();review_word(self.store,self.review(extraction));self.select(extraction)
        parsed=parse_eml(self.raw);parsed['holds'].append('html_body_requires_review')
        self.store.receive('synthetic','word',self.raw,parsed,META)
        result=self.prepare();self.assertEqual(result['file_count'],0);self.assertIn('html_body_requires_review',result['holds'])
        parsed['holds']=[]
        parsed['attachments'].append({**parsed['attachments'][0],'part_id':'2'})
        self.store.receive('synthetic','word',self.raw,parsed,META)
        result=self.prepare();self.assertEqual(result['file_count'],0);self.assertIn('attachment_held:legacy_doc',result['holds'])

    def test_already_published_is_association_only_and_never_a_second_candidate(self):
        self.store.record_publication(self.selection['event_id'],digest(b'published'),'synthetic publication evidence')
        extraction=self.extract();self.select(extraction)
        with self.assertRaisesRegex(ValueError,'publication'):review_word(self.store,self.review(extraction))
        approved=self.review(extraction,disposition='already_published',publication_sha256=digest(b'published'),publication_reference='synthetic publication evidence')
        with self.assertRaisesRegex(ValueError,'publication'):review_word(self.store,{**approved,'publication_sha256':'0'*64})
        review_word(self.store,approved)
        result=self.prepare();self.assertEqual(result['file_count'],0)
        self.assertIn('selected_word_already_published',result['holds'])
        self.assertTrue(self.prepare()['duplicate'])
        self.assertEqual(list(Path(result['bundle']).iterdir()),[Path(result['bundle'])/'review.json'])

    def test_later_publication_makes_approved_bundle_stale(self):
        extraction=self.extract();review_word(self.store,self.review(extraction));self.select(extraction)
        result=self.prepare();self.assertEqual(result['file_count'],1)
        self.store.record_publication(self.selection['event_id'],digest(b'published'),'synthetic publication evidence')
        with self.assertRaisesRegex(ValueError,'stale'):verify_draft(self.store,result['bundle_id'],self.site)
        self.assertEqual(self.prepare()['file_count'],0)

    def test_converter_failure_does_not_create_extraction_or_mutate_source(self):
        before=self.immutable_originals()
        for stdout,code in ((b'',0),(b'partial',1),(b'\xff',0),(b'\0',0)):
            with patch('mail_word.shutil.which',return_value=str(self.converter)),patch('mail_word.subprocess.run',return_value=SimpleNamespace(returncode=code,stdout=stdout,stderr=b'')):
                with self.assertRaises((ValueError,UnicodeError)):extract_word(self.store,self.source,str(self.converter))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM word_extractions').fetchone()[0],0)
        self.assertEqual(self.immutable_originals(),before)

    def test_real_antiword_cli_to_review_draft_and_readback(self):
        antiword=os.environ.get('ANTIWORD') or shutil.which('antiword')
        if not antiword:self.skipTest('install antiword or set ANTIWORD for the real converter integration test')
        script=Path(__file__).resolve().parents[1]/'scripts/mail_intake.py'
        command=[sys.executable,str(script),'--db',str(self.store.database)]
        source=self.root/'source.json';source.write_text(json.dumps(self.source))
        def run(*args):return json.loads(subprocess.check_output(command+list(args),text=True))
        extraction=run('extract-word','--source',str(source),'--antiword',antiword)
        self.assertEqual(extraction['text'],TEXT)
        self.assertEqual(extraction['source'],self.source)
        review=self.root/'review.json';review.write_text(json.dumps(self.review(extraction)))
        run('review-word','--review',str(review));self.select(extraction)
        plan=self.root/'selection.json';plan.write_text(json.dumps(self.selection))
        result=run('prepare-draft','--selection',str(plan),'--site-root',str(self.site))
        self.assertEqual(result['file_count'],1)
        manifest=json.loads((Path(result['bundle'])/'review.json').read_text())
        self.assertIn(TEXT.strip(),(Path(result['bundle'])/manifest['target_path']).read_text())
        self.assertTrue(run('verify-draft','--bundle-id',result['bundle_id'],'--site-root',str(self.site))['verified'])
        self.assertTrue(run('extract-word','--source',str(source),'--antiword',antiword)['duplicate'])
        self.assertTrue(run('prepare-draft','--selection',str(plan),'--site-root',str(self.site))['duplicate'])


if __name__=='__main__':unittest.main()
