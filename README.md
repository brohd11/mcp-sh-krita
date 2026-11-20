# mcp-sh-krita

A sandboxed bash shell over the running Krita session, served over MCP. Built on
[mcp-sh](https://github.com/brohd11/mcp-sh): the agent gets `run`,
`list_commands` and `help`, and its commands run as Python inside Krita, through a small
plug-in that ships with mcp-sh-krita.

```sh
mcp_sh_krita run 'layers | jq -c "select(.kind == \"vectorlayer\")" | layer set visible false'
mcp_sh_krita run 'filter ls blur'
mcp_sh_krita run 'filter apply "gaussian blur" horizRadius=8 vertRadius=8 --mask art.kra/Background'
mcp_sh_krita run 'view art.kra'      # prints the path of a PNG of the document
```

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/brohd11/mcp-sh-krita/main/install.sh | sh
mcp_sh_krita setup            # ~/.mcp-sh/krita/ + prints the claude/codex mcp add commands
mcp_sh_krita plugin install   # the bridge plug-in, into Krita's pykrita folder
```

On Windows: `irm https://raw.githubusercontent.com/brohd11/mcp-sh-krita/main/install.ps1 | iex`.

Start Krita once before `plugin install`, so its resource folder exists (or pass
`--dir PYKRITA_DIR`). Then, in Krita, enable **mcp-sh-krita Bridge** in **Settings >
Configure Krita > Python Plugin Manager** and restart Krita. The bridge starts with Krita
from then on. `mcp_sh_krita commands` checks the connection, and `mcp_sh_krita plugin
status` checks whether the installed plug-in matches the binary. After an update, run
`plugin install` again, then restart Krita.

The bridge listens on `127.0.0.1:9530` with no token. To change either:
- put `{"port": 9531, "token": "..."}` in `~/.mcp-sh/krita/bridge.json` for the plug-in;
- set `MCP_SH_KRITA_PORT` / `MCP_SH_KRITA_TOKEN` for mcp-sh-krita;
- then use **Tools > Scripts > Restart mcp-sh-krita Bridge**.

## Commands

| Command | Does |
|---|---|
| `docs` | the open documents as JSON lines: label (file name; for an unsaved document its name, or `#N` when that is not unique), size, color model, file, unsaved changes |
| `open PATH...` | open files, each in a window |
| `save DOC PATH` | a `.kra` path saves the document there (Save As); other formats export the visible image and leave the document's file alone (Export). No dialogs |
| `view [DOC] [--max N]` | save a PNG of what the document looks like and print its path, so the agent can look at it |
| `layers [DOC...]` | every layer and mask of the open documents, **inside groups too**: `id` (Krita's unique id), `path` (`DOC/Group/Layer`), `kind` (`paintlayer`, `vectorlayer`, `grouplayer`, `filtermask`, ...), visibility, opacity, blending, locks, bounds |
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

## The bridge

`plugin/mcp_sh_krita_bridge/` is a Krita Python plug-in (an `Extension`) speaking mcp-sh's
host protocol.
- It offers one host command, `python`, which runs the code it gets on stdin. mcp-sh-krita's script commands run through it (`host.exec` in `config.json`).
- The server is a `QTcpServer` on Krita's GUI thread, where the scripting API may be called, so there are no threads. Requests run one at a time, and a request that arrives while code waits on Krita (`doc.waitForDone()`) waits its turn.
- Each run gets a fresh namespace. A failure keeps what was printed before it.
- No run can open a dialog that nobody is there to answer. During a run, the bridge turns on batch mode for every document and for the app (exporters then use their default options), and wraps `createDocument`/`openDocument` so new documents get it too. Afterwards it puts each document's batch mode back, so Krita's own menus behave as usual. Any dialog that still opens is closed, and the run's stderr names it.

It imports PyQt5 (Krita 5.x) and falls back to PyQt6 (Krita 6). It was tested on Krita
5.3.4.

## Your own commands

Keep your own Python commands in a folder of their own and add it:

```sh
mcp_sh_krita commands add ~/code/krita-tools
```

A `_lib.py` in that folder is appended to the built-in one, so your commands can use and
replace its helpers (`targets`, `resolve`, `node_info`, `doc_ref`, `convert_like`,
`refresh`, ...). Check before changing anything and print last, as the built-in commands
do. See the mcp-sh README for the script format and folder order.

## Development

```sh
make           # host build -> build/<os>-<arch>/mcp_sh_krita
make test
make package   # release archives for every platform
```

After editing the plug-in, run `mcp_sh_krita plugin install` from a fresh build and
restart Krita.

The makefile body, installers, workflows and `cliff.toml` are rendered from
[sh-templates](https://github.com/brohd11/sh-templates) by the workspace's `render-go.sh`.
Only the config blocks above `# ---- end config ----` are edited here. Pushing a `v*` tag
releases.
