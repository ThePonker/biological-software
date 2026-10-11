"""One copy of Atrium at a time (L28, test 53, 10 Oct).

The first copy listens on a named local channel (a named pipe on Windows). A second
copy connects to it, asks it to show itself, and exits; the open copy brings its panel
to the front. If the channel cannot be opened at all, Atrium still starts (as before).
"""

import getpass
import sys
from typing import Callable, Optional

from PySide6.QtNetwork import QLocalServer, QLocalSocket

SHOW = b"show"
ACK = b"ok"


def channel_name(app: str = "Atrium") -> str:
    """Per-user name, so two Windows accounts on one PC don't see each other's copy."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    safe = "".join(ch for ch in user if ch.isalnum()) or "user"
    return f"BiologicalSoftware.{app}.{safe}"


def _allow_other_to_come_forward():
    """Windows only lets the foreground process hand the foreground on: this (new,
    foreground) copy allows the open one to bring its window to the front."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)    # ASFW_ANY
        except Exception:
            pass


class SingleInstance:
    def __init__(self, name: Optional[str] = None):
        self.name = name or channel_name()
        self._server: Optional[QLocalServer] = None
        self._on_show: Optional[Callable[[], None]] = None

    def signal_running_copy(self, timeout_ms: int = 500, ack_ms: int = 1500) -> bool:
        """True if another copy is open (it has been asked to come to the front).

        Waits for the open copy's "ok" before hanging up: on Windows a message on a named
        pipe can be lost if the line closes before the other side has read it (PC test,
        10 Oct). No reply in time still counts as "a copy is open" -- it answered the call.
        """
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(timeout_ms):
            return False
        _allow_other_to_come_forward()
        sock.write(SHOW)
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        got = b""
        while ACK not in got and sock.waitForReadyRead(ack_ms):
            got += bytes(sock.readAll())
        sock.disconnectFromServer()
        if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            sock.waitForDisconnected(timeout_ms)
        return True

    def listen(self, on_show: Callable[[], None]) -> bool:
        """Become the copy others find. False if the channel could not be opened."""
        self._on_show = on_show
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self.name):
            print(f"[Atrium] single-instance channel unavailable: {server.errorString()}")
            return False
        server.newConnection.connect(self._accept)
        self._server = server
        return True

    def _accept(self):
        while self._server is not None and self._server.hasPendingConnections():
            conn = self._server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read(c))
            conn.disconnected.connect(conn.deleteLater)
            if conn.bytesAvailable():
                self._read(conn)

    def _read(self, conn):
        data = bytes(conn.readAll())
        if SHOW in data:
            try:
                conn.write(ACK)          # the caller waits for this before hanging up
                conn.flush()
            except Exception:
                pass
            if self._on_show is not None:
                self._on_show()

    def close(self):
        if self._server is not None:
            self._server.close()
            self._server = None
