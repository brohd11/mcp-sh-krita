# Shared helpers for mcp-sh-krita's script commands, defined before every Python command.
# A user commands/_lib.py is appended after this one and can add or replace helpers.
#
# Commands run on Krita's GUI thread, one at a time, each in a fresh namespace. They check
# everything first, then change things, then print, so a failure never leaves half an
# edit behind.
import difflib
import json
import os

from krita import InfoObject, Krita

try:
    from PyQt5.QtCore import QUuid
except ImportError:  # Krita 6
    from PyQt6.QtCore import QUuid

app = Krita.instance()


class Fail(Exception):
    """An error shown to the agent as its plain message."""


def fail(msg):
    raise Fail(msg)


def emit(obj):
    print(json.dumps(obj))


# ---- documents --------------------------------------------------------------------------


def doc_label(doc, docs=None):
    """A saved document's file name; an unsaved one's name when that is unique and fits in a
    path; else #N (its place among the open documents)."""
    path = doc.fileName()
    if path:
        return os.path.basename(path)
    docs = app.documents() if docs is None else docs
    name = doc.name()
    if name and "/" not in name and not name.startswith("#") and [named(d) for d in docs].count(name) == 1:
        return name
    return "#%d" % docs.index(doc)


def named(doc):
    """What a document can be called by: its file name, or else its name."""
    return os.path.basename(doc.fileName()) if doc.fileName() else doc.name()


def open_docs(docs=None):
    docs = app.documents() if docs is None else docs
    labels = []
    for i, d in enumerate(docs):
        label = doc_label(d, docs)
        labels.append(label if label.startswith("#") else "#%d %s" % (i, label))
    return ", ".join(labels) or "none"


def doc_ref(ref):
    """The open document named by #N, N, its label, file name or Krita name."""
    ref = ref.strip()
    docs = app.documents()
    digits = ref[1:] if ref.startswith("#") else ref
    if digits.isdigit():
        if int(digits) >= len(docs):
            fail("no open document #%s (open: %s)" % (digits, open_docs(docs)))
        return docs[int(digits)]
    found = [d for d in docs if doc_label(d, docs) == ref] or [d for d in docs if ref in (named(d), d.name())]
    if not found:
        fail("no open document named %r (open: %s)" % (ref, open_docs(docs)))
    if len(found) > 1:
        fail("%d open documents are named %r: use #N (open: %s)" % (len(found), ref, open_docs(docs)))
    return found[0]


def only_doc(args):
    """The document named by args[0], else the only open one."""
    if args:
        return doc_ref(args[0])
    docs = app.documents()
    if len(docs) != 1:
        fail("%s: name one (open: %s)" % ("no document is open" if not docs else "%d documents are open" % len(docs), open_docs(docs)))
    return docs[0]


def doc_info(doc, docs=None):
    docs = app.documents() if docs is None else docs
    return {
        "doc": doc_label(doc, docs),
        "index": docs.index(doc),
        "name": doc.name(),
        "file": doc.fileName() or None,
        "width": doc.width(), "height": doc.height(),
        "color": "%s/%s" % (doc.colorModel(), doc.colorDepth()),
        "resolution": doc.resolution(),
        "modified": doc.modified(),
        "active": doc == app.activeDocument(),
        "layers": sum(1 for _ in walk(doc, docs)),
    }


def file_arg(text, what="path"):
    path = os.path.expanduser(text)
    if not os.path.isabs(path):
        fail("%s: use an absolute path (or ~/...), not %r" % (what, text))
    return path


# ---- layers -----------------------------------------------------------------------------


def node_id(node):
    return node.uniqueId().toString().strip("{}")


def children(node):
    """node's children, top to bottom (Krita lists them bottom to top)."""
    return list(reversed(node.childNodes()))


def walk(doc, docs=None):
    """Every layer and mask of doc, top to bottom, entering groups, as (node, path)."""
    def rec(parent, prefix):
        for node in children(parent):
            path = prefix + "/" + node.name()
            yield node, path
            yield from rec(node, path)
    yield from rec(doc.rootNode(), doc_label(doc, docs))


def doc_of(node):
    """The open document holding node."""
    uid = node.uniqueId()
    for doc in app.documents():
        if doc.nodeByUniqueID(uid) is not None:
            return doc
    fail("layer %s is not in an open document" % node_id(node))


def node_path(node, doc=None):
    doc = doc or doc_of(node)
    names = []
    cur = node
    while cur is not None and cur.parentNode() is not None:  # the root has no parent
        names.append(cur.name())
        cur = cur.parentNode()
    return doc_label(doc) + "/" + "/".join(reversed(names))


