# summary: save a document (.kra: Save As) or export its visible image (png, jpg, webp, ...): save DOC PATH
# usage: save DOC PATH      DOC: name, file name or #N; PATH: absolute (or ~/...), format from its extension
# A .kra path saves the document there and makes it the document's file (Save As). Any
# other format exports the visible image with Krita's default options for it, and leaves
# the document's file alone (Export). No dialogs either way. Prints the path.
if len(ARGS) != 2:
    fail("usage: save DOC PATH")
doc = doc_ref(ARGS[0])
path = file_arg(ARGS[1])
ext = os.path.splitext(path)[1].lower()
if not ext:
    fail("save: %r has no extension to pick the format from" % ARGS[1])
if not os.path.isdir(os.path.dirname(path)):
    fail("save: no such folder: %s" % os.path.dirname(path))
# Batch mode on the document, not the app: only that stops the exporter's options dialog.
batch = doc.batchmode()
doc.setBatchmode(True)
try:
    doc.waitForDone()
    ok = doc.saveAs(path) if ext == ".kra" else doc.exportImage(path, InfoObject())
    doc.waitForDone()
finally:
    doc.setBatchmode(batch)
if not ok or not os.path.isfile(path):
    fail("Krita could not %s %s to %s" % ("save" if ext == ".kra" else "export", doc_label(doc), path))
print(path)
