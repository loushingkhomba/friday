"""Offline parsing of spoken file requests (create file, ask for folder location)."""

import os
import re

from human import pick

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_NOISE_WORDS = {'a', 'an', 'the', 'new', 'blank', 'empty', 'text', 'physical', 'file', 'document', 'please',
                'friday', "friday's", 'folder', 'name', 'named', 'called', 'is', 'as', 'it', 'my', 'me', 'now'}
_CREATE = re.compile(r'\b(?:create|make|write|generate|save)\b', re.I)
_FILE_WORD = re.compile(r'\b(?:text\s+)?(?:file|document)\b', re.I)


def clean_filename(raw):
    """Turn a spoken name into a safe file name; empty string if nothing usable."""
    name = re.sub(r'\s+', ' ', raw or '').strip(' \t\r\n.,!?;:\'"')
    words = name.split(' ')
    while words and words[0].lower() in _NOISE_WORDS:
        words.pop(0)
    name = ' '.join(words).strip()
    name = _INVALID_CHARS.sub('', name).strip(' .')
    if not name or name.lower() in _NOISE_WORDS:
        return ''
    name = name[:60]
    if not os.path.splitext(name)[1]:
        name += '.txt'
    return name


def parse_create_file(text):
    """Return (filename, content) when text asks to create a file, else None.
    filename is '' when the user did not give a usable name."""
    text = (text or '').strip()
    if not _CREATE.search(text) or not _FILE_WORD.search(text):
        return None
    if re.search(r'\b(?:skill|code|update|patch|reminder|delete|remove|erase|trash)\b', text, re.I):
        return None
    if re.search(r'\b(?:read|open|find|search|show|delete|remove)\b', text, re.I) and not re.search(r'\b(?:create|make|write|generate)\b', text, re.I):
        return None

    work = text
    content = ''
    content_match = re.search(r'\b(?:with\s+(?:the\s+)?(?:content|text)|containing|that\s+says|saying)\s+(.+)$', work, re.I)
    if content_match:
        content = content_match.group(1).strip(' \t\r\n.,')
        work = work[:content_match.start()]

    # Drop location phrases so "in the friday's folder" is never taken as a name.
    work = re.sub(
        r"\b(?:in|inside|under|within|into|at|to|on)\s+(?:(?:this|the|that|your|my)\s+)*(?:friday(?:\s*'?s)?\s+)?(?:folder|directory|friday(?:\s*'?s)?\s*folder)\b",
        ' ', work, flags=re.I)

    patterns = (
        r"\b(?:named|called|titled|name\s+(?:is|it)|name\s+as|with\s+(?:the\s+)?name|file\s*name\s+(?:is|as))\s+(.+)$",
        r"\b(.+?)\s+as\s+(?:the\s+)?file\s*name\b",
        r"\b(?:text\s+)?(?:file|document)\s+(?:with|for|about)\s+(.+)$",
        r"\b(?:text\s+)?(?:file|document)\s+(.+)$",
    )
    candidate = ''
    for pattern in patterns:
        match = re.search(pattern, work, re.I)
        if match:
            candidate = match.group(1)
            if pattern.startswith(r"\b(.+?)\s+as"):
                candidate = re.sub(r'^.*\b(?:with|named|called)\s+', '', candidate, flags=re.I)
            candidate = re.split(r'\b(?:and|then|with|in|inside)\b|,', candidate, maxsplit=1, flags=re.I)[0]
            candidate = re.sub(r'^(?:the\s+)?(?:blank|empty|new)\s+', '', candidate.strip(), flags=re.I)
            if clean_filename(candidate):
                break
            candidate = ''
    return clean_filename(candidate), content


