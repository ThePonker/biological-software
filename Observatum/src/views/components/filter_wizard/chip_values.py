"""What a Filter Wizard chip holds when text is typed and Enter pressed (review SRCH13).

Enter used to add half-typed text ("Coleop", "Oxford") as an exact filter, which matched
nothing. Now: if the text is one of the offered values (ignoring case) the chip holds
that value; otherwise it becomes a "contains" chip ("~text"), shown as *text*.
The filter builder reads "~" as contains (services/filter_builder.text_match).
"""

from typing import Iterable, Tuple

PARTIAL = "~"


def typed_chip(text: str, offered: Iterable[str]) -> Tuple[str, str]:
    """(chip value, chip label text) for text typed and entered without a pick."""
    text = (text or "").strip()
    folded = text.casefold()
    for value in offered or ():
        if value is not None and str(value).casefold() == folded:
            return str(value), str(value)
    return PARTIAL + text, f"*{text}*"


def chip_label(value: str) -> str:
    """Label text for a stored chip value: '~oak' -> '*oak*'."""
    value = str(value)
    return f"*{value[1:]}*" if value.startswith(PARTIAL) else value
