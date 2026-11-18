# summary: open files in Krita, each in a window: open PATH...
# usage: open PATH...      absolute paths (or ~/...); prints each document as JSON (see docs)
paths = [file_arg(a) for a in ARGS]
if not paths:
    fail("usage: open PATH...")
for p in paths:
    if not os.path.isfile(p):
        fail("no such file: %s" % p)
opened = []
for p in paths:
    doc = app.openDocument(p)
    if doc is None:
        fail("Krita could not open %s" % p)
    window = app.activeWindow()
    if window is not None:
        window.addView(doc)
    opened.append(doc)
docs = app.documents()
for doc in opened:
    emit(doc_info(doc, docs))
