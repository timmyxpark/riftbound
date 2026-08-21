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
# caffeinate -i holds off idle sleep for exactly as long as the pull runs. A
# full refresh needs about three hours of continuous network, and this Mac is
# set to sleep after a minute idle - on Aug 20 it slept partway through, DNS
# went with it, and 23 cards came back as "nodename nor servname provided".
# This does NOT defeat closing the lid, and it cannot wake a sleeping machine:
# see the note at the foot of this file.
CAFF=""
command -v caffeinate >/dev/null 2>&1 && CAFF="caffeinate -i"
if ! RIFTBOUND_PYTHON="$VENV_PY" $CAFF bash scripts/refresh.sh; then
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

# ---- 3. refresh the published page ----------------------------------------
# docs/index.html is what GitHub Pages serves. It is a copy of the standalone
# board, committed alongside the data so the site and the snapshot never drift.
echo "--- published page ---"
if [ -f board.standalone.html ]; then
  mkdir -p docs
  cp board.standalone.html docs/index.html
  echo "  docs/index.html refreshed ($(wc -c < docs/index.html) bytes)"
else
  echo "  board.standalone.html missing - page not refreshed"
fi

# ---- 3b. commit -------------------------------------------------------------
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
echo "--- where it lands ---"
echo "  https://timmyxpark.github.io/riftbound/  (updates from this push, no human step)"
echo "  the Claude artifact is separate: ask Claude \"publish the board\" to update it,"
echo "  since the Artifact tool is not available to headless sessions."

echo "--- done $(date '+%H:%M:%S') ---"

# ---- what this job cannot do -----------------------------------------------
# It needs the Mac awake. caffeinate keeps it awake once the job has STARTED,
# but launchd cannot start a job on a machine that is asleep or off - it defers
# to the next wake, which may be hours late or, if the lid stays shut all day,
# not at all. To have the machine wake itself for the run:
#
#   sudo pmset repeat wake MTWRFSU 04:55:00
#
# (one repeating wake is all pmset allows, so it covers the 05:00 run only;
# the 17:00 run needs the Mac already awake.) A shut-down Mac cannot be woken
# by pmset at all.
#
# It also does not touch the Claude artifact: that tool is unavailable to
# headless sessions. A scheduled cloud routine republishes it from what this
# job pushes, and runs whether or not this machine is on - which means it can
# republish yesterday's prices perfectly happily. It reports the snapshot date
# every run so that is visible rather than silent.
