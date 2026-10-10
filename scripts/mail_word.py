"""Explicit, reviewed Word derivations. Originals and receipt holds are immutable."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from mail_draft import encoded, sha


def original(store, selector):
    key = tuple(selector[k] for k in ('account', 'message_id', 'part_id', 'sha256'))
    row = store.db.execute('SELECT source_hash,event_id FROM messages WHERE account=? AND message_id=?', key[:2]).fetchone()
    if not row or row[0] != selector.get('source_hash'):
        raise ValueError('Word source receipt hash mismatch')
    asset = store.db.execute('SELECT content,kind,status FROM attachments WHERE account=? AND message_id=? AND part_id=? AND sha256=?', key).fetchone()
    if not asset or sha(asset[0]) != key[3] or asset[1:] != ('legacy_doc', 'held'):
        raise ValueError('Word original missing, changed or not a held legacy DOC')
    if store.db.execute('SELECT COUNT(*) FROM attachments WHERE account=? AND message_id=? AND part_id=?', key[:3]).fetchone()[0] != 1:
        raise ValueError('Word original has conflicting versions')
    return asset[0], row[1]


def load_extraction(store, extraction_id):
    row = store.db.execute('SELECT payload FROM word_extractions WHERE extraction_id=?', (extraction_id,)).fetchone()
    if not row or sha(row[0]) != extraction_id:
        raise ValueError('Word extraction missing or changed')
    payload = json.loads(row[0])
    if sha(payload['text'].encode('utf-8')) != payload['text_sha256']:
        raise ValueError('Word extracted text hash mismatch')
    original(store, payload['source'])
    return payload


def extract_word(store, selector, antiword='antiword'):
    # Read from the receipt, never from a caller-provided document path.
    source = {k: selector[k] for k in ('account', 'message_id', 'source_hash', 'part_id', 'sha256')}
    data, _ = original(store, source)
    executable = shutil.which(str(antiword))
    if not executable or Path(executable).name not in ('antiword', 'antiword.exe'):
        raise ValueError('installed antiword executable required')
    binary_hash = sha(Path(executable).read_bytes())
    with tempfile.TemporaryDirectory(prefix='.word-', dir=store.database.parent) as directory:
        path = Path(directory) / 'original.doc'
        with path.open('xb') as output:
            os.chmod(path, 0o600)
            output.write(data)
        try:
            result = subprocess.run([executable, '-m', 'UTF-8.txt', '-w', '0', str(path)], capture_output=True, timeout=30, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Word extraction timed out; original preserved') from exc
    if result.returncode or not result.stdout or len(result.stdout) > 8 * 1024 * 1024 or len(result.stderr) > 65536:
        raise ValueError('Word extraction failed or output out of bounds; original preserved')
    text = result.stdout.decode('utf-8', errors='strict')
    if not text.strip() or '\x00' in text or '\ufffd' in text:
        raise ValueError('Word extraction requires complete readable UTF-8 text')
    payload = {'schema_version': 1, 'source': source, 'text': text,
               'text_sha256': sha(text.encode('utf-8')),
               'extractor': {'name': 'antiword', 'binary_sha256': binary_hash, 'arguments': ['-m', 'UTF-8.txt', '-w', '0'],
                             'diagnostic_sha256': sha(result.stderr), 'has_diagnostics': bool(result.stderr),
                             'diagnostics': result.stderr.decode('utf-8', errors='replace')}}
    content = encoded(payload)
    extraction_id = sha(content)
    with store.db:
        original(store, source)
        existing = store.db.execute('SELECT payload FROM word_extractions WHERE extraction_id=?', (extraction_id,)).fetchone()
        if existing and existing[0] != content:
            raise ValueError('existing Word extraction changed')
        store.db.execute('INSERT OR IGNORE INTO word_extractions VALUES (?,?)', (extraction_id, content))
    return {'extraction_id': extraction_id, 'text_sha256': payload['text_sha256'], 'text': text,
            'source': source, 'extractor': payload['extractor'], 'duplicate': bool(existing),
            'status': 'review_required', 'auto_publish': False}


def review_word(store, review):
    if review.get('approved') is not True or not isinstance(review.get('review_reference'), str) or not review['review_reference'].strip():
        raise ValueError('explicit Word text approval and review reference required')
    payload = load_extraction(store, review['extraction_id'])
    if review.get('source') != payload['source'] or review.get('text_sha256') != payload['text_sha256']:
        raise ValueError('Word review source or extracted text mismatch')
    _, event = original(store, payload['source'])
    if not event:
        raise ValueError('verified event required before Word review')
    publications = store.db.execute('SELECT content_hash,reference FROM publications WHERE event_id=?', (event,)).fetchall()
    disposition = review.get('disposition')
    if disposition == 'already_published':
        if (review.get('publication_sha256'), review.get('publication_reference')) not in publications:
            raise ValueError('existing publication evidence required')
    elif disposition == 'draft':
        if publications:
            raise ValueError('event already has publication evidence; no new Word draft approval')
    else:
        raise ValueError('explicit draft or already_published disposition required')
    record = {k: review[k] for k in ('extraction_id', 'source', 'text_sha256', 'approved', 'review_reference', 'disposition')}
    if disposition == 'already_published':
        record.update({k: review[k] for k in ('publication_sha256', 'publication_reference')})
    content = encoded(record)
    with store.db:
        previous = store.db.execute('SELECT payload FROM word_reviews WHERE extraction_id=?', (review['extraction_id'],)).fetchone()
        if previous and previous[0] != content:
            raise ValueError('Word review already recorded differently; original review preserved')
        store.db.execute('INSERT OR IGNORE INTO word_reviews VALUES (?,?)', (review['extraction_id'], content))
    return {'extraction_id': review['extraction_id'], 'disposition': disposition, 'duplicate': bool(previous), 'auto_publish': False}


def reviewed_body(store, selector):
    payload = load_extraction(store, selector['extraction_id'])
    source = {k: selector[k] for k in ('account', 'message_id', 'source_hash', 'part_id', 'sha256')}
    if source != payload['source']:
        raise ValueError('selected Word extraction belongs to a different document')
    row = store.db.execute('SELECT payload FROM word_reviews WHERE extraction_id=?', (selector['extraction_id'],)).fetchone()
    if not row:
        raise ValueError('selected Word extraction has not been approved')
    review = json.loads(row[0])
    if (review.get('approved') is not True or review.get('extraction_id') != selector['extraction_id']
            or review.get('source') != source or review.get('text_sha256') != payload['text_sha256']
            or not review.get('review_reference') or review.get('disposition') not in ('draft', 'already_published')):
        raise ValueError('Word review does not match selected extraction')
    return payload['text'], {'extraction_id': selector['extraction_id'], 'source': source,
                             'text_sha256': payload['text_sha256'], 'extractor': payload['extractor'],
                             'review': review, 'review_sha256': sha(row[0])}