def parse_clear_file_request(text, last_file=None):
    """Return a file target for content-clearing requests; None means no clear request."""
    value = re.sub(r'^\s*(?:(?:hey\s+)?friday[,:\s]+)?', '', text or '', flags=re.I).strip()
    value = re.sub(r'^(?:(?:could|can|would|will) you\s+|i want(?: you)? to\s+|i need(?: you)? to\s+|please\s+)+', '', value, flags=re.I)
    value = re.sub(r'\s+(?:please|now)[.!?]*$', '', value, flags=re.I).strip()
    if not re.match(r'^(?:clear|empty|wipe)\b', value, re.I):
        return None
    body = re.sub(r'^(?:clear|empty|wipe)\s+', '', value, flags=re.I).strip(' ,.!?')
    has_file_context = bool(re.search(
        r'\b(?:file|document|contents?|content)\b|\.(?:txt|md|csv|json|py|log|ya?ml|ini)\b', body, re.I))
    if not has_file_context:
        return None
    # Remove intent words around a filename, preserving the spoken filename itself.
    target = body
    target = re.sub(r'^(?:(?:the\s+)?(?:contents?|content)\s+(?:of|in|from)\s+)', '', target, flags=re.I)
    target = re.sub(r'^(?:of|in)\s+', '', target, flags=re.I)
    target = re.sub(r'^(?:(?:the|this|that|my|a|an)\s+)?(?:text\s+)?(?:file|document)\b\s*', '', target, flags=re.I)
    target = re.sub(r'^(?:(?:the\s+)?(?:contents?|content)\s+(?:of|in|from)\s+)', '', target, flags=re.I)
    target = re.sub(r'^(?:called|named)\s+', '', target, flags=re.I)
    target = re.sub(r'\s+(?:file|document)\s+(?:contents?|content)$', '', target, flags=re.I)
    target = re.sub(r'\s+(?:contents?|content)$', '', target, flags=re.I)
    target = re.sub(r'\s+(?:text\s+)?(?:file|document)$', '', target, flags=re.I)
    target = target.strip(' ,.!?')
    if target.casefold() in {'it', 'this', 'that', 'content', 'contents', 'the file', 'this file', 'that file'}:
        target = ''
    return target or (last_file or '')


def is_folder_location_question(text):
    low = (text or '').lower()
    return bool(re.search(
        r"\bwhere(?:'s| is| are)?\b.*\b(?:your|friday(?:'s)?|that|the|this)\b.*\b(?:folder|directory)\b"
        r"|\b(?:path|location)\b.*\b(?:folder|directory)\b|\b(?:folder|directory)\b.*\b(?:path|location)\b"
        r"|\bwhat(?:'s| is)\b.*\bfolder\b", low))


def spoken_folder_location(root):
    """Short spoken description of the folder (last few path parts)."""
    parts = [p for p in os.path.normpath(root).split(os.sep) if p and not p.endswith(':')]
    return f"Friday's folder is {', then '.join(parts[-4:])}. Full path: {os.path.normpath(root)}."


_APPEND_VERB = re.compile(r'^\s*(?:(?:please|now|also|and|okay|ok)[,\s]+)*(?:add|put|write|append|type|insert|save)\b\s*(.*)$', re.I | re.S)
_LEAD_FILLER = re.compile(r'^(?:(?:the|this|that|following|some|more|new)\s+)*(?:content|text|line|words?|following)?\s*(?:that\s+says|saying|:|-)?\s*', re.I)


def _strip_content(raw):
    raw = (raw or '').strip(' \t\r\n,:')
    raw = _LEAD_FILLER.sub('', raw).strip(' \t\r\n,:')
    return raw.strip().strip('"').strip()


def parse_append_file(text, last_file=None):
    """Return (filename, content) for requests like 'add hello to the file ideas'.
    filename falls back to last_file for 'it' / 'the file'; '' if unknown. None if not a file append."""
    verb = _APPEND_VERB.match(text or '')
    if not verb:
        return None
    body = verb.group(1).strip()
    if re.match(r'^(?:a\s+)?(?:skill|reminder|note|idea|code|update)\b', body, re.I):
        return None
    if re.match(r'^(?:a|an|new)\s+(?:\w+\s+){0,3}(?:file|document)\b', body, re.I):
        return None

    # "... to/in the file NAME : content"
    lead = re.match(
        r"^(?:(?:this|that|it|the\s+following)\s+)?(?:(?:some\s+)?(?:content|text)\s+)?(?:in|into|to|inside|onto)\s+(?:the\s+|that\s+|this\s+|my\s+)?(?:text\s+)?file\b\s*(?:named\s+|called\s+)?([\w .'-]*?)\s*(?:[:,]|\bsaying\b|\bthat\s+says\b|\bwith\s+(?:the\s+)?(?:content|text)\b|\bthat\b)\s*(.+)$",
        body, re.I | re.S)
    if lead:
        name = clean_filename(lead.group(1)) or (last_file or '')
        return name, _strip_content(lead.group(2))

    target = re.search(
        r"\s+(?:in|into|to|inside|onto)\s+(?:(?:the|that|this|my)\s+)?(?:(?:text\s+)?file\b\s*(?:named\s+|called\s+)?(.*)|(it)|([\w -]+\.\w{1,5}))\s*[.!?]?$",
        body, re.I)
    if not target:
        return None
    named = (target.group(1) or target.group(3) or '').strip()
    if not named and not target.group(2) and 'file' not in target.group(0).lower():
        return None
    if target.group(2) and not last_file:
        return None
    name = clean_filename(named) or (last_file or '')
    if named and not clean_filename(named):
        name = last_file or ''
    return name, _strip_content(body[:target.start()])


