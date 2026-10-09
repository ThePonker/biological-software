"""Standalone entry point for DataEntry (Atrium pattern).

    python -m DataEntry              # auto: newest data/observatum_dev_*.db + real uksi.db
    python -m DataEntry --db PATH    # explicit main database

Before showing the window, it points Observatum's get_database() singleton at the chosen
main DB + uksi so species search and the write path use them. Without --db it selects the
newest timestamped dev copy, never the live database.
"""
from __future__ import annotations

import argparse
import sys

from DataEntry import bootstrap


def _resolve_main_db(explicit):
    data_dir, uksi_db, live_db = bootstrap.resolve_suite_paths()
    if explicit:
        return explicit, uksi_db
    dev = bootstrap.newest_dev_db(data_dir)
    return (dev or live_db), uksi_db


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="DataEntry", description="Fast observation entry.")
    parser.add_argument("--db", default=None, help="Path to the main SQLite database.")
    args = parser.parse_args(argv)

    # Silence the benign, noisy "QFont::setPointSize: Point size <= 0" warnings that come from
    # Observatum's config/import chain (pixel-defined fonts). Everything else passes through.
    from PySide6.QtCore import qInstallMessageHandler

    def _quiet(mode, context, message):
        if "Point size <= 0" in message:
            return
        sys.stderr.write(message + "\n")

    qInstallMessageHandler(_quiet)

    main_db, uksi_db = _resolve_main_db(args.db)

    # Point Observatum's singleton at these DBs (dev copy + uksi). Non-fatal on failure --
    # the widget will show the reason and disable recording.
    _, err = bootstrap.init_databases(main_db, uksi_db)
    if err:
        print(f"[DataEntry] {err}")

    from PySide6.QtWidgets import QApplication
    from DataEntry.data_entry_widget import DataEntryWidget

    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("Flauna")
    app.setApplicationName("Observatum")  # so QSettings resolves the same USER_INITIALS

    widget = DataEntryWidget(main_db)
    widget.resize(860, 720)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
