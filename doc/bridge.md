# Bridge

[Back to README](../README.md)

## Settings

The bridge listens on `127.0.0.1:9530` with no token by default. To change the port
or add a token, write `~/.mcp-sh/krita/bridge.json`:

```json
{"port": 9531, "token": "your-token"}
```

Set `MCP_SH_KRITA_PORT` and `MCP_SH_KRITA_TOKEN` to matching values in the
shell binary's environment, including its MCP client registration.

Apply changes with **Tools > Scripts > Restart mcp-sh-krita Bridge**.

## Plugin maintenance

```sh
mcp_sh_krita plugin status
mcp_sh_krita update
mcp_sh_krita plugin install
```

`plugin status` compares the installed plugin with the binary. After updating,
reinstall the plugin and restart Krita.
Use `plugin remove` to uninstall it.

If automatic folder detection fails, use `plugin install --dir PYKRITA_DIR`.

## Connection problems

Run `mcp_sh_krita commands` to check connectivity. If the bridge is unavailable,
check that the plugin is installed and enabled in the Python Plugin Manager,
then verify the port and token match on both sides.

## Implementation

`plugin/mcp_sh_krita_bridge/` is a Python `Extension` speaking the core
[host protocol](https://github.com/brohd11/mcp-sh/blob/main/doc/native-hosts.md).
Its `python` command executes stdin; `host.exec` routes script commands through it.

A `QTcpServer` runs on Krita's GUI thread. Requests are serialized, including those
arriving during `doc.waitForDone()`. Each run gets a fresh namespace, and errors
preserve any output already printed.

During a run, the bridge enables batch mode for existing and newly opened documents,
so exporters use default options. It restores batch mode afterwards. Any remaining
dialog is closed and named in stderr.

The plugin uses PyQt5 for Krita 5.x and falls back to PyQt6 for Krita 6. It was tested
on Krita 5.3.4. [Scripting edits have no undo](commands.md).
