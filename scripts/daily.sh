#!/bin/bash
# Daily unattended refresh: pull prices, rebuild, publish, commit.
#
# Run by launchd (see scripts/com.riftbound.refresh.plist). launchd starts jobs
# with a bare environment, so PATH and the tool locations are set explicitly
# rather than inherited.
#
# Every step logs to logs/refresh-YYYY-MM-DD.log. The data refresh and the
# publish are separate concerns: if publishing fails the prices are still
# refreshed, committed and pushed, and the log says what went wrong.
set -u
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/refresh-$(date +%Y-%m-%d).log"
exec >>"$LOG" 2>&1

ARTIFACT_URL="https://claude.ai/code/artifact/c3f6a626-20d0-4fb0-b622-92f59dc125ad"
VENV_PY="$ROOT/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="python3"

echo
echo "================ $(date '+%Y-%m-%d %H:%M:%S %Z') ================"

# ---- 1. the data -----------------------------------------------------------
echo "--- refresh ---"
if ! RIFTBOUND_PYTHON="$VENV_PY" bash scripts/refresh.sh; then
  echo "REFRESH FAILED - board left untouched (every merge validates before writing)"
  exit 1
fi

# ---- 2. sanity -------------------------------------------------------------
# refresh.sh already ran this, but capture it here so the log has the summary
# and so a suspicious result can stop the publish.
echo "--- what moved ---"
MOVED="$("$VENV_PY" scripts/whatmoved.py 2>&1)"
echo "$MOVED"
if echo "$MOVED" | grep -q "WARNING: not one ask changed"; then
  echo "STOPPING: the pull did not reach TCGplayer. Nothing committed, nothing published."
  exit 1
fi
if echo "$MOVED" | grep -q "WARNING: almost every ask changed"; then
  echo "STOPPING: implausible number of changes - needs a human look."
  exit 1
fi

# ---- 3. commit -------------------------------------------------------------
echo "--- commit ---"
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "Refresh prices, $(date '+%B %-d %Y')" \
                -m "$MOVED" \
                -m "Automated by scripts/daily.sh." || echo "  commit failed"
  git push -q 2>/dev/null && echo "  pushed" || echo "  push skipped or failed (local commit kept)"
else
  echo "  nothing changed"
fi

# ---- 4. rebuild the shareable file ----------------------------------------
# The Claude artifact CANNOT be republished from here: the Artifact tool is not
# available to `claude -p` headless sessions (verified - it reports the tool is
# absent). So this step refreshes the self-contained HTML instead, and the
# artifact is updated by asking Claude interactively when you want it.
#
# board.standalone.html is produced by `npm run all` during the refresh and is
# a complete page on its own - it can be opened directly or hosted anywhere.
echo "--- shareable file ---"
if [ -f board.standalone.html ]; then
  echo "  board.standalone.html rebuilt ($(wc -c < board.standalone.html) bytes)"
  echo "  to update the Claude artifact, ask Claude: \"publish the board\""
else
  echo "  board.standalone.html missing - the build did not complete"
fi

echo "--- done $(date '+%H:%M:%S') ---"
