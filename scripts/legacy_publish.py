"""Fixed-scope explicit FTPS handoff. Default is unauthenticated read-only dry run."""
from pathlib import Path, PurePosixPath
import argparse, datetime, ftplib, getpass, hashlib, io, json, os, ssl, sys, warnings
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from urllib.error import HTTPError
from windows_credential import password_for_publish
from legacy_publication_ui import confirm_publication
from legacy_bundle import relative_file, bounded
ROOT=None
HOST='ippon.sakura.ne.jp'; USER='ippon'; REMOTE_ROOT='/home/ippon/www'
MANIFEST_SHA=None
MAX_BYTES=16*1024*1024
class Stop(RuntimeError):pass
class AuditedFTP_TLS(ftplib.FTP_TLS):
 def putcmd(self,line):
  # Record only a command verb. Never retain arguments, replies, or credentials.
  self.last_command=line.partition(' ')[0]
  return super().putcmd(line)

def journal(run,phase,path=None):
 (run/'phase.json').write_text(json.dumps({'phase':phase,'path':path}))

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise Stop('HTTP redirect is outside this handoff')
def digest(b):return hashlib.sha256(b).hexdigest()
def load_plan():
 raw=bounded(relative_file(ROOT,'manifest.json'))
 if digest(raw)!=MANIFEST_SHA:raise Stop('Reviewed manifest changed')
 m=json.loads(raw)
 if m.get('schema_version')!=1 or m.get('host')!=HOST or m.get('remote_root')!=REMOTE_ROOT or m.get('auto_publish') is not False:
  raise Stop('Invalid publication scope')
 import re
 import datetime
 date=datetime.date.fromisoformat(m['date']);year=str(date.year-1 if date.month<4 else date.year);slug=m['legacy_slug']
 if m.get('legacy_year')!=int(year):raise Stop('Fiscal year mismatch')
 if not re.fullmatch(date.strftime('%y%m%d')+r'_[a-z0-9_-]{1,60}',slug):raise Stop('Invalid report slug')
 rows=m['files']
 correction=m.get('operation')=='correction'
 if not isinstance(rows,list) or not 3<=len(rows)<=1003:raise Stop('Invalid file count')
 if correction:
  expected=[f'reikai/2026/images_261004/261004_minoyama-{n:02d}.{"jpg" if n==1 else "png"}' for n in range(1,25)]
  expected += ['reikai/2026/261004_minoyama.html','reikai/2026reikaihoukoku.html','index.htm']
  if m.get('legacy_slug')!='261004_minoyama' or m.get('date')!='2026-10-04' or [x.get('path') for x in rows]!=expected:
   raise Stop('Correction scope is not the reviewed Minoyama report')
  if sum(x.get('role')=='article' and x.get('before_sha256')!=x.get('sha256') for x in rows)!=1:
   raise Stop('Correction must change only the reviewed article')
 image_name='images_261004' if correction else 'images_'+slug
 image_prefix=f'reikai/{year}/{image_name}/'
 if [x.get('role') for x in rows[-3:]]!=['article','annual','top']:raise Stop('Invalid publication order')
 if [x['path'] for x in rows[-3:]]!=[f'reikai/{year}/{slug}.html',f'reikai/{year}reikaihoukoku.html','index.htm']:raise Stop('Unexpected targets')
 paths=set()
 for i,row in enumerate(rows):
  path=row['path']
  if path in paths:raise Stop('Duplicate target')
  paths.add(path)
  if i<len(rows)-3:
   if row.get('role')!='image' or not path.startswith(image_prefix) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png)',path[len(image_prefix):]):raise Stop('Invalid image scope')
  if not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise Stop('Invalid hash')
  before=row['before_sha256']
  if row['role'] in ('annual','top'):
   if not isinstance(before,str) or not re.fullmatch('[0-9a-f]{64}',before):raise Stop('Navigation baseline required')
   if digest(bounded(relative_file(ROOT,'baseline/'+path)))!=before:raise Stop('Local baseline changed')
  elif correction:
   if not isinstance(before,str) or not re.fullmatch('[0-9a-f]{64}',before):raise Stop('Correction baseline required')
   if row['role']!='article' and before!=row['sha256']:raise Stop('Correction cannot change images or navigation')
  elif before is not None:raise Stop('Only new reports are supported')
  data=bounded(relative_file(ROOT,'stage/'+path))
  if len(data)!=row['bytes'] or digest(data)!=row['sha256']:raise Stop('Stage changed')
 actual={p.relative_to(ROOT/'stage').as_posix() for p in (ROOT/'stage').rglob('*') if p.is_file()}
 if actual!=paths:raise Stop('Unexpected staged file')
 return m

def https_get(path):
 opener=build_opener(NoRedirect,HTTPSHandler(context=ssl.create_default_context()))
 try:
  with opener.open(Request('https://'+HOST+'/'+path,headers={'Cache-Control':'no-cache'}),timeout=30) as r:
   if r.status!=200:raise Stop('Unexpected HTTP status')
   b=r.read(MAX_BYTES+1)
   if len(b)>MAX_BYTES:raise Stop('HTTP response exceeds bounded size')
   return b
 except HTTPError as e:
  if e.code==404:return None
  raise Stop('HTTP access/status failure: '+str(e.code)) from None

