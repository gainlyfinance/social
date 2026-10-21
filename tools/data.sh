#!/bin/sh
# The "data" branch holds the made media (last few weeks) and the state files. It is rewritten as one commit each
# time, so the repository does not grow forever.
#   sh tools/data.sh get     clone it into ./data (or start empty)
#   sh tools/data.sh save    prune old media and force-push ./data as the new "data" branch
#   sh tools/data.sh site    copy the media into ./site for GitHub Pages
set -e
REMOTE="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
case "$1" in
  get)
    rm -rf data
    git clone -q --depth 1 --branch data "$REMOTE" data 2>/dev/null || mkdir -p data/state data/media
    ;;
  save)
    KEEP=$(python3 -c "import json;print(json.load(open('config.json')).get('keep_media_days',21))")
    CUT=$(date -u -d "-${KEEP} days" +%Y-%m-%d)
    for d in data/media/*/; do
      [ -d "$d" ] || continue
      n=$(basename "$d"); [ "$n" \< "$CUT" ] && rm -rf "$d"
    done
    cd data
    rm -rf .git
    git init -q -b data
    git add -A
    git -c user.name="Gainly autopilot" -c user.email="noreply@gainly.in" commit -q -m "data $(date -u +%FT%TZ)"
    git push -q -f "$REMOTE" data
    ;;
  site)
    rm -rf site && mkdir -p site
    [ -d data/media ] && cp -r data/media site/
    touch site/.nojekyll
    printf '<!doctype html><meta charset="utf-8"><title>Gainly media</title><p>Media for Gainly posts. <a href="https://gainly.in">gainly.in</a></p>\n' > site/index.html
    ;;
esac
