# summary: the open documents as JSON lines: label, size, color, file, unsaved changes
# usage: docs
#   {"doc" (file name; unsaved: its name, or #N when not unique), "index", "name", "file", "width", "height",
#    "color" (model/depth, e.g. RGBA/U8), "resolution", "modified", "active", "layers"}
# "doc" is what other commands take as DOC; #N (the index) works for any document.
docs = app.documents()
for row in [doc_info(d, docs) for d in docs]:
    emit(row)
