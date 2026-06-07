#!/bin/sh
# devbench Docker entrypoint
#
# Routes commands so that:
#   docker run devbench cf --help        → devbench cf --help
#   docker run devbench                  → devbench --help
#   docker run devbench python3 -c ...   → python3 -c ...  (passthrough)
#
# The rule: if the first argument matches a devbench subcommand (cf, detect,
# json, base64, etc.) or starts with --, route through `devbench`.
# Otherwise pass through as a regular command.

set -e

# Known devbench subcommands (from `devbench --list`).
DEVBENCH_COMMANDS="
  detect json base64 jwt hash url timestamp uuid diff cf
  list batch license
"

_first_arg_is_devbench() {
  case "$1" in
    --*)              return 0 ;;  # --help, --list, --version
    detect|json|base64|jwt|hash|url|timestamp|uuid|diff|cf|list|batch|license)
                      return 0 ;;
    *)                return 1 ;;
  esac
}

if [ $# -eq 0 ]; then
  # No args → show help.
  exec devbench --help
elif _first_arg_is_devbench "$1"; then
  # Looks like a devbench command → pass through.
  exec devbench "$@"
else
  # Pass through as-is (e.g. python3, sh, bash, cat).
  exec "$@"
fi