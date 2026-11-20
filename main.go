// mcp-sh-krita: a sandboxed bash shell over Krita, served over MCP.
// See `mcp_sh_krita --help` and the README.
package main

import (
	"embed"

	"github.com/brohd11/mcp-sh"
)

// appFS is the built-in config layer. Directory embeds skip files starting with "_",
// so the command library is listed explicitly.
//
//go:embed config.json commands commands/_lib.py
var appFS embed.FS

// version is set at build time via -ldflags "-X main.version=...". See the Makefile.
var version = "dev"

func main() {
	mcpsh.Main(mcpsh.Config{
		Name:        "mcp_sh_krita",
		App:         "krita",
		Version:     version,
		UpdateRepo:  "brohd11/mcp-sh-krita",
		FS:          appFS,
		Subcommands: []mcpsh.Subcommand{pluginCommand(version)},
	})
}
