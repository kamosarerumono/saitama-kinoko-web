"""Adapters for already-exported Gmail connector results and local original assets.

No provider calls or file-URI downloads. Only documented MIME representations
are accepted; a summary, extraction preview or snippet is not a full original.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

MAX_ASSET = 25 * 1024 * 1024


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


def local_part_files(manifest: dict, asset_root: Path, message_id: str) -> dict[str, bytes]:
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
        result[part_id] = resolved.read_bytes()
    return result
