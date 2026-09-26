"""
Sex summary formatting — one place, so the format cannot drift.

Specimen sex is shown in at least three places: Data Entry's species readout,
the Insect Collection taxonomic sidebar, and the collection dashboard. Writing
the format three times is how this codebase has produced nine instances of the
same rule drifting apart, so it is written once here.

    from shared.sex_summary import format_sex_summary, classify_sex

    format_sex_summary(3, 4, 0)   ->  "\u26423 \u26404"
    format_sex_summary(2, 1, 4)   ->  "\u26422 \u26401 +4"
    format_sex_summary(0, 0, 7)   ->  ""          <- nothing worth saying
    format_sex_summary(0, 0, 0)   ->  ""

The rule: show the breakdown only when something has been sexed. Telling
someone that seven unsexed specimens are seven unsexed specimens is noise, and
the caller is already displaying the total. `+n` means "and this many more, not
yet sexed" — it shrinks visibly as a collection is worked through.

"Unknown" — examined and could not be told — currently folds into the `+`.
There are two such records in the whole collection. If that grows, it wants
separating: examined-and-unknown is a determination, not an absence of one.
"""

MALE = "\u2642"
FEMALE = "\u2640"


def classify_sex(value):
    """'m' | 'f' | None for a stored sex value.

    Tolerant of what is actually in the database and what might be typed:
    Male / male / M / 1m all give 'm'; Female / F / 2f give 'f'; Unknown,
    blank and anything unrecognised give None.

    Female is tested first: both words would otherwise match on an initial
    scan, and 'f' is unambiguous where 'm' is not.
    """
    s = (value or "").strip().lower()
    if not s:
        return None
    if s.startswith("f") or s.startswith("\u2640") or "female" in s:
        return "f"
    if s.startswith("m") or s.startswith("\u2642"):
        return "m"
    return None


def count_sexes(values):
    """(male, female, other) across an iterable of stored sex values.

    `other` counts everything not resolvable to male or female — unsexed,
    blank, and "Unknown" alike.
    """
    male = female = other = 0
    for v in values:
        k = classify_sex(v)
        if k == "m":
            male += 1
        elif k == "f":
            female += 1
        else:
            other += 1
    return male, female, other


def format_sex_summary(male, female, other=0):
    """The bracketed part, or '' when nothing has been sexed.

    The caller supplies the total and the brackets:

        n = male + female + other
        s = format_sex_summary(male, female, other)
        label = f"Specimens {n}" + (f" ({s})" if s else "")
    """
    male = int(male or 0)
    female = int(female or 0)
    other = int(other or 0)
    if not male and not female:
        return ""
    parts = []
    if male:
        parts.append(f"{MALE}{male}")
    if female:
        parts.append(f"{FEMALE}{female}")
    if other:
        parts.append(f"+{other}")
    return " ".join(parts)


def label_with_sexes(prefix, male, female, other=0):
    """Complete label: 'Spec. 7 (\u26423 \u26404)', or 'Spec. 7' when unsexed."""
    total = int(male or 0) + int(female or 0) + int(other or 0)
    summary = format_sex_summary(male, female, other)
    return f"{prefix} {total}" + (f" ({summary})" if summary else "")
