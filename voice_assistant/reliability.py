"""Accuracy helpers: task classification for model routing, honesty rules, action-claim guard.

All offline. Friday's small model invents details, so factual questions go to a larger model,
temperature is lowered for facts, and replies that claim a tool action nobody ran are blocked.
"""

import re

HONESTY_RULES = (
    "Accuracy rules: answer only from your solid knowledge or the facts supplied below. "
    "If you are not sure of a specific fact such as a date, number, name, quote, or recent event, say you are not sure; never guess or invent. "
    "You are offline and have no live data, so for news, weather, prices, scores, or 'latest' questions say you cannot check right now. "
    "You do not remember anything about the user beyond the facts supplied below; if asked about something not there, say you don't have it. "
    "Never say you set a reminder, saved a note, opened or closed an app, changed volume, added a skill, or touched a file; "
    "those happen only through Friday's tools, which run before this reply, and none ran for this request. "
)

# Temperature by task type: low for facts, a little warmer for casual talk.
TEMPERATURE = {'factual': 0.2, 'reasoning': 0.3, 'casual': 0.78}

_CASUAL = re.compile(
    r"^(?:thanks?|thank you|ok(?:ay)?|cool|nice|great|good|awesome|got it|sure|yes|no|yeah|nope|hmm+|haha+|"
    r"how are you|how's it going|what's up|good (?:morning|night|evening)|you there|are you there|"
    r"i(?:'m| am) (?:fine|good|tired|bored|back)|tell me a joke|say something|sing)\b", re.I)
_FACT_QUESTION = re.compile(
    r"\b(?:who (?:is|was|are|were|invented|discovered|wrote|founded|won)|when (?:is|was|did|does|were)|where (?:is|was|are|did)|"
    r"which (?:country|city|year|person|company|planet|language)|how (?:many|much|far|old|tall|long|big|fast|hot|cold|heavy)|"
    r"what (?:is|are|was|were) (?:the|a|an)\b|what year|what date|capital of|population of|meaning of|definition of|"
    r"define\b|explain\b|difference between|how does|how do|how did|why (?:is|are|do|does|did|was)|"
    r"tell me about|what causes|history of|formula|calculate|convert|translate|spell)\b", re.I)
_PERSONAL = re.compile(r"\b(?:my|i|me|mine)\b", re.I)


def classify_task(message):
    """Return 'casual', 'factual', or 'reasoning' for model and temperature choice."""
    text = (message or '').strip()
    low = text.lower()
    words = re.findall(r"[\w'-]+", low)
    if not words:
        return 'casual'
    if _CASUAL.match(low) and len(words) <= 8:
        return 'casual'
    if _FACT_QUESTION.search(low):
        return 'factual'
    if len(words) >= 40 or re.search(r"\b(?:compare|analy[sz]e|evaluate|debug|design|plan|step[- ]by[- ]step|pros and cons)\b", low):
        return 'reasoning'
    if text.endswith('?') and len(words) >= 5 and not _PERSONAL.search(low):
        return 'factual'
    return 'casual'


_ACTION_VERB = (r"(?:set|saved|added|created|scheduled|opened|closed|launched|started|stopped|muted|unmuted|"
                r"turned|changed|adjusted|increased|decreased|raised|lowered|installed|updated|applied|rolled back|"
                r"deleted|removed|erased|renamed|moved|written|wrote|made|checked|scanned|noted|remembered|stored|"
                r"enrolled|registered|identified|recognized|will remind|reminded|booked|sent|called)")
_ACTION_CLAIM = re.compile(
    rf"\b(?:i(?:'ve| have)?|i just|i'll go ahead and|just|all set[,.]?\s*i(?:'ve)?)\s+(?:successfully\s+|now\s+|already\s+|just\s+)?{_ACTION_VERB}\b"
    r"|\b(?:your|the)\s+(?:reminder|note|idea|skill|file|alarm|timer)\s+(?:is|has been|was)\s+(?:set|saved|added|created|done|ready)\b"
    r"|\b(?:reminder|note|idea|skill|file)\s+(?:set|saved|added|created)\b"
    r"|\b(?:volume|app|application|voice profile|speaker profile)\s+(?:is|has been|was)\s+(?:now\s+)?(?:muted|up|down|opened|closed|increased|decreased|saved|created|enrolled|registered)\b",
    re.I)
_TARGET = re.compile(
    r"\b(?:reminders?|notes?|ideas?|skills?|files?|folders?|alarms?|timers?|profiles?|volume|apps?|applications?|"
    r"notepad|calculator|chrome|word|excel|code update|\.txt|\.md|memory|calendar|schedule|email|message)\b", re.I)


def grounded_context(name, city, memory_facts, skills_text=''):
    """Facts block that goes at the end of the system prompt."""
    lines = [f"Known facts about the user: name={name}; city={city}."]
    if memory_facts:
        lines.append(f"Saved notes/ideas relevant to this question: {memory_facts}")
    else:
        lines.append("No saved notes or ideas matched this question.")
    return ' '.join(lines)


