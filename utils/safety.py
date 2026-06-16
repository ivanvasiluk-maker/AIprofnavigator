CRISIS_PHRASES = [
    "не хочу жить",
    "убить себя",
    "суицид",
    "покончить с собой",
    "самоповреждение",
    "я себя порежу",
    "не могу больше жить",
    "лучше умереть",
]


def has_crisis_content(text: str) -> bool:
    text_low = (text or "").lower()
    return any(phrase in text_low for phrase in CRISIS_PHRASES)
