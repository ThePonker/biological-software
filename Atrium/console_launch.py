"""Run a suite console tool in its own titled console window (ATR-1).

    python -m Atrium.console_launch MODULE "WINDOW TITLE" [ARGS...]

Atrium starts Lector this way (with CREATE_NEW_CONSOLE): the title lets Atrium
find the window again and bring it forward instead of opening a second copy.
The window waits for Enter before closing, so the last message can be read.
"""
import runpy
import sys
import traceback


def set_console_title(title: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:  # noqa: BLE001 -- a missing title is not fatal
            pass


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 3:
        print("usage: python -m Atrium.console_launch MODULE TITLE [ARGS...]")
        return 2
    module, title, args = argv[1], argv[2], argv[3:]
    set_console_title(title)
    sys.argv = [module, *args]
    code = 0
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        if isinstance(e.code, int):
            code = e.code
        elif e.code is not None:        # a message: show it
            print(e.code)
            code = 1
    except KeyboardInterrupt:
        pass
    except Exception:  # noqa: BLE001 -- show it in the window, then wait
        traceback.print_exc()
        code = 1
    try:
        input("\nPress Enter to close this window.")
    except (EOFError, KeyboardInterrupt):
        pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
