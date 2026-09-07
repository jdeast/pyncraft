import socket
import select
import sys
from .util import flatten_parameters_to_bytestring

""" @author: Aron Nieminen, Mojang AB"""

class RequestError(Exception):
    pass

class ConnectionClosed(Exception):
    """The server closed the TCP connection.

    Deliberately not named ConnectionError: that has been a Python builtin
    since 3.3, and shadowing it here would mean any except ConnectionError
    in this module silently stops catching real socket errors.
    """
    pass

class Connection:
    """Connection to a Minecraft Pi game"""
    RequestFailed = "Fail"

    def __init__(self, address, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((address, port))
        # One file object for the life of the connection. Building a new one per
        # receive() gave each its own buffer, so when two replies arrived in the
        # same TCP segment the first reader buffered both, returned one, and was
        # then discarded along with the second.
        self.fd = self.socket.makefile("r", encoding="utf-8")
        self.lastSent = ""

    def drain(self):
        """Drains the socket of incoming data"""
        while True:
            readable, _, _ = select.select([self.socket], [], [], 0.0)
            if not readable:
                break
            data = self.socket.recv(1500)
            if len(data) == 0:
                raise ConnectionClosed("%s failed! Cause: connection closed" % self.lastSent.strip())
            e =  "Drained Data: <%s>\n"%data.strip().decode('utf-8', 'replace')
            e += "Last Message: <%s>\n"%self.lastSent.strip().decode('utf-8', 'replace')
            sys.stderr.write(e)

    def send(self, f, *data):
        """
        Sends data. Note that a trailing newline '\n' is added here

        The protocol is UTF-8. FruitJuice reads and writes the socket with an
        explicit "utf-8" InputStreamReader/OutputStreamWriter, and
        util._misc_to_bytes encodes UTF-8 on the way out. (Minecraft Pi used
        CP437; this fork does not.)
        """

        s = b"".join([f, b"(", flatten_parameters_to_bytestring(data), b")", b"\n"])
        self._send(s)

    def sendBatch(self, messages, chunk=512):
        """Send many already-built commands with as few writes as possible.

        One sendall per command is fine at human speed and hopeless at a
        hundred thousand: the per-call overhead, not the network, is what makes
        a large build slow. Joining them into a few big writes is most of the
        speed-up, and it costs nothing in protocol terms because the server
        splits on newlines anyway.

        Only for commands that send no reply. Anything that answers must go
        through sendReceive one at a time, or replies stop lining up with the
        requests that asked for them.

        `chunk` bounds how much is joined at once. Handing the socket one
        enormous buffer just moves the wait, and a bounded chunk keeps the
        server's queue from being flooded faster than a tick can drain it.
        """
        buf = []
        count = 0
        for m in messages:
            buf.append(m)
            count += 1
            if len(buf) >= chunk:
                self._send(b"".join(buf))
                buf = []
        if buf:
            self._send(b"".join(buf))
        return count

    def build(self, f, *data):
        """Build the bytes send() would transmit, without sending them."""
        return b"".join([f, b"(", flatten_parameters_to_bytestring(data), b")", b"\n"])

    def _send(self, s):
        """
        The actual socket interaction from self.send, extracted for easier mocking
        and testing
        """
        self.drain()
        self.lastSent = s
        self.socket.sendall(s)

    def receive(self):
        """Receives data. Note that the trailing newline '\n' is trimmed"""
        line = self.fd.readline()
        if line == "":
            # readline only returns empty at EOF, i.e. the server hung up. This
            # used to fall through and be returned as a perfectly ordinary answer.
            raise ConnectionClosed(
                "%s failed! Cause: connection closed" % self.lastSent.strip())
        s = line.rstrip("\n")
        checkFail = s.split(",")
        if checkFail[0] == Connection.RequestFailed:
            # clear anything still queued, or the next call reads this failure's tail
            self.drain()
            raise RequestError("%s failed! Cause: %s" % (self.lastSent.strip(),checkFail[-1]))
        return s

    def sendReceive(self, *data):
        """Sends and receive data"""
        self.send(*data)
        return self.receive()
