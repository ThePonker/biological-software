"""Small text helpers shared by the views."""


def counted(n: int, singular: str, plural: str = "") -> str:
    """'1 record', '2 records', '24,962 records' (review OBS-27: '1 records')."""
    return f"{n:,} {singular if n == 1 else (plural or singular + 's')}"