def allowed_before(row,data,plan):
 if data is not None and digest(data)==row['sha256']:return True
 if row['path'] in plan.get('resume_verified',[]):return False
 before=row['before_sha256']
 return data is None if before is None else data is not None and digest(data)==before

def public_preflight(plan,get=https_get):
 result={}
 for row in plan['files']:
  b=get(row['path'])
  if not allowed_before(row,b,plan):raise Stop('Public baseline changed: '+row['path'])
  result[row['path']]=None if b is None else digest(b)
 return result

def listing(ftp,directory):
 entries={}
 for name,facts in ftp.mlsd(directory):
  kind=facts.get('type','')
  if kind in ('cdir','pdir'):continue
  if name in ('.','..') or '/' in name or '\\' in name:raise Stop('Unexpected directory entry')
  entries[name]=kind
 return entries

def remote_state(ftp,plan):
 year=str(plan['legacy_year']);slug=plan['legacy_slug'];year_dir='reikai/'+year;image_name='images_261004' if plan.get('operation')=='correction' else 'images_'+slug
 dirs={'.':listing(ftp,'.')}
 if dirs['.'].get('reikai')!='dir':raise Stop('Ancestor is not a directory')
 dirs['reikai']=listing(ftp,'reikai')
 if dirs['reikai'].get(year)!='dir':raise Stop('Year directory must already exist')
 dirs[year_dir]=listing(ftp,year_dir)
 image_dir=year_dir+'/'+image_name
 kind=dirs[year_dir].get(image_name)
 if kind is not None and kind!='dir':raise Stop('Image directory is not a regular directory')
 dirs[image_dir]=listing(ftp,image_dir) if kind else {}
 result={}
 for row in plan['files']:
  p=PurePosixPath(row['path']);kind=dirs[str(p.parent)].get(p.name)
  if kind is None:result[row['path']]=None;continue
  if kind!='file':raise Stop('Target is not a regular file')
  chunks=[];size=0
  def take(b):
   nonlocal size
   size+=len(b)
   if size>MAX_BYTES:raise Stop('FTP response exceeds bounded size')
   chunks.append(b)
  ftp.retrbinary('RETR '+row['path'],take)
  result[row['path']]=b''.join(chunks)
 return result, bool(dirs[image_dir]) or image_name in dirs[year_dir]

def backup_all(state,run):
 for path,data in state.items():
  if data is None:continue
  out=run/'backup'/path;out.parent.mkdir(parents=True,exist_ok=True)
  with out.open('xb') as stream:stream.write(data)
  if out.read_bytes()!=data:raise Stop('Local backup verification failed')

def apply(ftp,plan,run,get=https_get):
 journal(run,'ftp_preflight')
 initial,_=remote_state(ftp,plan)
 for row in plan['files']:
  data=initial[row['path']]
  if not allowed_before(row,data,plan):raise Stop('FTP baseline changed: '+row['path'])
  public=get(row['path'])
  if (None if public is None else digest(public)) != (None if data is None else digest(data)):raise Stop('FTP and HTTPS baselines differ')
 journal(run,'local_backup')
 backup_all(initial,run) # Every existing target must be backed up before any remote write.
 uploaded=[];skipped=[]
 for row in plan['files']:
  # Re-list/re-read before each write. Access errors never imply absence.
  journal(run,'before_write_check',row['path'])
  current,has_images=remote_state(ftp,{**plan,'files':[row]})
  path=row['path'];before=initial[path]
  if current[path]!=before:raise Stop('Remote changed during this run: '+path)
  if before is not None and digest(before)==row['sha256']:
   skipped.append(path)
   (run/'progress.json').write_text(json.dumps({'uploaded':uploaded,'skipped':skipped}))
   continue
  if row['role'] in ('annual','top'):
   journal(run,'before_navigation_public_gate',path)
   for dependency in plan['files'][:-2]:
    published=get(dependency['path'])
    if published is None or digest(published)!=dependency['sha256']:
     raise Stop('Article/images are not verified publicly; navigation remains unchanged')
   # Refresh the navigation target after the public gate before overwriting it.
   fresh,_=remote_state(ftp,{**plan,'files':[row]})
   if fresh[path]!=before:raise Stop('Navigation changed during public gate')
  if row['role']=='image' and not has_images:ftp.mkd('reikai/'+str(plan['legacy_year'])+'/images_'+plan['legacy_slug'])
  data=bounded(relative_file(ROOT,'stage/'+path))
  if digest(data)!=row['sha256']:raise Stop('Stage changed during upload')
  journal(run,'upload_started',path)
  ftp.storbinary('STOR '+path,io.BytesIO(data))
  journal(run,'ftp_readback',path)
  after,_=remote_state(ftp,{**plan,'files':[row]})
  if after[path]!=data:raise Stop('FTP readback differs: '+path)
  uploaded.append(path);initial[path]=data
  (run/'progress.json').write_text(json.dumps({'uploaded':uploaded,'skipped':skipped},indent=2))
 verified=[]
 for row in plan['files']:
  journal(run,'https_readback',row['path'])
  data=get(row['path'])
  if data is None or digest(data)!=row['sha256']:raise Stop('HTTPS readback differs: '+row['path'])
  verified.append(row['path'])
 return {'status':'PUBLICATION_VERIFIED','verified_count':len(verified),'uploaded':uploaded,'skipped':skipped,'verified':verified}

