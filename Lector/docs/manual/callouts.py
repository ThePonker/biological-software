"""The numbered callouts drawn on each screenshot: one table, so they can be regenerated after
the screens change. Each row is (screen, target, number, label).

screen  one of the keys in make_screens.SHOTS
target  an objectName ("recordsTable") or an attribute path from the window, written
        "attr:screens.review.filters" (a dict key is written as a dotted name; "dialog."
        starts at the dialog for a shot that is a dialog). If a target is missing the
        callout is skipped and make_screens says so.
label   what manual.md says about it (manual.md is written by hand from this table)
"""
CALLOUTS = (
    # Saved searches
    ("saved_searches", "attr:screens.searches.filter_box", 1,
     "Type here to show only the searches that match."),
    ("saved_searches", "attr:screens.searches.table", 2,
     "One row for each saved search. The More menu at the end of a row holds Delete search."),
    ("saved_searches", "attr:nav_buttons.review", 3, "The Reading list."),
    ("saved_searches", "attr:key_link", 4,
     "The BHL key. Press it to see how to get the key or to paste a new one."),
    # New search
    ("builder", "attr:screens.builder.species_edit", 1,
     "Type a species. Lector suggests names even if you misspell them."),
    ("builder", "attr:screens.builder.find_btn", 2, "Find looks the name up in UKSI."),
    ("builder", "attr:screens.builder.mode_box", 3,
     "Choose a free-text search for an author or a place."),
    ("builder", "attr:screens.builder.names", 4,
     "The names to search. Names UKSI doubts are held back, with the reason."),
    ("builder", "attr:screens.builder.filters", 5, "Years and journals."),
    ("builder", "attr:screens.builder.run_btn", 6, "Save the search and fetch the pages."),
    # A search's page
    ("search_page", "attr:screens.history.summary", 1, "The search's names, years, journals and limits."),
    ("search_page", "attr:screens.history.refresh_check", 2,
     "Tick to ask BHL again for every name; untick to re-apply changed filters only."),
    ("search_page", "attr:screens.history.run_btn", 3, "Run (or Run again)."),
    ("search_page", "attr:screens.history.run_list", 4, "Every run, newest first."),
    ("search_page", "attr:screens.history.tabs", 5,
     "What changed in the chosen run: new, no longer matched, unchanged."),
    ("search_page", "attr:screens.history.review_btn", 6, "Read the new pages."),
    # Reading list
    ("reading_list", "attr:screens.review.search_box", 1, "Which search you are reading."),
    ("reading_list", "attr:screens.review.show_box", 2, "Show one status, or all pages."),
    ("reading_list", "attr:screens.review.order_box", 3, "Sort the list."),
    ("reading_list", "attr:screens.review.filters", 4,
     "Filters: years, journals, tag, and hide not relevant."),
    ("reading_list", "attr:screens.review.key", 5,
     "The key to the marks beside each page."),
    ("reading_list", "attr:screens.review.list", 6, "The pages. Press J and K to move."),
    ("reading_list", "attr:screens.review.page.translate_btn", 7,
     "Translate opens the page in Google Translate."),
    ("reading_list", "attr:screens.review.panel.record_btn", 8,
     "Record from this page opens the record form."),
    # Manage tags
    ("tags", "attr:dialog.list", 1, "The standard tags and your own."),
    ("tags", "attr:dialog.edit", 2, "Type a tag name here."),
    ("tags", "attr:dialog.add_btn", 3, "Add, rename, hide or delete."),
    # Extracted records
    ("records", "attr:screens.records.search_box", 1, "Show the records of one search."),
    ("records", "attr:screens.records.species_box", 2, "Or one species."),
    ("records", "attr:screens.records.year_box", 3, "Or one year."),
    ("records", "attr:screens.records.table", 4, "The records. Double-click one to edit it."),
    ("records", "attr:screens.records.remove_btn", 5, "Remove deletes the chosen record."),
    ("records", "attr:screens.records.export_btn", 6, "Export CSV for Observatum."),
    # The record form
    ("record_form", "attr:dialog.species_edit", 1, "The species, as UKSI names it."),
    ("record_form", "attr:dialog.check_btn", 2, "Check name looks it up in UKSI."),
    ("record_form", "attr:dialog.edits.date_printed", 3, "The date as printed, in your words."),
    ("record_form", "attr:dialog.day", 4, "The parsed date. Any part may be blank."),
    ("record_form", "attr:dialog.edits.grid_ref", 5, "A grid reference, checked as you save."),
    ("record_form", "attr:dialog.citation", 6, "The page's citation, filled in for you."),
    ("record_form", "attr:dialog.save_btn", 7, "Save the record."),
    # Exports
    ("exports", "attr:screens.export.search_box", 1, "Which search to export."),
    ("exports", "attr:screens.export.pv_table", 2, "A preview of the pages that will go in."),
    ("exports", "attr:screens.export.create_btn", 3, "Create dossier."),
    ("exports", "attr:screens.export.exports", 4, "Files you have already made."),
    # The BHL key guide
    ("api_key", "attr:dialog.open_btn", 1, "Opens the BHL page for the free key."),
    ("api_key", "attr:dialog.key_edit", 2, "Paste the key here."),
    ("api_key", "attr:dialog.test_btn", 3, "Test key asks BHL one small question."),
    ("api_key", "attr:dialog.save_btn", 4, "Save keeps the key on this computer."),
)
