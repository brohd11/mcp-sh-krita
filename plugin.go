package main

import (
	_ "embed"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"github.com/brohd11/mcp-sh"
)

// The Krita Python plug-in, written into Krita's pykrita folder by
// `mcp-sh-krita plugin install`, so the shell and the bridge it talks to always come from
// the same tag.
var (
	//go:embed plugin/mcp_sh_krita_bridge/__init__.py
	pluginSrc []byte
	//go:embed plugin/mcp_sh_krita_bridge.desktop
	pluginDesktop []byte
)

const (
	pluginName    = "mcp_sh_krita_bridge" // module folder and .desktop name; Krita needs them to match
	pluginUsage   = "plugin install|status|remove [--dir PYKRITA_DIR]"
	pluginSummary = "Install, check or remove the Krita plug-in (the bridge mcp-sh-krita talks to)"
)

func pluginCommand(version string) mcpsh.Subcommand {
	return mcpsh.Subcommand{
		Name: "plugin", Usage: pluginUsage, Summary: pluginSummary,
		Run: func(args []string, stdout, stderr io.Writer) int {
			return runPlugin(version, args, stdout, stderr)
		},
	}
}

func runPlugin(version string, args []string, stdout, stderr io.Writer) int {
	usage := func() int {
		fmt.Fprintf(stderr, "usage: mcp-sh-krita %s\n", pluginUsage)
		return 2
	}
	if len(args) == 0 {
		return usage()
	}
	sub, dir := args[0], ""
	for i := 1; i < len(args); i++ {
		switch a := args[i]; {
		case a == "--dir" && i+1 < len(args):
			dir = args[i+1]
			i++
		case strings.HasPrefix(a, "--dir="):
			dir = strings.TrimPrefix(a, "--dir=")
		default:
			fmt.Fprintf(stderr, "unexpected argument %q\n", a)
			return usage()
		}
	}
	if sub != "install" && sub != "status" && sub != "remove" {
		return usage()
	}
	if dir == "" {
		var err error
		if dir, err = findPykritaDir(); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
	}
	var err error
	switch sub {
	case "install":
		err = installPlugin(dir, version, stdout)
	case "status":
		pluginStatus(dir, version, stdout)
	case "remove":
		err = removePlugin(dir, stdout)
	}
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

// kritaDataDirs are the folders Krita keeps its resources in on this OS, in order of
// preference. Python plug-ins go in their pykrita subfolder.
func kritaDataDirs() []string {
	home, _ := os.UserHomeDir()
	switch runtime.GOOS {
	case "darwin":
		return []string{filepath.Join(home, "Library", "Application Support", "krita")}
	case "windows":
		return []string{filepath.Join(os.Getenv("APPDATA"), "krita")}
	}
	xdg := os.Getenv("XDG_DATA_HOME")
	if xdg == "" {
		xdg = filepath.Join(home, ".local", "share")
	}
	return []string{
		filepath.Join(xdg, "krita"),
		filepath.Join(home, ".var", "app", "org.kde.krita", "data", "krita"), // Flatpak
	}
}

// findPykritaDir is the pykrita folder of the first Krita data folder that exists.
func findPykritaDir() (string, error) {
	dirs := kritaDataDirs()
	for _, d := range dirs {
		if info, err := os.Stat(d); err == nil && info.IsDir() {
			return filepath.Join(d, "pykrita"), nil
		}
	}
	return "", fmt.Errorf("no Krita data folder in %s: start Krita once, or pass --dir (Settings > Manage Resources > Open Resource Folder, then its pykrita folder)", strings.Join(dirs, ", "))
}

var bridgeVersion = regexp.MustCompile(`(?m)^BRIDGE_VERSION = "([^"]*)"`)

func installPlugin(dir, version string, stdout io.Writer) error {
	dest := filepath.Join(dir, pluginName)
	if installed, ok := readBridgeVersion(dest); ok && compareVersions(installed, version) > 0 {
		return fmt.Errorf("installed plug-in %s is newer than this binary (%s); update mcp-sh-krita", installed, version)
	}
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return err
	}
	src := bridgeVersion.ReplaceAll(pluginSrc, []byte(`BRIDGE_VERSION = "`+strings.ReplaceAll(version, `"`, ``)+`"`))
	if err := os.WriteFile(filepath.Join(dest, "__init__.py"), src, 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, pluginName+".desktop"), pluginDesktop, 0o644); err != nil {
		return err
	}
	fmt.Fprintf(stdout, "Installed the mcp-sh-krita plug-in %s in %s\n", version, dest)
	fmt.Fprintln(stdout, "First install: enable \"mcp-sh-krita Bridge\" in Settings > Configure Krita > Python Plugin Manager.")
	fmt.Fprintln(stdout, "Then restart Krita: the bridge starts with it.")
	return nil
}

func pluginStatus(dir, version string, stdout io.Writer) {
	fmt.Fprintf(stdout, "pykrita   %s\n", dir)
	switch installed, ok := readBridgeVersion(filepath.Join(dir, pluginName)); {
	case !ok:
		fmt.Fprintln(stdout, "plug-in   not installed: mcp-sh-krita plugin install")
	case installed != version:
		fmt.Fprintf(stdout, "plug-in   %s, binary is %s: mcp-sh-krita plugin install, then restart Krita\n", installed, version)
	default:
		fmt.Fprintf(stdout, "plug-in   %s (matches the binary)\n", installed)
	}
}

func removePlugin(dir string, stdout io.Writer) error {
	dest := filepath.Join(dir, pluginName)
	if _, ok := readBridgeVersion(dest); !ok {
		if _, err := os.Stat(dest); errors.Is(err, os.ErrNotExist) {
			fmt.Fprintf(stdout, "No plug-in in %s\n", dest)
			return nil
		}
		return fmt.Errorf("%s is not the mcp-sh-krita plug-in; not removing it", dest)
	}
	if err := os.RemoveAll(dest); err != nil {
		return err
	}
	if err := os.Remove(filepath.Join(dir, pluginName+".desktop")); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	fmt.Fprintf(stdout, "Removed %s. Restart Krita to unload it.\n", dest)
	return nil
}

// readBridgeVersion reads the version stamped into the plug-in installed in dir.
func readBridgeVersion(dir string) (string, bool) {
	data, err := os.ReadFile(filepath.Join(dir, "__init__.py"))
	if err != nil {
		return "", false
	}
	m := bridgeVersion.FindSubmatch(data)
	if m == nil {
		return "", false
	}
	return string(m[1]), true
}

// compareVersions compares the vMAJOR.MINOR.PATCH prefix of two versions, such as
// `git describe` output. It returns 0 when either has none ("dev"), so dev builds never
// block an install.
func compareVersions(a, b string) int {
	va, okA := parseVersion(a)
	vb, okB := parseVersion(b)
	if !okA || !okB {
		return 0
	}
	for i := range va {
		if va[i] != vb[i] {
			if va[i] > vb[i] {
				return 1
			}
			return -1
		}
	}
	return 0
}

var semverPrefix = regexp.MustCompile(`^v?(\d+)\.(\d+)\.(\d+)`)

func parseVersion(v string) ([3]int, bool) {
	var out [3]int
	m := semverPrefix.FindStringSubmatch(v)
	if m == nil {
		return out, false
	}
	for i := range out {
		out[i], _ = strconv.Atoi(m[i+1])
	}
	return out, true
}