_FOLDER_WORD = re.compile(r"\b(?:folder|directory|files)\b", re.I)
_LIST_VERB = re.compile(r"\b(?:list|show|scan|check|refresh|look|see|what|which|read|tell|any|got|is there|are there|contents?)\b", re.I)
_FILE_ACTION = re.compile(r"\b(?:delete|remove|create|make|write|add|append|rename|move|copy|save|erase|trash)\b", re.I)


def is_list_files_request(text):
    """'scan the folder again', 'what files do you have', 'list the files'."""
    low = (text or '').lower()
    if not _FOLDER_WORD.search(low) or _FILE_ACTION.search(low) and not re.search(r'\b(?:list|show|scan|what)\b', low):
        return False
    return bool(_LIST_VERB.search(low)) and not is_folder_location_question(low)


def is_vague_file_request(text):
    """A file/folder action we could not parse. Better to say so than let the chat model pretend."""
    low = (text or '').lower()
    if len(low.split()) > 14 or re.match(r'^(?:how|why|explain|what is|what are|tell me about)\b', low):
        return False
    return bool(re.search(r"\b(?:files?|folders?|\.txt|\.md)\b", low) and _FILE_ACTION.search(low)
                or re.search(r"\b(?:check|scan|see|look)\b.*\b(?:file|folder)\b", low))


VAGUE_FILE_REPLY = ("I didn't catch which file action you want. You can say: create a file called name; "
                    "add text to the file name; delete the file name; restore name; or list the files.")


def list_files_reply(root, limit=12):
    """Real directory listing; never guesses."""
    try:
        entries = sorted(e for e in os.listdir(root) if not e.startswith('.'))
    except OSError:
        return "I can't read Friday's folder right now."
    files = [e for e in entries if os.path.isfile(os.path.join(root, e))]
    folders = [e for e in entries if os.path.isdir(os.path.join(root, e))]
    if not files and not folders:
        return "Friday's folder is empty."
    parts = []
    if files:
        shown = files[:limit]
        parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''}: " + ', '.join(shown)
                     + (f', and {len(files) - limit} more' if len(files) > limit else ''))
    if folders:
        parts.append(f"{len(folders)} folder{'s' if len(folders) != 1 else ''}: " + ', '.join(folders[:limit]))
    return pick('list_lead', ["Friday's folder has ", "Right now Friday's folder has ", "I'm seeing "]) + '; '.join(parts) + '.'


_ACTION_CLAIM = re.compile(
    r"\b(?:i(?:'ve| have)?|i just|just)\s+(?:successfully\s+|now\s+|already\s+)?"
    r"(?:deleted|removed|erased|created|made|written|wrote|added|appended|renamed|moved|saved|checked|scanned|"
    r"looked (?:in|through|at)|refreshed|verified|confirmed)\b", re.I)
_FILE_CONTEXT = re.compile(r"\b(?:files?|folders?|directory|\.txt|\.md)\b", re.I)


def claims_unverified_file_action(reply, user_text=''):
    """True when a chat reply says it did a file action that no tool performed."""
    return bool(_ACTION_CLAIM.search(reply or '') and _FILE_CONTEXT.search(f'{reply} {user_text}'))