def node_info(node, doc, path=None):
    b = node.bounds()
    parent = node.parentNode()
    return {
        "id": node_id(node),
        "path": path or node_path(node, doc),
        "doc": doc_label(doc),
        "name": node.name(),
        "kind": node.type(),
        "parent": node_id(parent) if parent is not None and parent.parentNode() is not None else None,
        "visible": node.visible(),
        "opacity": round(node.opacity() * 100 / 255, 1),
        "blending": node.blendingMode(),
        "locked": node.locked(),
        "alpha_locked": node.alphaLocked(),
        "x": b.x(), "y": b.y(), "width": b.width(), "height": b.height(),
    }


def resolve(ref):
    """(node, doc) for an id or a DOC/Group/Layer path."""
    ref = str(ref).strip()
    if "/" not in ref:
        uid = QUuid(ref if ref.startswith("{") else "{%s}" % ref)
        if uid.isNull():
            fail("not a layer id or DOC/LAYER path: %r" % ref)
        for doc in app.documents():
            node = doc.nodeByUniqueID(uid)
            if node is not None:
                return node, doc
        fail("no layer with id %s" % ref)
    head, rest = ref.split("/", 1)
    doc = doc_ref(head)
    cur = doc.rootNode()
    for name in rest.split("/"):
        found = [c for c in children(cur) if c.name() == name]
        if not found:
            where = doc_label(doc) if cur.parentNode() is None else node_path(cur, doc)
            fail("not found: %s (no %r in %s)" % (ref, name, where))
        if len(found) > 1:
            fail("%d layers are named %r in %s: use the id" % (len(found), name, ref))
        cur = found[0]
    return cur, doc


def refs(first=0, field="id"):
    """Refs from ARGS[first:], or else one per STDIN line: plain refs, or JSON objects
    with `field` (or "path")."""
    out = list(ARGS[first:])
    if out:
        return out
    for line in STDIN.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                fail("stdin: not a JSON object: " + line)
            ref = obj.get(field, obj.get("path"))
            if ref is None:
                fail("stdin: JSON line has no %s or path field: %s" % (field, line))
            line = str(ref)
        out.append(line)
    return out


def targets(first=0, allow_empty=False):
    """(node, doc) pairs named by ARGS[first:] or STDIN."""
    out, seen = [], set()
    for ref in refs(first):
        node, doc = resolve(ref)
        if node_id(node) not in seen:
            seen.add(node_id(node))
            out.append((node, doc))
    if not out and not allow_empty:
        fail("no targets: pass ids or paths as arguments, or one per stdin line (e.g. from layers)")
    return out


def refresh(docs):
    """Wait for Krita's background work, then redraw."""
    done = []
    for doc in docs:
        if doc not in done:
            doc.waitForDone()
            doc.refreshProjection()
            done.append(doc)


# ---- values -----------------------------------------------------------------------------


def split_kv(tokens):
    """KEY=VALUE tokens as a dict (in order), and the other tokens."""
    kv, rest = {}, []
    for t in tokens:
        if "=" in t and not t.startswith("=") and "/" not in t.split("=", 1)[0]:
            k, v = t.split("=", 1)
            kv[k] = v
        else:
            rest.append(t)
    return kv, rest


def did_you_mean(text, options):
    close = difflib.get_close_matches(text, options, n=1)
    return " (did you mean %s?)" % close[0] if close else ""


_TRUE = ("true", "1", "yes", "on")
_FALSE = ("false", "0", "no", "off")


def parse_bool(text, what):
    t = text.strip().lower()
    if t in _TRUE:
        return True
    if t in _FALSE:
        return False
    fail("%s: %r is not a boolean (true/false)" % (what, text))


def parse_number(text, what, lo=None, hi=None, integer=False):
    try:
        v = int(text) if integer else float(text)
    except ValueError:
        fail("%s: %r is not %s" % (what, text, "an integer" if integer else "a number"))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        fail("%s: %s is out of range (%s to %s)" % (what, text, lo, hi))
    return v


def value_type(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    return type(v).__name__


def convert_like(default, text, what):
    """text as a value of default's type, or a Fail."""
    kind = value_type(default)
    if kind == "bool":
        return parse_bool(text, what)
    if kind in ("int", "number"):
        return parse_number(text, what, integer=kind == "int")
    if kind == "string":
        return text
    fail("%s: values of type %s are not supported here; use python" % (what, kind))


def to_json(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [to_json(x) for x in v]
    return str(v)
