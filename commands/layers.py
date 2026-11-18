# summary: every layer and mask of the open documents, inside groups too, as JSON lines with an id and path
# usage: layers [DOC...]      DOC: name, file name or #N; default: every open document
# One JSON object per layer or mask, top to bottom, groups before their contents:
#   {"id", "path", "doc", "name", "kind", "parent", "visible", "opacity" (0-100),
#    "blending", "locked", "alpha_locked", "x", "y", "width", "height"}
# kind: paintlayer, grouplayer, vectorlayer, filterlayer, filllayer, clonelayer, filelayer,
# transparencymask, filtermask, transformmask, selectionmask, colorizemask.
# Paths are DOC/Group/Layer. DOC is the file name, or an unsaved document's name (#N when
# that is not unique). Pipe into commands that take layers, or pick with jq first:
#   layers | jq -c 'select(.kind == "vectorlayer")' | layer set visible false
docs = [doc_ref(a) for a in ARGS] or list(app.documents())
all_docs = app.documents()
rows = [node_info(node, doc, path) for doc in docs for node, path in walk(doc, all_docs)]
for row in rows:
    emit(row)
