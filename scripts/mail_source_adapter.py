"""Adapters for already-exported Gmail connector results and local original assets.

No provider calls or file-URI downloads. Only documented MIME representations
are accepted; a summary, extraction preview or snippet is not a full original.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

MAX_ASSET = 25 * 1024 * 1024


def transferred_files_manifest(message: dict, transfers: dict, account: str, message_id: str) -> dict:
    """Join normalized full MIME with local original-transfer receipts, without I/O.

    This is our local receipt contract, not a Gmail/Library response schema. The
    authorized transfer caller records original bytes' SHA before this ingestion.
    No file_uri, Library ID, provider call or filename-derived ID is invented here.
    """
    if not isinstance(message, dict) or not isinstance(transfers, dict):
        raise ValueError('full MIME and transfer receipt objects required')
    if message.get('id') != message_id or transfers.get('message_id') != message_id or transfers.get('account') != account:
        raise ValueError('transfer account/message_id mismatch')
    if 'raw' in message or not isinstance(message.get('payload'), dict):
        raise ValueError('transferred files require full MIME; raw identity is separate')
    records = transfers.get('files')
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise ValueError('nonempty bounded original transfer files list required')
    parts = []

    def walk(part):
        mime = part.get('mimeType', '')
        if mime == 'message/rfc822':
            return  # Existing parser holds nested forwards rather than ingesting them.
        children = part.get('parts', [])
        if children:
            for child in children:
                walk(child)
        elif part.get('filename') or (mime and not mime.startswith(('text/', 'multipart/'))):
            parts.append(part)

    walk(message['payload'])
    # Validate inline originals too, before matching any transferred files.
    # Parser fallback IDs must never alias an attachment's real provider ID.
    part_ids = set()
    for part in parts:
        part_id = part.get('partId')
        if not isinstance(part_id, str) or not part_id.strip():
            raise ValueError('original MIME part_id required; cannot infer it')
        if part_id in part_ids:
            raise ValueError('duplicate MIME part_id')
        part_ids.add(part_id)
    result, used_parts, used_paths = [], set(), set()
    for record in records:
        if not isinstance(record, dict) or record.get('message_id') != message_id:
            raise ValueError('each transfer must identify the same parent message')
        if record.get('source_kind') != 'original':
            raise ValueError('original transfer required; extraction previews are not originals')
        expected = record.get('sha256')
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('original transfer SHA256 required')
        relative = record.get('relative_path')
        if not isinstance(relative, str) or any(p in ('', '.', '..') for p in relative.split('/')) or '\\' in relative or ':' in relative:
            raise ValueError('canonical relative original path required')
        attachment_id = record.get('attachment_id')
        filename = record.get('filename')
        if attachment_id is not None:
            if not isinstance(attachment_id, str) or not attachment_id or record.get('attachment_id_complete') is not True or '...' in attachment_id or '\u2026' in attachment_id:
                raise ValueError('complete attachment_id required; do not use truncated IDs')
            matches = [p for p in parts if p.get('body', {}).get('attachmentId') == attachment_id]
        else:
            if not isinstance(filename, str) or not filename:
                raise ValueError('complete attachment_id or exact filename required')
            matches = [p for p in parts if p.get('filename') == filename]
        if len(matches) != 1:
            raise ValueError('attachment match missing or ambiguous')
        part = matches[0]
        part_id = part.get('partId')
        if 'part_id' in record and record['part_id'] != part_id:
            raise ValueError('transfer part_id mismatch')
        if filename is not None and filename != part.get('filename'):
            raise ValueError('transfer filename mismatch')
        if part_id in used_parts or relative in used_paths:
            raise ValueError('duplicate transferred part or original path')
        inline = part.get('body', {}).get('data')
        if inline is not None:
            data = base64.b64decode(inline + '=' * (-len(inline) % 4), altchars=b'-_', validate=True)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('transfer SHA256 conflicts with inline MIME original')
        used_parts.add(part_id)
        used_paths.add(relative)
        result.append({'part_id': part_id, 'relative_path': relative, 'sha256': expected})
    if any(p.get('body', {}).get('data') is None and p.get('partId') not in used_parts for p in parts):
        raise ValueError('missing transferred original for attachment MIME part')
    return {'account': account, 'message_id': message_id, 'files': sorted(result, key=lambda r: r['part_id'])}


def connector_message(export: dict) -> dict:
    """Unwrap one MCP JSON result, then normalize connector snake_case MIME fields."""
    if not isinstance(export, dict) or export.get('isError'):
        raise ValueError('successful single-message connector export required')
    if 'structuredContent' in export:
        export = export['structuredContent']
    elif isinstance(export.get('content'), list):
        texts = [block.get('text') for block in export['content'] if block.get('type') == 'text']
        if len(texts) != 1:
            raise ValueError('single complete JSON text block required')
        export = json.loads(texts[0])
    if isinstance(export, dict) and isinstance(export.get('api_content'), dict):
        export = export['api_content']
    if not isinstance(export, dict):
        raise ValueError('single-message API object required; batch or thread exports need individual messages')
    message_id = export.get('id') or export.get('message_id')
    if not isinstance(message_id, str) or not message_id:
        raise ValueError('immutable provider message id missing')
    if 'raw' in export:
        if not isinstance(export['raw'], str):
            raise ValueError('raw RFC2822 base64url string required')
        return {'id': message_id, 'raw': export['raw']}
    payload = export.get('payload')
    if not isinstance(payload, dict) or not (payload.get('mime_type') or payload.get('mimeType')):
        raise ValueError('full MIME payload or raw RFC2822 required; summaries are insufficient')

    def normalize(part):
        body = part.get('body') or {}
        mime = part.get('mime_type') or part.get('mimeType') or ''
        normalized = {
            'mimeType': mime,
            'filename': part.get('filename') or '',
            'headers': part.get('headers') or [],
            'body': {},
            'parts': [normalize(child) for child in part.get('parts', [])],
        }
        if 'part_id' in part or 'partId' in part:
            normalized['partId'] = part.get('part_id', part.get('partId'))
        attachment_id = body.get('attachment_id') or body.get('attachmentId')
        if attachment_id:
            normalized['body']['attachmentId'] = attachment_id
        binary = body.get('base64_url_content', body.get('data'))
        if binary is not None:
            normalized['body']['data'] = binary
        elif mime.startswith('text/') and isinstance(body.get('content'), str):
            normalized['body']['decodedContent'] = body['content']
            normalized['body']['contentTruncated'] = bool(body.get('content_truncated') or part.get('content_truncated'))
        return normalized

    return {'id': message_id, 'payload': normalize(payload)}


def local_part_files(manifest: dict, asset_root: Path, message_id: str, *, require_unique_paths: bool = False) -> dict[str, bytes]:
    """Map stable part IDs to originals already staged inside one private directory.

    Provider file_uri/extraction_file_uri requires an authorized external download
    before this call. It is never opened here. Paths must be operator-supplied
    relative paths, and cannot escape asset_root (including via symlinks).
    """
    if manifest.get('message_id') != message_id:
        raise ValueError('attachment manifest message_id mismatch')
    root = asset_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('asset root directory required')
    records = manifest.get('files')
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError('bounded attachment files list required')
    result = {}
    used_paths = set()
    for record in records:
        part_id, relative = record.get('part_id'), record.get('relative_path')
        if not isinstance(part_id, str) or not isinstance(relative, str) or not relative:
            raise ValueError('stable part_id and relative_path required; file_uri is not a local original')
        path = Path(relative)
        if path.is_absolute():
            raise ValueError('asset path must be relative')
        resolved = (root / path).resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError('asset path escapes private root or is not a file')
        if resolved.stat().st_size > MAX_ASSET:
            raise ValueError('local original asset too large')
        if part_id in result:
            raise ValueError('duplicate MIME part in attachment manifest')
        if require_unique_paths and resolved in used_paths:
            raise ValueError('duplicate transferred original path')
        used_paths.add(resolved)
        data = resolved.read_bytes()
        if 'sha256' in record and record['sha256'] != hashlib.sha256(data).hexdigest():
            raise ValueError('local original SHA256 mismatch; transfer evidence preserved')
        result[part_id] = data
    return result
