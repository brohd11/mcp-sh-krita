# mcp-sh-krita bridge: lets mcp-sh-krita run Python inside Krita.
#
# It speaks mcp-sh's host protocol (v1): a loopback TCP server that reads one JSON
# request line and writes one JSON response line per connection.
#
#   -> {"id":1,"method":"hello","token":"..."}
#   <- {"id":1,"name":"krita","version":"5.3.4","commands":[{"name":"python",...}]}
#   -> {"id":2,"method":"invoke","token":"...","cmd":"python","args":[],"stdin":"<code>"}
#   <- {"id":2,"stdout":"...","stderr":"...","exit_code":0}
#
# The server is a QTcpServer on Krita's GUI thread, where the scripting API may be called,
# so there are no threads: code runs as the request arrives, one request at a time. Each
# run gets a fresh namespace and keeps what it printed when it fails.
#
# Port and token come from MCP_SH_KRITA_PORT / MCP_SH_KRITA_TOKEN, else from
# ~/.mcp-sh/krita/bridge.json ({"port": 9530, "token": "..."}); the default is port
# 9530 with no token. It starts with Krita once enabled in Settings > Configure Krita >
# Python Plugin Manager; Tools > Scripts > Restart mcp-sh-krita Bridge restarts it.
import hmac
import io
import json
import os
import sys
import traceback

from krita import Extension, Krita

try:
    from PyQt5.QtCore import QEvent, QObject, QTimer
    from PyQt5.QtNetwork import QHostAddress, QTcpServer
    from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
    SHOW_EVENT = QEvent.Show
except ImportError:  # Krita 6
    from PyQt6.QtCore import QEvent, QObject, QTimer
    from PyQt6.QtNetwork import QHostAddress, QTcpServer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
    SHOW_EVENT = QEvent.Type.Show

BRIDGE_VERSION = "dev"  # stamped by `mcp_sh_krita plugin install`
DEFAULT_PORT = 9530
MAX_REQUEST = 64 << 20

PYTHON_HELP = """usage: python [ARGS...] < CODE
Run Python inside Krita, with ARGS as a list of strings. `from krita import *` is done,
and app is Krita.instance(). What the code prints is the output; an exception exits 1
with its message, after whatever was printed before it.
  python <<'EOF'
  for doc in app.documents():
      print(doc.name(), doc.width(), doc.height())
  EOF"""


def log(msg):
    # Never sys.stdout: while code runs, that is the command's output.
    if sys.__stderr__ is not None:
        print("[mcp-sh-krita] " + msg, file=sys.__stderr__, flush=True)


