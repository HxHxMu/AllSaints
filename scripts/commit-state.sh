#!/usr/bin/env bash
# Commit pipeline state back to the repo, retrying on concurrent pushes.
set -u
git config user.name "A.S. bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add state data 2>/dev/null
git diff --cached --quiet && { echo "No state changes"; exit 0; }
# Cloudflare Pages skips "[skip ci]" commits; let it rebuild the site only when an episode
# goes public or gets its YouTube Short (no GitHub workflow runs on push either way).
skip=" [skip ci]"
git diff --cached -U0 -- state/episodes | grep -qE '^\+ *"(status": "published|url": "https://youtube\.com/shorts/)' && skip=""
git commit -q -m "state: $1$skip"
for i in 1 2 3 4 5; do
  git pull -q --rebase -X theirs origin main && git push -q origin HEAD:main && exit 0
  sleep $((i * 3))
done
echo "Failed to push state" && exit 1
