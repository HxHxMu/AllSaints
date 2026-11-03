#!/usr/bin/env bash
# Tell Telegram that a workflow run failed (the job crashed, not just one post: those report themselves).
# Only on the first failure in a row, so a broken poll doesn't message every 10 minutes.
# Usage: notify-failure.sh "<what failed, in plain words>" <workflow file>
set -u
prev=$(gh run list -R "$GITHUB_REPOSITORY" --workflow "$2" --limit 10 --json databaseId,conclusion \
  -q "[.[] | select(.databaseId != $GITHUB_RUN_ID and (.conclusion == \"success\" or .conclusion == \"failure\"))][0].conclusion" 2>/dev/null)
[ "$prev" = "failure" ] && { echo "The previous run failed too: already reported"; exit 0; }
export MSG="⚠️ $1
It retries on its next scheduled run. If it keeps failing, you won't get repeat messages.
$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
pip install -q requests >/dev/null 2>&1
cd engine && python -c "import os, telegram; telegram.send(os.environ['MSG'])"
