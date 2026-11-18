# summary: find and apply any Krita filter, baked in or as a filter mask: filter ls|info|apply
# usage: filter ls [PATTERN]          filter ids, one per line, matching PATTERN
#        filter info FILTER           one JSON line per parameter: name, type, default
#        filter apply FILTER [KEY=VALUE...] [--mask] [LAYER...]
# LAYERs are ids or DOC/Group/Layer paths, from arguments or stdin (e.g. from layers).
# apply checks every KEY=VALUE against the filter's parameters (names and types, from the
# defaults) before any layer changes, then bakes the filter into each paint layer's pixels,
# or with --mask adds it as an editable filter mask on each layer.
#   filter ls blur
#   filter info "gaussian blur"
#   layers | jq -c 'select(.name == "Sky")' | filter apply "gaussian blur" horizRadius=8 vertRadius=8
def check_filter(name):
    names = list(app.filters())
    if name not in names:
        fail("unknown filter %r%s (list them with: filter ls)" % (name, did_you_mean(name, names)))
    return app.filter(name)


def cmd_ls():
    pattern = " ".join(ARGS[1:]).lower()
    for name in sorted(app.filters()):
        if pattern in name.lower():
            print(name)


def cmd_info():
    if len(ARGS) != 2:
        fail("usage: filter info FILTER")
    f = check_filter(ARGS[1])
    for key, default in sorted(f.configuration().properties().items()):
        emit({"param": key, "type": value_type(default), "default": to_json(default)})


def cmd_apply():
    if len(ARGS) < 2:
        fail("usage: filter apply FILTER [KEY=VALUE...] [--mask] [LAYER...]")
    f = check_filter(ARGS[1])
    rest = [a for a in ARGS[2:] if a != "--mask"]
    mask = len(rest) != len(ARGS) - 2
    kv, layer_args = split_kv(rest)
    nodes = [resolve(r) for r in layer_args] if layer_args else targets(len(ARGS))
    for node, doc in nodes:
        if mask and node.type().endswith("mask"):
            fail("%s is a %s: filter masks go on layers" % (node_path(node, doc), node.type()))
        if not mask and node.type() != "paintlayer":
            fail("%s is a %s: filters bake into paint layers only (use --mask for others)" % (node_path(node, doc), node.type()))
    config = f.configuration()
    params = config.properties()
    for key, text in kv.items():
        if key not in params:
            fail("%s has no parameter %r%s (see: filter info %s)" % (f.name(), key, did_you_mean(key, list(params)), json.dumps(f.name())))
        config.setProperty(key, convert_like(params[key], text, key))
    f.setConfiguration(config)

    out = []
    for node, doc in nodes:
        if mask:
            m = doc.createFilterMask(f.name(), f, node)
            if m is None or not node.addChildNode(m, None):
                fail("Krita could not add a filter mask to %s" % node_path(node, doc))
            out.append({"id": node_id(m), "path": node_path(m, doc)})
        else:
            b = node.bounds()
            if not b.isEmpty():
                f.apply(node, b.x(), b.y(), b.width(), b.height())  # returns None in Krita 5.3
            out.append({"id": node_id(node), "path": node_path(node, doc)})
    refresh([doc for _, doc in nodes])
    for row in out:
        emit(row)


COMMANDS = {"ls": cmd_ls, "info": cmd_info, "apply": cmd_apply}
if not ARGS or ARGS[0] not in COMMANDS:
    fail("usage: filter ls|info|apply ... (see: help filter)")
COMMANDS[ARGS[0]]()
