# Commands

[Back to README](../README.md)

Run `mcp_sh_krita commands` to list commands. From the agent shell, use
`help -s TERM` to search and `<command> --help` for usage.

| Command | Does |
|---|---|
| `docs` | the open documents as JSON lines: label (file name; for an unsaved document its name, or `#N` when that is not unique), size, color model, file, unsaved changes |
| `open PATH...` | open files, each in a window |
| `save DOC PATH` | a `.kra` path saves the document there (Save As); other formats export the visible image and leave the document's file alone (Export). No dialogs |
| `view [DOC] [--max N]` | write a PNG preview and print its path |
| `layers [DOC...]` | every layer and mask of the open documents, including groups: `id` (Krita's unique id), `path` (`DOC/Group/Layer`), `kind` (`paintlayer`, `vectorlayer`, `grouplayer`, `filtermask`, ...), visibility, opacity, blending, locks, bounds |
| `layer set PROP VALUE [LAYER...]` | set `name`, `visible`, `opacity`, `blending`, `position`, `color_label`, a lock, `inherit_alpha` or `collapsed` on many layers at once |
| `filter ls [PATTERN]`, `filter info FILTER` | find any of Krita's filters, and see a filter's parameters with their types and defaults |
| `filter apply FILTER [KEY=VALUE...] [--mask] [LAYER...]` | bake a filter into paint layers or, with `--mask`, add it as an editable filter mask on any layer |
| `python [ARGS...] < CODE` | run one-off Python inside Krita (`from krita import *` done; `app` is `Krita.instance()`) |

Commands that take layers read ids or paths from arguments, or one per stdin line (JSON
lines with an `id` or `path` work too), and print the layers they changed, so they chain:

```sh
layers | jq -c 'select(.kind == "vectorlayer")' | layer set opacity 50 | layer set color_label 3
layers art.kra | jq -c 'select(.name == "Sky")' | filter apply desaturate --mask
```

Values are checked before anything changes. That covers unknown parameters, wrong value
types, out-of-range numbers and unknown blending modes, which Krita would otherwise accept
and draw as normal. Each failure lists the valid options.

**Krita's scripting API records no undo steps**, so these edits cannot be undone with
Ctrl+Z. Prefer `filter apply --mask` (delete the mask to undo it), and save before baking
filters into pixels.
