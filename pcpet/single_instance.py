"""Make sure only one copy runs; later launches pass their request to it."""

from __future__ import annotations

import getpass
import hashlib
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # getuser can fail in odd environments
        user = "user"
    return "pcpet-" + hashlib.sha1(user.encode("utf-8")).hexdigest()[:12]


class SingleInstance(QObject):
    message_received = Signal(str)

    def __init__(self, lock_dir: Path):
        super().__init__()
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.name = _server_name()
        self.lock = QLockFile(str(lock_dir / "pcpet.lock"))
        self.lock.setStaleLockTime(0)  # only a dead process makes the lock stale
        self.server: QLocalServer | None = None

    def acquire(self) -> bool:
        """True if we are the first instance."""
        if not self.lock.tryLock(200):
            return False
        QLocalServer.removeServer(self.name)  # clean up after a crash
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._on_connection)
        self.server.listen(self.name)
        return True

    def send(self, message: str, timeout_ms: int = 1500) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write((message + "\n").encode("utf-8"))
        ok = sock.waitForBytesWritten(timeout_ms)
        sock.disconnectFromServer()
        if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            sock.waitForDisconnected(timeout_ms)
        return ok

    def _on_connection(self):
        while self.server is not None and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            buffer = bytearray()

            def on_ready(sock=sock, buffer=buffer):
                buffer.extend(bytes(sock.readAll()))
                while b"\n" in buffer:
                    line, _, rest = bytes(buffer).partition(b"\n")
                    buffer[:] = rest
                    self.message_received.emit(line.decode("utf-8", "replace"))

            sock.readyRead.connect(on_ready)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                on_ready()

    def release(self):
        if self.server is not None:
            self.server.close()
            self.server = None
        if self.lock.isLocked():
            self.lock.unlock()
