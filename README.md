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
- `maker/music.py`: background music made by code, different for every video (seeded by the slug), no copyright.
- `assets/`: logo (from `web/public/img/brand`) and fonts (Anek, SIL Open Font License).

Not built yet: voice (Sarvam or Google TTS), uploading to YouTube, Instagram and Facebook, the daily GitHub Action.
