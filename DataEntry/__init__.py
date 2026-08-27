"""DataEntry -- fast keyboard-driven observation entry for the Biological Software suite.

Widget-first architecture: `DataEntryWidget` is a self-contained QWidget that takes a
database PATH and has NO dependency on Observatum's main-window internals. Observatum
embeds it as a tab; a thin `__main__` opens it standalone (the Atrium pattern). Keeping
the widget ignorant of Observatum is the whole safety story -- the moment it reaches into
a parent, standalone mode breaks.

Step 1 (this build): SHELL ONLY. The window opens, connects to the given database, proves
the wiring with read-only proof-of-life queries, and touches nothing. The session picker
and hot loop arrive in the next increment.

Design source: docs/26_Data_Entry_Design.md + docs/26a_Data_Entry_Build_Ready_Addendum.md
"""

__version__ = "0.1.0-shell"
