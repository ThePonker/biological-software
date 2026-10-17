"""check_readback -- read a checker's reply to "Export for checking" (17 Oct 2026).

The reply is the exported spreadsheet with its Agree? / Their ID / Notes columns filled in (or
the same columns saved as a CSV). Each line's Ref is found again through the export's row list
(the hidden "_rows" sheet, or refs.json in the export folder); the visible Row id and Species
columns must agree with that list, so a reply cannot land on another export's rows. Nothing here
writes: plan() says what each answer would do, changes_for() gives the field values for one
accepted answer, and the Data Entry page applies them through its grid
(check_readback_dialog.py).

What an accepted answer does (Wil, 17 Oct 2026):
  agree          the mark comes off; Comment gets "conf. <checker>" (and their notes)
  new ID         only when Their ID matches ONE species for certain (the same rule as a pasted
                 name): species and TVK changed, Determiner = checker, the mark comes off;
                 Comment gets "det. <checker> (was <old name>)" (and their notes)
  no / unsure    the row stays marked; their answer, any suggested name and notes go into Check
                 note. Also: "cf." / "?" / "agg." in Their ID, a name that does not match one
                 species, and an unsure answer with a name.
  notes only     the row stays as it is; the notes go into Check note
Review 17 Oct 2026: a line whose Ref appears twice in the reply is not applied at all.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

from DataEntry import staging_repo as repo
from DataEntry.check_export import DATA_SHEET, REFS_FILE, REFS_SHEET

YES = {"yes", "y", "agree", "agreed", "ok", "correct", "true", "x", "✓", "✔"}
NO = {"no", "n", "disagree", "wrong", "false", "✗", "✘"}
UNSURE = {"?", "unsure", "not sure", "maybe", "possibly", "don't know", "dont know", "dk"}
NOT_A_NAME = YES | NO | UNSURE | {"-", "--", "n/a", "na", "none", "same", "as above", "ditto",
                                  "sp", "sp.", "spp", "spp."}
DOUBT = re.compile(r"(\bcf\b|\?|\bagg\b|\baff\b|\bnr\b|\bprob\b|\bpossibly\b)", re.I)

ACTIONS = {
    "agree": "Agreed: the mark comes off",
    "new_id": "New ID: species changed, determiner set, the mark comes off",
    "no": "Not settled: stays marked, their answer in Check note",
    "note": "Notes only: added to Check note",
    "none": "No answer",
    "repeat": "Ref appears more than once in the reply: not applied",
    "mismatch": "Does not match the export's list (another export?): not applied",
    "missing": "Row no longer in the job (committed or deleted)",
    "other_job": "Row belongs to another job",
}
APPLICABLE = ("agree", "new_id", "no", "note")


def _norm(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v if v is not None else "").split())


def _key(v) -> str:
    return _norm(v).casefold()


def _header_index(head: List) -> Dict[str, int]:
    """Column positions, forgiving of case, spaces and '?'."""
    want = {"ref": "ref", "rowid": "row_id", "species": "species", "agree": "agree",
            "theirid": "their_id", "notes": "notes", "note": "notes"}
    out = {}
    for i, h in enumerate(head):
        k = "".join(ch for ch in _key(h) if ch.isalnum())
        if k in want and want[k] not in out:
            out[want[k]] = i
    return out


def _refs_from_file(path: Path) -> Optional[Dict]:
    """refs.json next to the reply, or in the folder above it."""
    for folder in (path.parent, path.parent.parent):
        f = folder / REFS_FILE
        if f.is_file():
            data = json.loads(f.read_text(encoding="utf-8"))
            return {"job_id": data.get("job_id"),
                    "rows": {r["ref"]: {"row_id": r["row_id"], "species": r.get("species", "")}
                             for r in data.get("rows", [])}}
    return None


def read_reply(path) -> Dict:
    """{'lines': [{ref, row_id, species, agree, their_id, notes}], 'refs': {job_id, rows}}.
    Raises ValueError with a plain message when the file cannot be used."""
    path = Path(path)
    refs = None
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            data_ws = (wb[DATA_SHEET] if DATA_SHEET in wb.sheetnames else
                       next((ws for ws in wb.worksheets if ws.title != REFS_SHEET), None))
            rows = [list(r) for r in data_ws.iter_rows(values_only=True)] if data_ws else []
            if REFS_SHEET in wb.sheetnames:
                rr = [list(r) for r in wb[REFS_SHEET].iter_rows(values_only=True)][1:]
                job_ids = {r[2] for r in rr if r and r[0]}
                refs = {"job_id": job_ids.pop() if len(job_ids) == 1 else None,
                        "rows": {str(r[0]): {"row_id": int(r[1]), "species": r[3] or ""}
                                 for r in rr if r and r[0] and r[1] is not None}}
        finally:
            wb.close()
    elif path.suffix.lower() in (".csv", ".txt"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = [r for r in csv.reader(f, dialect)]
    else:
        raise ValueError("Choose the checker's reply: the .xlsx spreadsheet or a .csv.")
    if refs is None:
        refs = _refs_from_file(path)
    if refs is None:
        raise ValueError("This reply has no list of which row each Ref stands for. Keep it in "
                         "(or next to) the export's folder, which holds refs.json, or use the "
                         "spreadsheet itself. Exports made before 17 Oct 2026 have no list: "
                         "export the rows again.")
    if not rows:
        raise ValueError("The reply is empty.")
    idx = _header_index(rows[0])
    if "ref" not in idx:
        raise ValueError("The reply has no Ref column, so its lines cannot be matched to rows.")
    lines = []
    for r in rows[1:]:
        def get(k):
            i = idx.get(k)
            return _norm(r[i]) if i is not None and i < len(r) else ""
        ref = get("ref")
        if ref:
            lines.append({"ref": ref, "row_id_seen": get("row_id"), "species_seen": get("species"),
                          "has_row_id": "row_id" in idx, "has_species": "species" in idx,
                          "agree": get("agree"), "their_id": get("their_id"),
                          "notes": get("notes")})
    return {"lines": lines, "refs": refs}


def answer_kind(agree: str) -> Optional[str]:
    """'yes' / 'no' / 'unsure' / None (blank) / 'other' (a word we do not know)."""
    k = _key(agree).rstrip(".!")
    if not k:
        return None
    if k in YES:
        return "yes"
    if k in NO:
        return "no"
    if k in UNSURE:
        return "unsure"
    if DOUBT.search(k):
        return "unsure"
    return "other"


def is_name(text: str) -> bool:
    """Could Their ID be a species name? Not a yes/no word, a dash, a number or 'same'."""
    k = _key(text).rstrip(".!")
    return bool(k) and k not in NOT_A_NAME and not re.fullmatch(r"[\d\s.,/-]+", k)


def plan(conn, job_id: int, reply: Dict,
         resolve: Optional[Callable[[str], Optional[Dict]]] = None) -> List[Dict]:
    """One item per reply line: the row as it is now, the answer, and what accepting it does.
    resolve(text) -> the one species it matches for certain ({scientific_name, tvk, ...}) or
    None; without it no new ID is ever applied. item['action'] is a key of ACTIONS;
    item['changed'] is True when the row's species is no longer the one exported (then it is
    not ticked by default)."""
    refs = reply["refs"]
    by_id = {r["id"]: r for r in repo.fetch_rows(conn, job_id)}
    seen: Dict[str, int] = {}
    for line in reply["lines"]:
        seen[line["ref"]] = seen.get(line["ref"], 0) + 1
    items = []
    for line in reply["lines"]:
        ref_info = refs["rows"].get(line["ref"])
        row_id = ref_info["row_id"] if ref_info else None
        row = by_id.get(row_id)
        item = {**line, "row_id": row_id, "row": row, "changed": False, "resolved": None,
                "suggested": "",
                "your_id": (row or {}).get("species_name") or (ref_info or {}).get("species", "")}
        kind = answer_kind(line["agree"])
        their = line["their_id"]
        if seen[line["ref"]] > 1:
            item["action"] = "repeat"
        elif refs.get("job_id") not in (None, job_id):
            item["action"] = "other_job"
        elif ref_info is None or (line["has_row_id"] and line["row_id_seen"] != str(row_id)) or \
                (line["has_species"] and line["species_seen"]
                 and _key(line["species_seen"]) != _key(ref_info.get("species"))):
            item["action"] = "mismatch"
        elif row is None:
            item["action"] = "missing"
        else:
            item["changed"] = _key(row.get("species_name")) != _key(ref_info.get("species"))
            current = _key(row.get("species_name"))
            named = is_name(their) and _key(their) != current
            found = resolve(their) if (named and resolve and not DOUBT.search(their)) else None
            if found and _key(found.get("scientific_name")) == current:
                found, named = None, False            # their name is the row's species
            if named and found and kind != "unsure":
                item["action"], item["resolved"] = "new_id", found
            elif named:                                # doubtful, unmatched or unsure: suggest
                item["action"], item["suggested"] = "no", their
            elif kind == "yes":
                item["action"] = "agree"
            elif kind in ("no", "unsure", "other"):
                item["action"] = "no"
            elif line["notes"]:
                item["action"] = "note"
            elif their and _key(their) == current:
                item["action"] = "agree"
            else:
                item["action"] = "none"
        item["tick"] = item["action"] in APPLICABLE and not item["changed"]
        items.append(item)
    return items


def _join(old, new, sep="; ") -> str:
    old, new = _norm(old), _norm(new)
    if not new or new in old:
        return old
    return f"{old}{sep}{new}" if old else new


def changes_for(item: Dict, checker: str) -> Dict:
    """The field values accepting this item writes ('species' is the resolved species dict for
    the grid). Empty dict: nothing to do."""
    row, who, notes = item["row"] or {}, _norm(checker), item["notes"]
    action = item["action"]
    said = f"{who}: " if who else "Checker: "
    if action == "agree":
        add = (f"conf. {who}" if who else "confirmed") + (f" ({notes})" if notes else "")
        return {"check_flag": None, "comment": _join(row.get("comment"), add)}
    if action == "new_id" and item.get("resolved"):
        old = row.get("species_name") or "?"
        add = (f"det. {who}" if who else "re-identified") + f" (was {old})" + \
              (f"; {notes}" if notes else "")
        out = {"species": item["resolved"], "check_flag": None,
               "comment": _join(row.get("comment"), add)}
        if who:
            out["determiner"] = who
        return out
    if action == "no":
        parts = [item["agree"] or ("suggests" if item.get("suggested") else "not agreed")]
        if item.get("suggested"):
            parts.append(item["suggested"])
        if notes:
            parts.append(notes)
        return {"check_note": _join(row.get("check_note"), said + ", ".join(parts))}
    if action == "note":
        return {"check_note": _join(row.get("check_note"), said + notes)}
    return {}
