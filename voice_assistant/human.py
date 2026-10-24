"""Varied, natural phrasing so Friday does not repeat the same sentence every time."""

import random
from datetime import datetime

_last = {}


def pick(key, options):
    """Random option, never the same one twice in a row for a key."""
    options = list(options)
    choices = [o for o in options if o != _last.get(key)] or options
    choice = random.choice(choices)
    _last[key] = choice
    return choice


def part_of_day(now=None):
    hour = (now or datetime.now()).hour
    return 'morning' if hour < 12 else 'afternoon' if hour < 17 else 'evening'


def wake_ack(name=''):
    who = f', {name}' if name else ''
    return pick('wake', [
        'Yeah?', f"I'm here{who}.", 'Go ahead.', "What's up?", 'Listening.', f'Yes{who}?',
        'Right here.', 'Mm-hm?', f"I'm all ears.", 'What do you need?',
    ])


def greeting(name='', now=None):
    pod = part_of_day(now)
    who = f', {name}' if name else ''
    return pick('greet', [
        f'Hey{who}. What can I do for you?', f'Good {pod}{who}. What are we up to?',
        f'Hi{who}. Good to hear you.', f'Hey{who}. How is your {pod} going?',
        f"Hello{who}. I'm ready when you are.", f"Good {pod}{who}. What's on your mind?",
    ])
