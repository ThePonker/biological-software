"""Lector desktop window (stage B, 12 Oct 2026): `python -m Lector gui`.

app.py           the window: navigation, screens, background task line
searches.py      Saved searches (dashboard)
builder*.py      New / edit search: species, names, filters, preview
history.py       A search's runs and what changed
review_*.py      Reading list: page list, the page, review marks
export_screen.py Word / Excel / PDF / text exports
workers.py       background tasks (QThread) with progress and cancel
style.py         Observatum's theme applied to Lector; common.py the shared screen frame

The screens use LectorService only (Lector/service.py, Lector/SERVICE_API.md).
"""