# ---- Added: stricter claim detection, history hygiene, corrections, honest recall ----

_FUTURE_CLAIM = re.compile(
    r"\b(?:i(?:'ll| will)|let me|i'm going to|i am going to|going to)\s+(?:go ahead and\s+)?(?:now\s+)?"
    r"(?:delete|remove|erase|create|set|save|add|open|close|rename|move|check|scan|look|find|restore|mute|install)\b"
    r"|\bare you sure you want (?:me )?to (?:delete|remove|erase)\b"
    r"|\byou(?:'ve| have| had)?\s+(?:already\s+)?confirmed\b"
    r"|\bi(?:'ve| have)?\s+confirmed\b", re.I)
_STALE_NOISE = ("I can't confirm that.", "I didn't catch which file action", "I couldn't form a useful reply")
_FALSE_RETENTION_CLAIM = re.compile(
    r"\b(?:45 seconds|about 45 seconds)\b.{0,180}\b(?:cleared|blank slate|start from scratch)\b"
    r"|\b(?:conversation log|chat history)\b.{0,120}\b(?:cleared|erased)\b",
    re.I,
)


def claims_unverified_action(reply, user_text=''):
    """True when a chat reply claims a tool action. ai_chat runs only when no tool ran, so any claim is false."""
    reply = reply or ''
    if _FUTURE_CLAIM.search(reply) and _TARGET.search(f'{reply} {user_text}'):
        return True
    return bool(_ACTION_CLAIM.search(reply) and _TARGET.search(f'{reply} {user_text}'))


def trustworthy_history(history):
    """Drop assistant turns that claim tool actions or are failure noise so the model cannot quote old lies."""
    kept = []
    for item in history or []:
        content = str(item.get('content', ''))
        if item.get('role') == 'assistant' and (
                claims_unverified_action(content, '') or content.startswith(_STALE_NOISE)
                or _FALSE_RETENTION_CLAIM.search(content)):
            continue
        kept.append(item)
    return kept


_FILE_TALK = re.compile(r"\b(?:files?|folders?|directory|delete[ds]?|\w+\.(?:txt|md|exe|docx?|csv|json|py))\b", re.I)


def mentions_files(message, recent=()):
    return bool(_FILE_TALK.search(message or '') or any(_FILE_TALK.search(str(m)) for m in recent))


_CORRECTION = re.compile(
    r"(?:\b(?:what|everything|all)\b.*\byou(?:'ve| have)?\s+(?:been\s+)?(?:saying|said|told me)\b.*\b(?:incorrect|wrong|false|untrue|not true|made up)\b)"
    r"|\byou(?:'re| are)\s+(?:wrong|lying|hallucinating|making (?:things|that|it|stuff) up|not (?:right|correct|telling the truth))\b"
    r"|\b(?:that(?:'s| is| was)|this is)\s+(?:not true|incorrect|wrong|false|a lie|made up)\b"
    r"|\byou\s+(?:made|are making)\s+(?:that|it|things|stuff)\s+up\b|\bstop (?:lying|making (?:things|stuff) up|hallucinating)\b"
    r"|\bthat(?:'s| is| was) not (?:what )?(?:i|happened)\b", re.I)

CORRECTION_REPLY = ("You're right, I'm sorry. When no command runs, I can make things up, and I did that with the files. "
                    "I only trust results from my own commands, like creating, listing or adding to a file. "
                    "I've dropped those earlier answers so I won't repeat them.")


def is_correction(text):
    return bool(_CORRECTION.search(text or ''))


_LAST_CONVO = re.compile(
    r"\bwhat (?:was|were) (?:your|our|the) (?:last|previous|earlier) (?:conversation|chat|talk|topic|question)\b"
    r"|\bwhat did (?:we|i) (?:talk|speak|discuss|say)(?: about)?(?: (?:last|earlier|before|just now))?\b"
    r"|\bwhat were we (?:talking|speaking|discussing)(?: about)?\b|\bwhat have we been (?:talking|discussing)\b", re.I)


def is_last_conversation_query(text):
    return bool(_LAST_CONVO.search(text or ''))


def last_conversation_reply(history, current_command=''):
    """Quote the real previous exchange; never paraphrase from memory."""
    items = list(history or [])
    if items and items[-1].get('role') == 'user' and items[-1].get('content', '').strip() == (current_command or '').strip():
        items = items[:-1]
    users = [i for i in items if i.get('role') == 'user'
             and len(str(i.get('content', '')).split()) > 2 and not is_last_conversation_query(i.get('content', ''))]
    if not users:
        return "We haven't really talked about anything yet."
    last = str(users[-1]['content']).strip()
    follow = []
    seen = False
    for i in items:
        if i is users[-1]:
            seen = True
            continue
        if seen and i.get('role') == 'assistant':
            follow.append(str(i['content']).strip())
            break
    reply = f'Before this, you said: "{last[:140]}".'
    if follow and not claims_unverified_action(follow[0], ''):
        reply += f' I answered: "{follow[0][:140]}".'
    return reply
