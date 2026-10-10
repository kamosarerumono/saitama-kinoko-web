#!/usr/bin/env python3
"""Offline manuscript intake. No network, conversion, execution, or publication."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sqlite3
import unicodedata
import zipfile
from datetime import date
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from mail_source_adapter import connector_message, local_part_files

MAX_MESSAGE = 40 * 1024 * 1024
MAX_PART = 25 * 1024 * 1024
MAX_UNPACKED = 80 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def b64(data: str) -> bytes:
    if len(data) > MAX_MESSAGE * 2:
        raise ValueError('encoded part too large')
    return base64.b64decode(data + '=' * (-len(data) % 4), altchars=b'-_', validate=True)


def decode_text(data: bytes, charset: str | None) -> tuple[str | None, str | None]:
    try:
        text = data.decode(charset or 'utf-8', errors='strict')
    except (UnicodeError, LookupError):
        return None, 'body_decode_failed'
    # Google exports sometimes carry already-corrupted JIS escape sequences.
    if '\ufffd' in text or '\x1b' in text or re.search(r'\$B.{4,}\(B', text):
        return None, 'body_mojibake'
    return text, None


def classify(filename: str, mime: str, data: bytes) -> tuple[str, str]:
    """Classify signatures and containers; never run Office or TNEF converters."""
    suffix = Path(filename.lower()).suffix
    if len(data) > MAX_PART:
        return 'oversize', 'held'
    if filename.lower() == 'winmail.dat' or mime == 'application/ms-tnef':
        return 'tnef', 'held'
    if suffix in {'.docm', '.xlsm', '.pptm'}:
        return 'macro_document', 'held'
    if suffix in {'.docx', '.xlsx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 4000 or sum(x.file_size for x in entries) > MAX_UNPACKED:
                    return 'unsafe_archive', 'held'
                names = {x.filename for x in entries}
                if any(x.flag_bits & 1 or '..' in Path(x.filename).parts or x.filename.startswith('/') for x in entries):
                    return 'unsafe_archive', 'held'
                if any('vbaproject' in name.lower() or name.lower().endswith('.bin') for name in names):
                    return 'macro_document', 'held'
                expected = 'word/document.xml' if suffix == '.docx' else 'xl/workbook.xml'
                if '[Content_Types].xml' not in names or expected not in names:
                    return 'signature_mismatch', 'held'
                return suffix[1:], 'review_required'
        except (zipfile.BadZipFile, ValueError):
            return 'signature_mismatch', 'held'
    if suffix == '.doc':
        return ('legacy_doc', 'held') if data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')) else ('signature_mismatch', 'held')
    if suffix == '.pdf':
        return ('pdf', 'review_required') if data.startswith(b'%PDF-') else ('signature_mismatch', 'held')
    if suffix in {'.jpg', '.jpeg'}:
        return ('jpeg', 'review_required') if data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9') else ('signature_mismatch', 'held')
    return 'unsupported', 'held'


def parse_eml(raw: bytes) -> dict:
    if len(raw) > MAX_MESSAGE:
        raise ValueError('message too large')
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    headers = [(key.lower(), str(value)) for key, value in msg.items()]
    texts, attachments, holds = [], [], []

    def walk(part, part_id):
        if part.is_multipart():
            if part.get_content_type() == 'message/rfc822':
                holds.append('nested_forward_requires_review')
                return
            for index, child in enumerate(part.iter_parts()):
                walk(child, f'{part_id}.{index}')
            return
        content = part.get_payload(decode=True) or b''
        if part.defects:
            holds.append('mime_defect')
        filename = part.get_filename()
        mime = part.get_content_type()
        if filename or part.get_content_disposition() == 'attachment' or not mime.startswith('text/'):
            attachments.append({'part_id': part_id, 'filename': filename or '', 'mime': mime, 'data': content})
        elif mime == 'text/plain':
            text, error = decode_text(content, part.get_content_charset())
            if error:
                holds.append(error)
            elif text:
                texts.append(text)
        else:
            holds.append('html_body_requires_review')
    walk(msg, '0')
    if msg.defects:
        holds.append('mime_defect')
    return {'headers': headers, 'body': '\n'.join(texts), 'attachments': attachments, 'holds': holds}


def parse_gmail(message: dict, attachment_data: dict | None = None, part_data: dict | None = None) -> dict:
    """Use full payload only; snippet never substitutes for body.

    attachment_data maps provider attachmentId to previously fetched base64url bytes.
    It is a transport lookup, not an identity or deduplication key.
    """
    attachment_data = attachment_data or {}
    part_data = part_data or {}
    payload = message.get('payload') or {}
    headers = [(x['name'].lower(), x['value']) for x in payload.get('headers', [])]
    texts, attachments, holds = [], [], []

    def walk(part, fallback):
        mime = part.get('mimeType', '')
        part_id = part.get('partId')
        if part_id is None:
            part_id = fallback
        if mime == 'message/rfc822':
            holds.append('nested_forward_requires_review')
            return
        for index, child in enumerate(part.get('parts', [])):
            walk(child, f'{fallback}.{index}')
        body = part.get('body') or {}
        encoded = body.get('data')
        filename = part.get('filename') or ''
        attachment_id = body.get('attachmentId')
        if mime == 'text/plain' and 'decodedContent' in body and not filename:
            holds.append('connector_decoded_text_requires_original')
            if body.get('contentTruncated'):
                holds.append('body_content_truncated')
                return
            text, error = decode_text(body['decodedContent'].encode('utf-8'), 'utf-8')
            if error:
                holds.append(error)
            elif text:
                texts.append(text)
            return
        if str(part_id) in part_data:
            if part.get('parts') or (mime.startswith('text/') and not filename):
                raise ValueError('local asset mapping must identify an attachment MIME part')
            encoded = base64.urlsafe_b64encode(part_data[str(part_id)]).decode()
            used_part_data.add(str(part_id))
        if encoded is None and attachment_id:
            encoded = attachment_data.get(attachment_id)
        if encoded is None:
            if attachment_id or filename or mime.startswith('text/'):
                holds.append('missing_part_data')
            return
        data = b64(encoded)
        if filename or not mime.startswith('text/'):
            attachments.append({'part_id': str(part_id), 'filename': filename, 'mime': mime, 'data': data})
        elif mime == 'text/plain':
            content_type = next((h['value'] for h in part.get('headers', []) if h['name'].lower() == 'content-type'), '')
            charset_match = re.search(r'charset\s*=\s*["\']?([^;"\'\s]+)', content_type, re.I)
            text, error = decode_text(data, charset_match[1] if charset_match else None)
            if error:
                holds.append(error)
            elif text:
                texts.append(text)
        else:
            holds.append('html_body_requires_review')
    used_part_data = set()
    walk(payload, '0')
    if used_part_data != set(part_data):
        raise ValueError('attachment manifest contains an unknown MIME part')
    return {'headers': headers, 'body': '\n'.join(texts), 'attachments': attachments, 'holds': holds}


def gmail_identity(message: dict) -> str:
    """Stable full MIME envelope; attachment hydration and transport IDs are mutable."""
    def stable(part):
        mime = part.get('mimeType', '')
        body = part.get('body') or {}
        result = {key: part.get(key) for key in ('partId', 'mimeType', 'filename', 'headers')}
        result['parts'] = [stable(child) for child in part.get('parts', [])]
        if mime.startswith('text/') and not part.get('filename'):
            result['body_data'] = body.get('data')
            result['decoded_content'] = body.get('decodedContent')
            result['content_truncated'] = body.get('contentTruncated')
        return result
    return digest(json.dumps({'id': message.get('id'), 'payload': stable(message.get('payload') or {})}, sort_keys=True, ensure_ascii=False).encode())


def event_identity(name: str, held_on: str) -> tuple[str, str]:
    date.fromisoformat(held_on)
    normalized = re.sub(r'\s+', '', unicodedata.normalize('NFKC', name)).casefold()
    if not normalized:
        raise ValueError('event name required')
    return digest(f'{held_on}\0{normalized}'.encode()), normalized


def sender_context(parsed: dict, candidates: dict) -> dict:
    headers = parsed['headers']
    values = lambda key: [value for name, value in headers if name == key]
    addresses = getaddresses(values('from'))
    sender = addresses[0][1].lower() if len(addresses) == 1 else ''
    subject = ' '.join(values('subject'))
    list_mail = bool(values('list-id') or values('list-post') or values('mailing-list'))
    auth = ' '.join(values('authentication-results'))
    # Headers are reported evidence from an offline export, not cryptographic verification.
    # No status here authorizes publication, even when all checks report pass.
    if list_mail:
        status = 'mailing_list_fail' if re.search(r'(dkim|spf|dmarc)=fail', auth, re.I) else 'mailing_list_unverified'
    elif len(values('authentication-results')) > 1:
        status = 'reported_auth_conflict'
    elif re.search(r'(dkim|spf|dmarc)=fail', auth, re.I):
        status = 'reported_direct_fail'
    elif re.search(r'\bmx\.google\.com\s*;', auth, re.I) and re.search(r'\bdmarc=pass\b', auth, re.I) and re.search(r'\b(dkim|spf)=pass\b', auth, re.I):
        status = 'reported_direct_pass'
    elif re.search(r'(dkim|spf|dmarc)=fail', auth, re.I):
        status = 'reported_direct_fail'
    else:
        status = 'unverified'
    excluded = []
    if list_mail:
        excluded.append('mailing_list')
    if values('x-wp-notification') or 'wordpress' in sender or re.search(r'\bwordpress\b', subject, re.I):
        excluded.append('wordpress_notification')
    if re.search(r'パスワード|認証|役員|名簿|会員管理|ログイン|password|verification|one.time.code', subject, re.I):
        excluded.append('administrative_mail')
    if not sender:
        excluded.append('ambiguous_sender')
    if sender in [address.lower() for address in candidates.get('excluded_addresses', [])]:
        excluded.append('excluded_sender')
    known = next((person for person in candidates.get('people', []) if sender in [x.lower() for x in person.get('addresses', [])]), None)
    forwarded = bool(re.search(r'(^|\n)(?:From:|差出人:)|forwarded message|転送メッセージ', parsed['body'], re.I) or re.match(r'\s*(fwd?|転送):', subject, re.I))
    return {'outer_sender': sender, 'candidate_id': known.get('id') if known else None, 'candidate_name': known.get('name') if known else None, 'auth': status, 'auth_evidence': auth, 'excluded': excluded, 'forwarded': forwarded}


SCHEMA = '''
CREATE TABLE IF NOT EXISTS messages (
 account TEXT NOT NULL, message_id TEXT NOT NULL, source_hash TEXT NOT NULL,
 source BLOB NOT NULL, body TEXT NOT NULL, context TEXT NOT NULL,
 event_id TEXT, author TEXT, holds TEXT NOT NULL,
 PRIMARY KEY(account, message_id));
CREATE TABLE IF NOT EXISTS events (
 event_id TEXT PRIMARY KEY, event_name TEXT NOT NULL, event_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attachments (
 account TEXT NOT NULL, message_id TEXT NOT NULL, part_id TEXT NOT NULL,
 sha256 TEXT NOT NULL, filename TEXT NOT NULL, mime TEXT NOT NULL,
 kind TEXT NOT NULL, status TEXT NOT NULL, content BLOB NOT NULL,
 PRIMARY KEY(account, message_id, part_id, sha256),
 FOREIGN KEY(account, message_id) REFERENCES messages(account,message_id));
CREATE TABLE IF NOT EXISTS source_snapshots (
 account TEXT NOT NULL, message_id TEXT NOT NULL, sha256 TEXT NOT NULL, source BLOB NOT NULL,
 PRIMARY KEY(account,message_id,sha256),
 FOREIGN KEY(account,message_id) REFERENCES messages(account,message_id));
CREATE TABLE IF NOT EXISTS corrections (
 account TEXT NOT NULL, message_id TEXT NOT NULL, target_message_id TEXT NOT NULL,
 PRIMARY KEY(account, message_id,target_message_id),
 FOREIGN KEY(account,message_id) REFERENCES messages(account,message_id),
 FOREIGN KEY(account,target_message_id) REFERENCES messages(account,message_id));
CREATE TABLE IF NOT EXISTS publications (
 event_id TEXT NOT NULL REFERENCES events(event_id), content_hash TEXT NOT NULL,
 reference TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(event_id,content_hash));
CREATE TABLE IF NOT EXISTS metadata_reviews (
 account TEXT NOT NULL, message_id TEXT NOT NULL, metadata TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(account,message_id) REFERENCES messages(account,message_id));
'''


class Intake:
    def __init__(self, database: Path, candidates: dict | None = None):
        self.candidates = candidates or {}
        database = Path(database)
        database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if database.parent.stat().st_mode & 0o077:
            raise ValueError('database directory must be private (0700); use a dedicated private directory')
        # umask also protects SQLite rollback journals.
        old = os.umask(0o077)
        try:
            self.db = sqlite3.connect(database)
            os.chmod(database, 0o600)
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript(SCHEMA)
        finally:
            os.umask(old)

    def close(self):
        self.db.close()

    def receive(self, account: str, message_id: str, source: bytes, parsed: dict, metadata: dict | None = None, identity_hash: str | None = None) -> dict:
        metadata = metadata or {}
        if not account.strip() or not message_id.strip():
            raise ValueError('account and provider message_id required')
        if len(source) > MAX_MESSAGE:
            raise ValueError('message too large')
        if len(parsed['attachments']) > 1000 or sum(len(part['data']) for part in parsed['attachments']) > MAX_MESSAGE:
            raise ValueError('attachment set too large')
        context = sender_context(parsed, self.candidates)
        holds = set(parsed['holds'])
        if not parsed['body'] and not parsed['attachments']:
            holds.add('missing_full_body_or_assets')
        if context['auth'] != 'reported_direct_pass':
            holds.add('authentication_requires_review')
        if not context['candidate_id']:
            holds.add('unknown_sender')
        if context['forwarded']:
            holds.add('forwarded_author_requires_review')
        holds.update(context['excluded'])
        name, held_on = metadata.get('event_name'), metadata.get('event_date')
        event_id = None
        if name and held_on and metadata.get('event_verified') is True:
            event_id, _ = event_identity(name, held_on)
        else:
            holds.add('event_identity_requires_review')
        author = metadata.get('author') if metadata.get('author_verified') is True else None
        correction = metadata.get('corrects_message_id')
        if re.search(r'訂正|修正|差し替え|correction', ' '.join(v for k,v in parsed['headers'] if k == 'subject'), re.I) and not correction:
            holds.add('correction_target_requires_review')
        source_hash = identity_hash or digest(source)
        existing = self.db.execute('SELECT source_hash FROM messages WHERE account=? AND message_id=?', (account,message_id)).fetchone()
        if existing and existing[0] != source_hash:
            raise ValueError('same receipt key has different source; existing receipt preserved')
        with self.db:
            if correction:
                target = self.db.execute('SELECT event_id FROM messages WHERE account=? AND message_id=?', (account,correction)).fetchone()
                if not target or not event_id or target[0] != event_id or correction == message_id:
                    raise ValueError('correction target must exist in same account and verified event')
            if event_id:
                self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?)', (event_id,name,held_on))
            if not existing:
                self.db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)', (account,message_id,source_hash,source,parsed['body'],json.dumps(context,ensure_ascii=False),event_id,author,json.dumps(sorted(holds))))
            else:
                # Retry cannot silently change event, author, or correction attribution.
                row = self.db.execute('SELECT event_id,author FROM messages WHERE account=? AND message_id=?',(account,message_id)).fetchone()
                previous_targets = [r[0] for r in self.db.execute('SELECT target_message_id FROM corrections WHERE account=? AND message_id=?',(account,message_id))]
                if row != (event_id,author) or previous_targets != ([correction] if correction else []):
                    raise ValueError('receipt metadata changed; review existing receipt explicitly')
            self.db.execute('INSERT OR IGNORE INTO source_snapshots VALUES (?,?,?,?)', (account,message_id,digest(source),source))
            for part in parsed['attachments']:
                kind, status = classify(part['filename'],part['mime'],part['data'])
                self.db.execute('INSERT OR IGNORE INTO attachments VALUES (?,?,?,?,?,?,?,?,?)', (account,message_id,part['part_id'],digest(part['data']),part['filename'],part['mime'],kind,status,part['data']))
            # Derive durable asset holds from the complete receipt, including
            # previously saved originals omitted by this retry. Do this after
            # insertion so conflicts within one incoming batch are held too.
            if self.db.execute('''SELECT 1 FROM attachments
                    WHERE account=? AND message_id=? GROUP BY part_id
                    HAVING COUNT(DISTINCT sha256)>1 LIMIT 1''', (account,message_id)).fetchone():
                holds.add('attachment_content_conflict')
            holds.update('attachment_held:' + kind for (kind,) in self.db.execute(
                "SELECT DISTINCT kind FROM attachments WHERE account=? AND message_id=? AND status='held'",
                (account,message_id)))
            self.db.execute('UPDATE messages SET holds=? WHERE account=? AND message_id=?', (json.dumps(sorted(holds)),account,message_id))
            if correction:
                self.db.execute('INSERT OR IGNORE INTO corrections VALUES (?,?,?)',(account,message_id,correction))
        return {'account':account,'message_id':message_id,'duplicate':bool(existing),'event_id':event_id,'auto_publish':False,'holds':sorted(holds)}

    def assign(self, account: str, message_id: str, metadata: dict) -> dict:
        """Explicitly attach a previously unassigned receipt to a reviewed event.

        This records review evidence, never publication approval. Existing event
        attribution cannot be silently reassigned and correction sources must be
        reviewed before their later corrections.
        """
        if metadata.get('event_verified') is not True:
            raise ValueError('verified event metadata required')
        event_id, _ = event_identity(metadata['event_name'], metadata['event_date'])
        with self.db:
            row = self.db.execute('SELECT event_id,author,holds FROM messages WHERE account=? AND message_id=?', (account,message_id)).fetchone()
            if not row:
                raise ValueError('receipt does not exist')
            if row[0] and row[0] != event_id:
                raise ValueError('already assigned event cannot be changed')
            author = metadata.get('author') if metadata.get('author_verified') is True else row[1]
            if row[1] and author != row[1]:
                raise ValueError('already reviewed author cannot be changed')
            correction = metadata.get('corrects_message_id')
            if correction:
                target = self.db.execute('SELECT event_id FROM messages WHERE account=? AND message_id=?', (account,correction)).fetchone()
                if not target or target[0] != event_id or correction == message_id:
                    raise ValueError('correction target must exist in same account and verified event')
                previous = self.db.execute('SELECT target_message_id FROM corrections WHERE account=? AND message_id=?', (account,message_id)).fetchone()
                if previous and previous[0] != correction:
                    raise ValueError('already reviewed correction cannot be changed')
                ancestors = self.db.execute('''WITH RECURSIVE chain(target) AS (
                    SELECT ? UNION SELECT c.target_message_id FROM corrections c JOIN chain ON c.message_id=chain.target WHERE c.account=?
                    ) SELECT target FROM chain''', (correction,account)).fetchall()
                if (message_id,) in ancestors:
                    raise ValueError('correction would create a cycle')
            holds = set(json.loads(row[2]))
            holds.discard('event_identity_requires_review')
            if correction:
                holds.discard('correction_target_requires_review')
            self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?)', (event_id,metadata['event_name'],metadata['event_date']))
            self.db.execute('UPDATE messages SET event_id=?,author=?,holds=? WHERE account=? AND message_id=?', (event_id,author,json.dumps(sorted(holds)),account,message_id))
            if correction:
                self.db.execute('INSERT OR IGNORE INTO corrections VALUES (?,?,?)', (account,message_id,correction))
            self.db.execute('INSERT INTO metadata_reviews(account,message_id,metadata) VALUES (?,?,?)', (account,message_id,json.dumps(metadata,ensure_ascii=False)))
        return {'event_id':event_id,'auto_publish':False,'holds':sorted(holds)}

    def record_publication(self, event_id: str, content_hash: str, reference: str):
        """Record evidence of a separately completed publication; performs no publication."""
        if not re.fullmatch('[0-9a-f]{64}', content_hash) or not reference.strip():
            raise ValueError('SHA256 and publication reference required')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO publications(event_id,content_hash,reference) VALUES (?,?,?)',(event_id,content_hash,reference))

    def summary(self) -> dict:
        events = []
        for event_id,name,held_on in self.db.execute('SELECT * FROM events ORDER BY event_date,event_id'):
            receipts = []
            for account,message_id,body,context,author,holds in self.db.execute('SELECT account,message_id,body,context,author,holds FROM messages WHERE event_id=? ORDER BY account,message_id',(event_id,)):
                assets = [{'part_id':p,'sha256':h,'filename':f,'kind':k,'status':s} for p,h,f,k,s in self.db.execute('SELECT part_id,sha256,filename,kind,status FROM attachments WHERE account=? AND message_id=?',(account,message_id))]
                receipts.append({'account':account,'message_id':message_id,'body':body,'context':json.loads(context),'author':author,'holds':json.loads(holds),'assets':assets,'corrects':[r[0] for r in self.db.execute('SELECT target_message_id FROM corrections WHERE account=? AND message_id=?',(account,message_id))]})
            events.append({'event_id':event_id,'event_name':name,'event_date':held_on,'receipts':receipts,'published':[{'sha256':h,'reference':r} for h,r in self.db.execute('SELECT content_hash,reference FROM publications WHERE event_id=?',(event_id,))],'auto_publish':False})
        return {'events':events,'unassigned':[{'account':a,'message_id':m,'holds':json.loads(h)} for a,m,h in self.db.execute('SELECT account,message_id,holds FROM messages WHERE event_id IS NULL')],'auto_publish':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=Path('data/private/intake.sqlite3'))
    parser.add_argument('--candidates',type=Path)
    sub = parser.add_subparsers(dest='command',required=True)
    receive = sub.add_parser('receive')
    receive.add_argument('--account',required=True)
    receive.add_argument('--message-id',required=True)
    receive.add_argument('--format',choices=['eml','gmail','gmail-connector'],required=True)
    receive.add_argument('--input',type=Path,required=True)
    receive.add_argument('--metadata',type=Path)
    receive.add_argument('--attachment-data',type=Path)
    receive.add_argument('--attachment-files',type=Path)
    receive.add_argument('--asset-root',type=Path)
    assign = sub.add_parser('assign')
    assign.add_argument('--account',required=True)
    assign.add_argument('--message-id',required=True)
    assign.add_argument('--metadata',type=Path,required=True)
    sub.add_parser('summary')
    pub = sub.add_parser('record-publication')
    pub.add_argument('--event-id',required=True)
    pub.add_argument('--sha256',required=True)
    pub.add_argument('--reference',required=True)
    args = parser.parse_args()
    read_json = lambda path: json.loads(path.read_text()) if path else {}
    store = Intake(args.db,read_json(args.candidates))
    try:
        if args.command == 'receive':
            raw = args.input.read_bytes()
            identity_hash = None
            if args.format == 'eml':
                parsed = parse_eml(raw)
                source = raw
            else:
                msg = json.loads(raw)
                if args.format == 'gmail-connector':
                    msg = connector_message(msg)
                if msg.get('id') != args.message_id:
                    raise ValueError('Gmail id does not match receipt message_id')
                part_data = {}
                if args.attachment_files:
                    if not args.asset_root:
                        raise ValueError('--asset-root required with --attachment-files')
                    part_data = local_part_files(read_json(args.attachment_files),args.asset_root,args.message_id)
                if 'raw' in msg:
                    original = b64(msg['raw'])
                    parsed = parse_eml(original)
                    identity_hash = digest(original)
                else:
                    parsed = parse_gmail(msg,read_json(args.attachment_data),part_data)
                    identity_hash = gmail_identity(msg)
                source = raw
            result = store.receive(args.account,args.message_id,source,parsed,read_json(args.metadata),identity_hash)
        elif args.command == 'assign':
            result = store.assign(args.account,args.message_id,read_json(args.metadata))
        elif args.command == 'record-publication':
            store.record_publication(args.event_id,args.sha256,args.reference)
            result = {'recorded':True,'auto_publish':False}
        else:
            result = store.summary()
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
