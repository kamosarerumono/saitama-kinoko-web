import copy
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import legacy_bundle as b
import legacy_publish as p
import legacy_publication_ui as ui

class FakeFTP:
 def __init__(self,plan,root):
  self.plan=plan;self.root=root;self.dirs={'.','reikai','reikai/2026'};self.writes=[]
  self.files={r['path']:(root/'baseline'/r['path']).read_bytes() for r in plan['files'] if r['role'] in ('annual','top')}
  self.fail_list=False;self.fail_write=False;self.corrupt=False;self.run=None
 def mlsd(self,d):
  if self.fail_list:raise PermissionError()
  if d not in self.dirs:raise FileNotFoundError()
  values=[(PurePosixPath(x).name,{'type':'dir'}) for x in self.dirs if x!='.' and str(PurePosixPath(x).parent)==d]
  return values+[(PurePosixPath(x).name,{'type':'file'}) for x in self.files if str(PurePosixPath(x).parent)==d]
 def retrbinary(self,cmd,callback):callback(self.files[cmd[5:]])
 def mkd(self,path):
  assert (self.run/'backup/index.htm').exists();self.dirs.add(path)
 def storbinary(self,cmd,stream):
  assert (self.run/'backup/index.htm').exists()
  if self.fail_write:raise EOFError()
  path=cmd[5:];self.files[path]=b'corrupt' if self.corrupt else stream.read();self.writes.append(path)

class LegacyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.source=self.root/'source';self.source.mkdir();self.inputs=self.root/'inputs';self.inputs.mkdir()
  self.name='src/content/reikai/2026-11-03-synthetic.md';self.md=b'---\ntitle: Synthetic\ndate: 2026-11-03\n---\n\nBody\n'
  file=self.source/self.name;file.parent.mkdir(parents=True);file.write_bytes(self.md)
  self.photo='/reikai/2026/synthetic.jpg';self.image=b'\xff\xd8\xfffixture\xff\xd9'
  file=self.source/('public'+self.photo);file.parent.mkdir(parents=True);file.write_bytes(self.image)
  self.annual=b'<html><body><a href="old.html">old</a><!-- add --></body></html>'
  self.top='<html><body>既存のお知らせ<!-- add --></body></html>'.encode('cp932')
  for name,data in [('annual.html',self.annual),('top.htm',self.top)]: (self.inputs/name).write_bytes(data)
  self.spec={'schema_version':1,'review_reference':'synthetic owner review','source':{'path':self.name,'sha256':b.sha(self.md)},
    'legacy_slug':'261103_synthetic','assets':{self.photo:b.sha(self.image)},'navigation':{
    'annual':{'file':'annual.html','sha256':b.sha(self.annual),'encoding':'utf-8','anchor':'<!-- add -->'},
    'top':{'file':'top.htm','sha256':b.sha(self.top),'encoding':'cp932','anchor':'<!-- add -->'}}}
  self.rendered={'metadata':{'title':'合成報告','date':'2026-11-03','reporter':'合成担当','photographer':'撮影者'},'html':'<p>確認済み本文</p><img src="'+self.photo+'" alt="合成写真（撮影 人物）"><figcaption>合成写真（撮影 人物）</figcaption>'}
  self.output=self.root/'bundle'
  self.mock=patch.object(b,'render_markdown',return_value=self.rendered);self.mock.start();self.addCleanup(self.mock.stop)
 def prepare(self):
  result=b.prepare(self.spec,self.source,self.inputs,self.output)
  self.addCleanup(patch.stopall)
  p.ROOT=self.output;p.MANIFEST_SHA=result['manifest_sha256'];self.plan=p.load_plan();self.ftp=FakeFTP(self.plan,self.output)
  self.run=self.root/'run';self.run.mkdir(exist_ok=True);self.ftp.run=self.run
  return result
 def get(self,path):return self.ftp.files.get(path)
 def test_generate_three_pages_and_images_preserves_original_bytes(self):
  result=self.prepare();self.assertEqual(result['file_count'],4)
  article=(self.output/'stage/reikai/2026/261103_synthetic.html').read_text(encoding='utf-8')
  self.assertIn('images_261103_synthetic/synthetic.jpg',article);self.assertNotIn('撮影 人物',article);self.assertNotIn('撮影者',article);self.assertIn('確認済み本文',article)
  top=(self.output/'stage/index.htm').read_bytes();self.assertTrue(top.startswith(self.top.split(b'<!--')[0]))
  self.assertEqual((self.output/'baseline/index.htm').read_bytes(),self.top)
  self.assertEqual((self.source/self.name).read_bytes(),self.md)
  self.assertEqual(b.prepare(self.spec,self.source,self.inputs,self.output),result)
 def test_changed_reviewed_source_rejected(self):
  (self.source/self.name).write_bytes(self.md+b'edit');self.assertRaises(ValueError,self.prepare)
 def test_text_only_report_creates_no_image_directory(self):
  self.rendered['html']='<p>Text only</p>';self.spec['assets']={};self.prepare()
  result=p.apply(self.ftp,self.plan,self.run,self.get)
  self.assertEqual(result['verified_count'],3);self.assertEqual(self.ftp.dirs,{'.','reikai','reikai/2026'})
 def test_january_report_uses_previous_fiscal_year(self):
  self.name='src/content/reikai/2027-01-10-synthetic.md';(self.source/self.name).write_bytes(self.md)
  self.spec['source']['path']=self.name;self.spec['legacy_slug']='270110_synthetic';self.rendered['metadata']['date']='2027-01-10'
  self.prepare();self.assertEqual(self.plan['legacy_year'],2026)
  self.assertEqual(self.plan['files'][-3]['path'],'reikai/2026/270110_synthetic.html')
 def test_concurrent_navigation_change_preserved(self):
  self.prepare();original=self.ftp.storbinary
  def store(cmd,stream):
   original(cmd,stream)
   if len(self.ftp.writes)==2:self.ftp.files['index.htm']=b'another editor'
  self.ftp.storbinary=store
  self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,self.get)
  self.assertEqual(self.ftp.files['index.htm'],b'another editor');self.assertNotIn('index.htm',self.ftp.writes)
 def test_changed_image_rejected(self):
  (self.source/('public'+self.photo)).write_bytes(self.image+b'edit');self.assertRaises(ValueError,self.prepare)
 def test_held_intake_draft_not_bypassed(self):
  (self.source/'review.json').write_text(json.dumps({'holds':['conflict'],'status':'held'}));self.spec['draft_review']='review.json'
  self.assertRaises(ValueError,self.prepare)
 def test_anchor_missing_or_ambiguous_stops(self):
  self.spec['navigation']['annual']['anchor']='absent';self.assertRaises(ValueError,self.prepare)
 def test_active_html_and_external_images_rejected(self):
  for code in ['<script>bad</script>','<img src="https://example.test/x.jpg">','<img src="'+self.photo+'" onerror="bad">']:
   self.rendered['html']=code;self.assertRaises(ValueError,self.prepare)
 def test_new_report_omits_photographer_table_rows_and_supported_credits(self):
  self.rendered['html']=(
   '<table><tbody><tr><th>写真</th><td>栗原晴夫、松村、近藤</td></tr>'
   '<tr><th>場所</th><td>県民&amp;森</td></tr></tbody></table>'
   '<figure><img src="'+self.photo+'" alt="観察写真（撮影 栗原）">'
   '<figcaption>観察写真（写真提供 栗原晴夫）</figcaption></figure>'
   '<p>記録（撮影：近藤）</p>')
  self.prepare()
  article=(self.output/'stage/reikai/2026/261103_synthetic.html').read_text(encoding='utf-8')
  self.assertNotIn('栗原',article);self.assertNotIn('松村',article);self.assertNotIn('近藤',article)
  self.assertNotIn('<th>写真</th>',article);self.assertIn('<th>場所</th>',article)
  self.assertIn('観察写真',article);self.assertIn('県民&amp;森',article);self.assertIn('記録',article)
 def test_path_escape_rejected(self):
  self.spec['navigation']['top']['file']='../other';self.assertRaises(ValueError,self.prepare)
 def test_stale_bundle_not_overwritten(self):
  self.prepare();path=self.output/'stage/index.htm';path.write_bytes(b'keep');self.assertRaises(ValueError,b.prepare,self.spec,self.source,self.inputs,self.output);self.assertEqual(path.read_bytes(),b'keep')
 def test_manifest_scope_and_stage_tamper_rejected(self):
  self.prepare();(self.output/'stage/extra.docx').write_bytes(b'not allowed');self.assertRaises(p.Stop,p.load_plan)
 def test_success_order_backup_and_public_readback(self):
  self.prepare();result=p.apply(self.ftp,self.plan,self.run,self.get)
  self.assertEqual(result['verified_count'],4);self.assertEqual(self.ftp.writes,[r['path'] for r in self.plan['files']])
  self.assertEqual((self.run/'backup/index.htm').read_bytes(),self.top)
 def test_identical_image_skip_remaining_three(self):
  self.prepare();row=self.plan['files'][0];self.ftp.files[row['path']]=self.image;self.ftp.dirs.add(str(PurePosixPath(row['path']).parent))
  self.plan['resume_verified']=[row['path']];result=p.apply(self.ftp,self.plan,self.run,self.get)
  self.assertEqual(result['skipped'],[row['path']]);self.assertEqual(len(self.ftp.writes),3)
 def test_missing_confirmed_target_stops(self):
  self.prepare();self.plan['resume_verified']=[self.plan['files'][0]['path']]
  self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,self.get);self.assertFalse(self.ftp.writes)
 def test_unknown_existing_article_stops(self):
  self.prepare();self.ftp.files[self.plan['files'][-3]['path']]=b'other'
  self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,self.get);self.assertFalse(self.ftp.writes)
 def test_permission_is_not_absence(self):
  self.prepare();self.ftp.fail_list=True
  self.assertRaises(PermissionError,p.apply,self.ftp,self.plan,self.run,self.get);self.assertFalse(self.ftp.writes)
 def test_ftp_https_difference_stops(self):
  self.prepare();self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,lambda path:b'different');self.assertFalse(self.ftp.writes)
 def test_navigation_waits_for_published_article(self):
  self.prepare()
  def get(path):return None if len(self.ftp.writes)>=2 and path==self.plan['files'][-3]['path'] else self.get(path)
  self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,get)
  self.assertEqual(self.ftp.writes,[r['path'] for r in self.plan['files'][:-2]])
 def test_existing_backup_never_overwritten(self):
  self.prepare();p.backup_all({'index.htm':b'keep'},self.run)
  self.assertRaises(FileExistsError,p.apply,self.ftp,self.plan,self.run,self.get)
  self.assertEqual((self.run/'backup/index.htm').read_bytes(),b'keep');self.assertFalse(self.ftp.writes)
 def test_eof_keeps_backup_and_does_not_retry(self):
  self.prepare();self.ftp.fail_write=True;self.assertRaises(EOFError,p.apply,self.ftp,self.plan,self.run,self.get)
  self.assertEqual((self.run/'backup/index.htm').read_bytes(),self.top)
  self.assertEqual(json.loads((self.run/'phase.json').read_text())['phase'],'upload_started')
 def test_corrupt_ftp_readback_stops(self):
  self.prepare();self.ftp.corrupt=True;self.assertRaises(p.Stop,p.apply,self.ftp,self.plan,self.run,self.get)
  self.assertEqual(len(self.ftp.writes),1)
 def test_previous_run_bound_to_same_manifest(self):
  self.prepare();runs=self.root/'runs';run=runs/'one';run.mkdir(parents=True)
  (run/'manifest.sha256').write_text(p.MANIFEST_SHA);(run/'progress.json').write_text(json.dumps({'uploaded':[self.plan['files'][0]['path']],'skipped':[]}))
  self.assertEqual(p.previous_verified(self.plan,runs),[self.plan['files'][0]['path']])
  (run/'manifest.sha256').write_text('wrong');self.assertRaises(p.Stop,p.previous_verified,self.plan,runs)
 def test_confirmation_no_or_close_denies(self):
  self.prepare()
  with patch.object(ui.sys,'platform','win32'),patch.object(ui.sys.stdin,'isatty',return_value=True):
   for result in [0,2,7]:self.assertFalse(ui.confirm_publication(self.plan,Mock(return_value=result)))
 def test_correction_confirmation_names_single_article_and_keeps_no_as_default(self):
  plan={'operation':'correction','title':'Minoyama photographer correction',
        'files':[{'path':f'reikai/2026/images_261004/{n:02d}.jpg'} for n in range(24)] +
                [{'path':'reikai/2026/261004_minoyama.html'},
                 {'path':'reikai/2026/annual.html'},{'path':'index.htm'}]}
  show=Mock(side_effect=[6,7,2])
  with patch.object(ui.sys,'platform','win32'),patch.object(ui.sys.stdin,'isatty',return_value=True):
   self.assertTrue(ui.confirm_publication(plan,show))
   self.assertFalse(ui.confirm_publication(plan,show))
   self.assertFalse(ui.confirm_publication(plan,show))
  self.assertEqual(show.call_count,3)
  _,message,title,flags=show.call_args_list[0].args
  self.assertIn('https://ippon.sakura.ne.jp/reikai/2026/261004_minoyama.html',message)
  self.assertIn('27 files checked; only the article HTML may change.',message)
  self.assertIn('Existing image and navigation files must already match.',message)
  self.assertIn('All existing files are backed up before the article update.',message)
  self.assertIn('No cancels without authentication or upload.',message)
  self.assertEqual(title,'Reviewed article correction')
  self.assertEqual(flags,0x4|0x20|0x100|0x10000)
 def test_actual_cmd_rejects_pipe_before_credentials(self):
  if sys.platform!='win32':self.skipTest('Windows launcher')
  self.prepare();proc=subprocess.run(['cmd.exe','/d','/c',str(self.output/'PUBLISH_REPORT.cmd')],input='\n',capture_output=True,text=True,encoding='utf-8',timeout=20)
  self.assertEqual(proc.returncode,2);self.assertIn('本人のWindows端末',proc.stdout)
 def test_real_astro_renderer(self):
  self.mock.stop()
  node=os.environ.get('LEGACY_TEST_NODE','node')
  source=self.md+b'\n![caption]('+self.photo.encode()+b')\n'
  (self.source/self.name).write_bytes(source);self.spec['source']['sha256']=b.sha(source)
  result=b.prepare(self.spec,self.source,self.inputs,self.output,node)
  self.assertEqual(result['file_count'],4)

if __name__=='__main__':unittest.main(verbosity=2)
