# summary: save a PNG of what a document looks like and print its path: view [DOC] [--max N]
# usage: view [DOC] [--max N]     DOC: name, file name or #N (default: the only open document)
# The visible composite, scaled to fit N pixels (default 1024), saved under
# ~/.mcp-sh/krita/images/ (the newest 50 are kept). Open the path to look at it.
import time

try:
    from PyQt5.QtCore import Qt
except ImportError:
    from PyQt6.QtCore import Qt

args = list(ARGS)
size = 1024
if "--max" in args:
    i = args.index("--max")
    if i + 1 >= len(args) or not args[i + 1].isdigit() or int(args[i + 1]) < 1:
        fail("--max needs a size in pixels")
    size = int(args[i + 1])
    del args[i:i + 2]
if len(args) > 1:
    fail("usage: view [DOC] [--max N]")
doc = only_doc(args)

folder = os.path.join(os.path.expanduser("~"), ".mcp-sh", "krita", "images")
os.makedirs(folder, exist_ok=True)
stem = os.path.splitext(doc_label(doc))[0].lstrip("#") or "doc"
path = os.path.join(folder, "view-%s-%s.png" % (stem, time.strftime("%Y%m%d-%H%M%S")))
doc.waitForDone()
doc.refreshProjection()
img = doc.projection(0, 0, doc.width(), doc.height())
if img.isNull():
    fail("Krita returned no image for %s" % doc_label(doc))
if max(img.width(), img.height()) > size:
    img = img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
if not img.save(path, "PNG"):
    fail("could not write %s" % path)

files = sorted((os.path.join(folder, n) for n in os.listdir(folder)), key=os.path.getmtime, reverse=True)
for old in files[50:]:
    os.remove(old)
print(path)
