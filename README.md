# Gainly social autopilot

Makes Gainly's daily Hindi video (YouTube Shorts, Instagram Reel, Facebook Reel) and picture post (Instagram,
Facebook) from the gainly.in calculators. Plan and status: `SOCIAL_PLAN.md` in the main repo. This folder becomes
the public GitHub repo `gainlyfinance/social`.

## Make the media

    pip install playwright numpy scipy && python3 -m playwright install chromium   # once; ffmpeg must be installed
    python3 maker/make.py queue/samples.json out/            # every item
    python3 maker/make.py queue/samples.json out/ <slug>     # one item

For each item: `out/<slug>.jpg` (1080x1350 picture) and `out/<slug>.mp4` (1080x1920, about 28 s, our own music).
Format: suspense, the second number is hidden and sent to people who comment the keyword (see SOCIAL_PLAN.md).

- `queue/*.json`: one entry per post: hook, inputs, result, bars, twist (hidden second number), keyword,
  reply, question, note, title, caption, hashtags, mood (calm, growth, serious, desi). Numbers always come from the gainly.in calculators.
  No example person (name, town) in social posts: those stay in the blog posts only.
- `maker/template.html`: the look (site logo, Gainly colours, Anek font). The same page draws the picture and,
  frame by frame, the video.
- Backgrounds change every day (owner's rule, 22 Oct 2026: not everything the same dark blue). `THEMES` in the
  template has 10 colour themes (6 dark, 4 light, the light ones use the dark logo) and 5 patterns plus textures.
  The theme is picked from the date, so two days in a row never match, and the day's picture uses a different theme
  from the day's video. A queue entry can force one with `"theme"` (video) or `"card_theme"` (picture).
- `maker/music.py`: background music made by code, different for every video (seeded by the slug), no copyright.
- `assets/`: logo (from `web/public/img/brand`) and fonts (Anek, SIL Open Font License).

## The daily autopilot (GitHub Actions)

| Workflow | When (India time) | What |
|---|---|---|
| Prepare tomorrow's post | 20:30 the evening before | Makes the picture and video with the Hindi voice (`config.json` voice), puts them on GitHub Pages, opens an issue for the owner |
| Publish video | 06:00 | YouTube Short, Instagram Reel, Facebook Reel, Threads |
| Publish photo | 19:00 | Instagram, Facebook, Threads |
| Answer keyword comments | every 30 min | Replies to comments with the post's keyword (`SIP 20` …) with the post's `reply` |
| Check keys | by hand | Tests every secret, posts nothing |
| Voice samples | by hand | Same video in several Hindi voices |

- Every issue the autopilot opens is locked at once (only the owner and collaborators can comment), and only their
  `stop` counts.
- `config.json`: `start_date` (nothing runs on schedule before it), `mode` (`approve`: write `stop` on the day's issue
  to hold the posts, `auto`: no issue needed), voice, platforms.
- `queue/2026-MM.json`: one entry per day with a `date`. A day with no entry is skipped.
  When fewer than 5 days are left in the queue, the evening job opens a locked `queue` issue (GitHub emails the
  owner). It closes itself once the queue is filled. Claude prepares the next month's queue around the 20th.
- The `data` branch (rewritten as one commit each time) keeps the media of the last 21 days and the state: what was
  posted where (`state/published.json`), which comments were answered, and the renewed Threads token (encrypted).
- Manual runs of Publish and Answer default to a dry run that only prints what would happen.
- Secrets: see `tools/verify.py`. GitHub Pages must be set to "GitHub Actions" (Settings > Pages).