def load_settings():
    port, token = DEFAULT_PORT, ""
    base = os.environ.get("MCP_SH_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".mcp-sh")
    path = os.path.join(base, "krita", "bridge.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        port = int(data.get("port", port))
        token = str(data.get("token", token))
    except FileNotFoundError:
        pass
    except (ValueError, OSError) as e:
        log("ignoring %s: %s" % (path, e))
    if os.environ.get("MCP_SH_KRITA_PORT", "").isdigit():
        port = int(os.environ["MCP_SH_KRITA_PORT"])
    token = os.environ.get("MCP_SH_KRITA_TOKEN", token)
    return port, token


def error_text(exc):
    """An exception as the agent should see it: a Fail (mcp-sh-krita's lib) as its message,
    anything else as its type and message, with the innermost line of the command."""
    if type(exc).__name__ == "Fail":
        return str(exc)
    text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<command>"]
    if frames:
        f = frames[-1]
        where = "line %d" % f.lineno if f.name == "<module>" else "line %d, in %s" % (f.lineno, f.name)
        text += " (%s)" % where
    return text


class DialogGuard(QObject):
    """Closes any dialog that opens while code runs. Nobody is there to answer it, and a
    modal dialog would hold Krita's GUI thread, and so the bridge, until someone did."""

    def __init__(self):
        super().__init__()
        self.closed = []

    def eventFilter(self, obj, event):
        if event.type() == SHOW_EVENT and isinstance(obj, QDialog):
            self.closed.append(obj.windowTitle() or type(obj).__name__)
            QTimer.singleShot(0, obj.reject)
        return False


def batched(make, made):
    """make (a Krita method returning a Document), with batch mode set on what it returns,
    which is added to made."""
    def wrapper(self, *args):
        doc = make(self, *args)
        if doc is not None:
            doc.setBatchmode(True)
            made.append(doc)
        return doc
    return wrapper


def execute(code, args):
    """Run code; its output, error output and exit code."""
    out, err = io.StringIO(), io.StringIO()
    namespace = {"__name__": "__mcp_sh_krita__", "ARGS": list(args)}
    exit_code = 0
    # Batch mode keeps exporters and savers from asking for options. It is per document and
    # new documents do not inherit the app's, so set it on each open one, and wrap the calls
    # that make documents so theirs is set too.
    app = Krita.instance()
    batch = app.batchmode(), [(d, d.batchmode()) for d in app.documents()]
    app.setBatchmode(True)
    for d, _ in batch[1]:
        d.setBatchmode(True)
    makers = {name: getattr(Krita, name) for name in ("createDocument", "openDocument")}
    made = []
    for name, fn in makers.items():
        setattr(Krita, name, batched(fn, made))
    guard = DialogGuard()
    QApplication.instance().installEventFilter(guard)
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        exec("from krita import *\napp = Krita.instance()", namespace)
        exec(compile(code, "<command>", "exec"), namespace)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if e.code is not None and not isinstance(e.code, int):
            err.write(str(e.code) + "\n")
    except BaseException as e:  # noqa: BLE001 - every failure goes back to the caller
        exit_code = 1
        err.write(error_text(e) + "\n")
    finally:
        sys.stdout, sys.stderr = saved
        QApplication.instance().removeEventFilter(guard)
        for name, fn in makers.items():
            setattr(Krita, name, fn)
        app.setBatchmode(batch[0])
        # Afterwards documents ask again, so saving from Krita's menus shows the usual dialogs.
        for d, was in batch[1] + [(d, False) for d in made]:
            try:
                d.setBatchmode(was)
            except RuntimeError:  # closed by the code
                pass
    for title in guard.closed:
        err.write("closed a dialog the code opened (%s): nobody can answer it here. For exports, "
                  "call doc.setBatchmode(True) first, or use the save command.\n" % title)
    return {"stdout": out.getvalue(), "stderr": err.getvalue(), "exit_code": exit_code}


class Bridge:
    def __init__(self, port, token):
        self.port, self.token = port, token
        self.server = QTcpServer()
        self.server.newConnection.connect(self.accept)
        self.buffers = {}  # socket -> bytes read so far
        self.queue = []    # (socket, request line) waiting to run
        self.busy = False

    def listen(self):
        if not self.server.listen(QHostAddress("127.0.0.1"), self.port):
            raise OSError(self.server.errorString())

    def close(self):
        self.server.close()

    def accept(self):
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            self.buffers[conn] = b""
            conn.readyRead.connect(lambda c=conn: self.read(c))
            conn.disconnected.connect(lambda c=conn: self.drop(c))

    def drop(self, conn):
        self.buffers.pop(conn, None)
        conn.deleteLater()

    def read(self, conn):
        if conn not in self.buffers:
            return
        buf = self.buffers[conn] + bytes(conn.readAll())
        if b"\n" not in buf:
            if len(buf) > MAX_REQUEST:
                del self.buffers[conn]
                self.reply(conn, {"error": "bridge: request too large"})
            else:
                self.buffers[conn] = buf
            return
        del self.buffers[conn]
        self.queue.append((conn, buf.split(b"\n", 1)[0].decode("utf-8", "replace")))
        self.drain()

    def drain(self):
        # Code that spins the event loop (doc.waitForDone(), dialogs) can deliver the next
        # request while one is still running: it waits its turn instead of nesting.
        if self.busy:
            return
        self.busy = True
        try:
            while self.queue:
                conn, line = self.queue.pop(0)
                try:
                    resp = self.handle(line)
                except Exception as e:  # noqa: BLE001
                    resp = {"error": "bridge: %s" % e}
                self.reply(conn, resp)
        finally:
            self.busy = False

    def reply(self, conn, resp):
        conn.write(json.dumps(resp).encode("utf-8") + b"\n")
        conn.disconnectFromHost()  # after the pending bytes are written

    def handle(self, line):
        try:
            req = json.loads(line)
        except ValueError as e:
            return {"error": "bad request: %s" % e}
        rid = req.get("id", 0)
        if self.token and not hmac.compare_digest(str(req.get("token", "")), self.token):
            return {"id": rid, "error": "Unauthorized"}
        method = req.get("method")
        if method == "hello":
            return {"id": rid, "name": "krita", "version": "%s, bridge %s" % (Krita.instance().version(), BRIDGE_VERSION), "commands": [
                {"name": "python", "summary": "run Python inside Krita: python [ARGS...] < CODE", "help": PYTHON_HELP},
            ]}
        if method == "help":
            if req.get("cmd") == "python":
                return {"id": rid, "stdout": PYTHON_HELP}
            return {"id": rid, "error": "unknown command %s" % req.get("cmd")}
        if method == "invoke":
            if req.get("cmd") != "python":
                return {"id": rid, "error": "unknown command %s" % req.get("cmd")}
            res = execute(req.get("stdin") or "", req.get("args") or [])
            res["id"] = rid
            return res
        return {"id": rid, "error": "unknown method %s" % method}


class McpShKritaBridge(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.bridge = None

    def setup(self):
        try:
            self.start()
        except OSError as e:
            log("not listening: %s" % e)

    def createActions(self, window):
        action = window.createAction("mcp_sh_krita_bridge_restart", "Restart mcp-sh-krita Bridge", "tools/scripts")
        action.triggered.connect(self.restart)

    def start(self):
        if self.bridge:
            self.bridge.close()
            self.bridge = None
        port, token = load_settings()
        bridge = Bridge(port, token)
        try:
            bridge.listen()
        except OSError as e:
            raise OSError("port %d is in use (another Krita?): %s" % (port, e)) from None
        self.bridge = bridge
        log("listening on 127.0.0.1:%d%s" % (port, " (token required)" if token else ""))
        return port

    def restart(self):
        try:
            port = self.start()
        except OSError as e:
            QMessageBox.warning(None, "mcp-sh-krita", "The bridge is not listening: %s" % e)
            return
        QMessageBox.information(None, "mcp-sh-krita", "The bridge is listening on 127.0.0.1:%d" % port)


Krita.instance().addExtension(McpShKritaBridge(Krita.instance()))
