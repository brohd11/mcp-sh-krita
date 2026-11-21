# Development

[Back to README](../README.md)

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
