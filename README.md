# mcp-sh-krita

Give an agent a sandboxed bash shell over the running Krita session through MCP.
The agent gets `run`, `list_commands` and `help`, and combines app commands with
pipes, loops, `jq` and `grep`. Commands run as Python through the bundled Krita
plugin. Built on [mcp-sh](https://github.com/brohd11/mcp-sh).

**Krita scripting edits cannot be undone with Ctrl+Z.** Save before editing; prefer
removable filter masks (`filter apply --mask`) when applying filters.

## Install

Requires Krita 5.2+ with Python plugin support. Start it once before installing the
bridge so its resource folder exists.

**macOS / Linux (sh)**

```sh
curl -fsSL https://raw.githubusercontent.com/brohd11/mcp-sh-krita/main/install.sh | sh
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/brohd11/mcp-sh-krita/main/install.ps1 | iex
```

Follow the installer's PATH instructions, then run in either shell:

```sh
mcp_sh_krita setup
mcp_sh_krita plugin install
```

`setup` creates `~/.mcp-sh/krita/` and prints registration commands for Claude Code
and Codex. Run the appropriate printed command for your client; `setup` does not
register the server itself.

In Krita, enable **mcp-sh-krita Bridge** under **Settings > Configure Krita >
Python Plugin Manager**, then restart Krita. The bridge starts automatically from then on.

## Quickstart

With a document open in Krita, check the connection and inspect it:

```sh
mcp_sh_krita commands
mcp_sh_krita run 'docs'
mcp_sh_krita run 'layers | head -5'
```

In your MCP client, ask the agent to list the open documents and inspect their layers.
Use `list_commands` to discover commands and `help` for usage. Commands act on the
open documents; see [Commands](doc/commands.md) for editing and filter examples.

## Documentation

- [Commands](doc/commands.md): files, layers, filters and Python.
- [Bridge](doc/bridge.md): settings, plugin updates and troubleshooting.
- [Custom commands](doc/custom-commands.md): add your own Python scripts.
- [Development](doc/development.md): builds, tests and releases.
- [Core configuration](https://github.com/brohd11/mcp-sh/blob/main/doc/configuration.md) and
  [sandbox](https://github.com/brohd11/mcp-sh/blob/main/doc/sandbox.md).