def previous_verified(plan, runs):
 """Only local records bound to this immutable manifest influence recovery."""
 known={row['path'] for row in plan['files']}; verified=set()
 if runs.exists():
  for run in runs.iterdir():
   if run.is_symlink() or not run.is_dir():raise Stop('Unexpected run storage')
   identity=run/'manifest.sha256'
   if not identity.exists() or identity.read_text()!=MANIFEST_SHA:raise Stop('Unbound prior run')
   progress=run/'progress.json'
   if progress.exists():
    record=json.loads(progress.read_text())
    paths=set(record.get('uploaded',[])+record.get('skipped',[]))
    if not paths<=known:raise Stop('Prior run scope differs')
    verified.update(paths)
 return sorted(verified)

def main():
 global ROOT,MANIFEST_SHA
 parser=argparse.ArgumentParser(description='確認済み新規例会報告をさくらへ公開。既定は認証なし事前確認。')
 parser.add_argument('--bundle',required=True);parser.add_argument('--manifest-sha',required=True)
 mode=parser.add_mutually_exclusive_group();mode.add_argument('--publish',action='store_true');mode.add_argument('--readback',action='store_true')
 args=parser.parse_args();ROOT=Path(args.bundle).resolve(strict=True);MANIFEST_SHA=args.manifest_sha
 plan=load_plan()
 print('対象: '+plan['title']+' / https://'+HOST+'/'+plan['files'][-3]['path'])
 print('ファイル数: '+str(len(plan['files']))+' / 年間一覧・TOPは最後に更新します。')
 if args.readback:
  matches=[]
  for row in plan['files']:
   data=https_get(row['path']);matches.append(data is not None and digest(data)==row['sha256'])
  print(json.dumps({'matched':sum(matches),'expected':len(matches)}));return 0 if all(matches) else 2
 if not args.publish:
  public_preflight(plan);print('DRY_RUN_PASS: 公開側と手元の内容を確認。認証・送信なし。');return 0
 if not sys.stdin.isatty():raise Stop('本人のWindows端末から起動してください')
 if not confirm_publication(plan):print('キャンセルしました。認証・送信なし。');return 0
 # One lock shared across all bundles handled by this installed publisher.
 state=Path(__file__).resolve().parents[1]/'data'/'legacy-publication'
 state.mkdir(parents=True,exist_ok=True)
 lock=state/'GT030-publication.lock'
 fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 ftp=None;run=None
 try:
  os.write(fd,str(os.getpid()).encode());os.close(fd);fd=None
  runs=state/'runs'/MANIFEST_SHA
  plan['resume_verified']=previous_verified(plan,runs)
  run=runs/datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%S.%fZ')
  run.mkdir(parents=True,exist_ok=False);(run/'manifest.sha256').write_text(MANIFEST_SHA)
  journal(run,'public_preflight');public_preflight(plan)
  context=ssl.create_default_context();context.minimum_version=ssl.TLSVersion.TLSv1_2
  journal(run,'tls_connect');ftp=AuditedFTP_TLS(context=context,timeout=30);ftp.set_debuglevel(0);ftp.connect(HOST,21);ftp.auth()
  journal(run,'local_credential_input');password=password_for_publish()
  try:
   journal(run,'ftp_login');ftp.login(USER,password)
  finally:del password
  ftp.prot_p();ftp.set_pasv(True);ftp.cwd(REMOTE_ROOT)
  result=apply(ftp,plan,run)
  (run/'receipt.json').write_text(json.dumps(result,indent=2))
  print('公開確認完了: '+str(result['verified_count'])+'/'+str(len(plan['files']))+'。記録: '+str(run/'receipt.json'))
  return 0
 except (Exception,KeyboardInterrupt) as error:
  if run is not None:
   phase=json.loads((run/'phase.json').read_text()) if (run/'phase.json').exists() else {}
   (run/'receipt.json').write_text(json.dumps({'status':'STOPPED_SAFELY','error_type':type(error).__name__,
      'publication_verified':False,'phase':phase,'last_ftp_command':getattr(ftp,'last_command',None)}))
  print('停止しました。自動再試行しません。記録・バックアップを保持してください。');return 2
 finally:
  if fd is not None:os.close(fd)
  if ftp is not None:
   try:ftp.close()
   except Exception:pass
  lock.unlink(missing_ok=True)

if __name__=='__main__':
 try:raise SystemExit(main())
 except Stop as error:
  print('停止しました: '+str(error));raise SystemExit(2)
 except (Exception,KeyboardInterrupt):
  print('停止しました。対象ファイル・確認済みmanifest・起動方法を確認してください。秘密情報は出力しません。');raise SystemExit(2)
