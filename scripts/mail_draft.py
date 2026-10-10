"""Private, immutable review bundles from Intake. No site writes or publishing."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def literal(text: str) -> str:
    # A raw HTML block keeps Astro's Markdown autolinks/smart quotes from
    # rewriting the manuscript. Only our fixed tags are active HTML.
    return '<div class="mail-body">\n<p>' + html.escape(text).replace('\n', '<br>\n') + '</p>\n</div>'


def draft_files(store, selection: dict, site_root: Path) -> dict[str, bytes]:
    """Read one consistent DB snapshot; preserve holds and explicit provenance."""
    event_id = selection['event_id']
    event = store.db.execute('SELECT event_name,event_date FROM events WHERE event_id=?', (event_id,)).fetchone()
    if not event:
        raise ValueError('verified event does not exist')
    target = selection['target']
    if target.get('collection', 'reikai') != 'reikai':
        raise ValueError('only the existing reikai article format is supported')
    slug, title = target['slug'], target['title']
    if not isinstance(slug, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9][a-z0-9_-]{0,79}', slug) or not slug.startswith(event[1] + '-'):
        raise ValueError('target slug must begin with verified event date and use lowercase ASCII')
    if not isinstance(title, str) or not title.strip() or len(title) > 300 or any(ord(c) < 32 for c in title):
        raise ValueError('single-line title required')
    root = Path(site_root).resolve(strict=True)
    target_path = f'src/content/reikai/{slug}.md'
    destination = root / target_path
    if not destination.resolve().is_relative_to(root) or destination.is_symlink():
        raise ValueError('target escapes site root or is a symlink')
    current_hash = sha(destination.read_bytes()) if destination.exists() else None
    holds = set()
    if current_hash != target.get('expected_sha256'):
        holds.add('target_content_changed')

    receipts = {}
    for account, mid, source_hash, source, body, author, saved_holds in store.db.execute(
            'SELECT account,message_id,source_hash,source,body,author,holds FROM messages WHERE event_id=? ORDER BY account,message_id', (event_id,)):
        assets = [{'part_id': part, 'sha256': h, 'kind': kind, 'status': status} for part, h, kind, status in store.db.execute(
            'SELECT part_id,sha256,kind,status FROM attachments WHERE account=? AND message_id=? ORDER BY part_id,sha256', (account,mid))]
        receipts[(account, mid)] = {
            'account': account, 'message_id': mid, 'source_hash': source_hash,
            'original_sha256': sha(source), 'body_sha256': sha(body.encode('utf-8')),
            'body': body, 'author': author, 'holds': json.loads(saved_holds), 'assets': assets,
            'source_snapshots': [r[0] for r in store.db.execute('SELECT sha256 FROM source_snapshots WHERE account=? AND message_id=? ORDER BY sha256', (account,mid))],
            'corrects': [r[0] for r in store.db.execute('SELECT target_message_id FROM corrections WHERE account=? AND message_id=? ORDER BY target_message_id', (account,mid))],
        }
    successors = {}
    for key, receipt in receipts.items():
        # Until the correction target is reviewed, no selected older source in
        # this event can be assumed unaffected. Selecting around it is not review.
        if 'correction_target_requires_review' in receipt['holds']:
            holds.add('correction_target_requires_review')
        for old in receipt['corrects']:
            successors.setdefault((key[0], old), []).append(key[1])
    if any(len(v) > 1 for v in successors.values()):
        holds.add('ambiguous_corrections')

    derivation = None
    body_selection = selection['body_source']
    if 'extraction_id' in body_selection:
        from mail_word import reviewed_body
        body_text, derivation = reviewed_body(store, body_selection)

    def selected(record):
        key = (record['account'], record['message_id'])
        if key not in receipts:
            raise ValueError('selected source must belong to the verified event')
        receipt = receipts[key]
        if record.get('source_hash') != receipt['source_hash']:
            raise ValueError('selected source hash mismatch')
        effective_holds = set(receipt['holds'])
        # Scope this exception to the reviewed source DOC. Other held assets,
        # receipt holds (including HTML), and the original DB remain untouched.
        if derivation and key == (body_selection['account'], body_selection['message_id']):
            held_assets = [a for a in receipt['assets'] if a['status'] == 'held']
            if len(held_assets) == 1 and held_assets[0] == {
                    'part_id': body_selection['part_id'], 'sha256': body_selection['sha256'],
                    'kind': 'legacy_doc', 'status': 'held'}:
                effective_holds.discard('attachment_held:legacy_doc')
        holds.update(effective_holds)
        if key in successors:
            holds.add('selected_source_superseded')
        return receipt

    body_receipt = selected(selection['body_source'])
    if not derivation:
        body_text = body_receipt['body']
    if not body_text.strip():
        holds.add('missing_selected_body')
    files = {}
    photos = []
    seen = set()
    requested_assets = selection.get('assets', [])
    if not isinstance(requested_assets, list) or len(requested_assets) > 1000:
        raise ValueError('bounded asset selection required')
    for item in requested_assets:
        selected(item)
        key = (item['account'], item['message_id'], item['part_id'], item['sha256'])
        if key in seen:
            raise ValueError('duplicate selected asset')
        seen.add(key)
        row = store.db.execute('SELECT content,kind,status FROM attachments WHERE account=? AND message_id=? AND part_id=? AND sha256=?', key).fetchone()
        if not row or sha(row[0]) != key[3]:
            raise ValueError('selected asset missing or content hash mismatch')
        if row[1:] != ('jpeg', 'review_required'):
            holds.add('selected_asset_requires_manual_conversion')
        reference = item.get('review_reference')
        if not isinstance(reference, str) or not reference.strip():
            holds.add('selected_asset_requires_review')
        # Only reviewed JPEG originals can be staged; never execute/convert Office/PDF.
        name = f'public/reikai/{event[1][:4]}/{key[3]}.jpg'
        asset_destination = root / name
        if not asset_destination.resolve().is_relative_to(root) or asset_destination.is_symlink():
            raise ValueError('asset target escapes site root or is a symlink')
        if asset_destination.exists() and sha(asset_destination.read_bytes()) != key[3]:
            holds.add('target_asset_changed')
        photos.append((name, row[0]))

    publications = [{'sha256': h, 'reference': ref} for h, ref in store.db.execute(
        'SELECT content_hash,reference FROM publications WHERE event_id=? ORDER BY content_hash', (event_id,))]
    if derivation and (publications or derivation['review']['disposition'] == 'already_published'):
        holds.add('selected_word_already_published')
    if not holds:
        front = f'---\ntitle: {json.dumps(title, ensure_ascii=False)}\ndate: {event[1]}\n'
        if body_receipt['author']:
            front += f'reporter: {json.dumps(body_receipt["author"], ensure_ascii=False)}\n'
        content = front + '---\n\n' + literal(body_text) + '\n'
        for name, data in photos:
            files[name] = data
            content += f'\n![]({name.removeprefix("public")})\n'
        files[target_path] = content.encode('utf-8')
    # The private manifest contains evidence, never sender data in site artifacts.
    manifest = {
        'schema_version': 1, 'auto_publish': False,
        'status': 'held' if holds else 'review_required', 'holds': sorted(holds),
        'selection': selection, 'event_name': event[0], 'event_date': event[1],
        'target_path': target_path, 'target_current_sha256': current_hash,
        'operation': 'update' if current_hash else 'create',
        'sources': [{k: v for k, v in r.items() if k != 'body'} for r in receipts.values()],
        'publications': publications,
        'body_derivation': derivation,
        'files': [{'path': name, 'sha256': sha(data)} for name, data in sorted(files.items())],
    }
    files['review.json'] = encoded(manifest)
    return files


def readback(directory: Path, files: dict[str, bytes]):
    actual = set()
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink in draft bundle')
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(files) or any((directory / name).read_bytes() != data for name, data in files.items()):
        raise ValueError('draft bundle content mismatch; existing output preserved')


def prepare_draft(store, selection: dict, site_root: Path) -> dict:
    for root in (Path(site_root).resolve(), Path(__file__).resolve().parents[1]):
        if store.database.is_relative_to(root) and store.database.relative_to(root).parts[0] != 'data':
            raise ValueError('in-repository draft storage must be under ignored data/')
    with store.db:
        store.db.execute('BEGIN')
        files = draft_files(store, selection, site_root)
    bundle_id = sha(files['review.json'])
    parent = store.database.parent / 'drafts'
    if parent.is_symlink():
        raise ValueError('draft directory must not be a symlink')
    parent.mkdir(mode=0o700, exist_ok=True)
    if parent.stat().st_mode & 0o077:
        raise ValueError('draft directory must be private (0700)')
    output = parent / bundle_id
    duplicate = output.exists()
    if output.is_symlink():
        raise ValueError('draft bundle must not be a symlink')
    if not duplicate:
        # Temporary directory cleanup owns only files created by this invocation.
        with tempfile.TemporaryDirectory(prefix='.prepare-', dir=parent) as temporary:
            staging = Path(temporary) / 'bundle'
            staging.mkdir(mode=0o700)
            for name, data in files.items():
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with path.open('xb') as handle:
                    os.chmod(path, 0o600)
                    handle.write(data)
            staging.rename(output)
    readback(output, files)
    manifest = json.loads(files['review.json'])
    return {'bundle': str(output), 'bundle_id': bundle_id, 'duplicate': duplicate,
            'status': manifest['status'], 'holds': manifest['holds'],
            'file_count': len(manifest['files']), 'auto_publish': False}


def verify_draft(store, bundle_id: str, site_root: Path) -> dict:
    if not re.fullmatch('[0-9a-f]{64}', bundle_id):
        raise ValueError('bundle id must be SHA256')
    parent = store.database.parent / 'drafts'
    directory = parent / bundle_id
    if parent.is_symlink() or directory.is_symlink():
        raise ValueError('draft bundle must not be a symlink')
    manifest_path = directory / 'review.json'
    if manifest_path.is_symlink():
        raise ValueError('draft manifest must not be a symlink')
    manifest = manifest_path.read_bytes()
    if sha(manifest) != bundle_id:
        raise ValueError('draft manifest hash mismatch')
    with store.db:
        store.db.execute('BEGIN')
        current = draft_files(store, json.loads(manifest)['selection'], site_root)
    if current['review.json'] != manifest:
        raise ValueError('draft is stale; prepare again from current intake and target')
    readback(directory, current)
    return {'bundle_id': bundle_id, 'verified': True, 'status': json.loads(manifest)['status'], 'auto_publish': False}
