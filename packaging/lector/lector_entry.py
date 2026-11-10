"""Start-up script for the free-standing Lector (PyInstaller). Same as `python -m Lector gui`."""
import multiprocessing
import os
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    for name in ("stdout", "stderr"):                  # a windowed build has no console
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    from Lector.__main__ import main
    main(["gui"])
