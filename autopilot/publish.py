"""Posts today's picture or video on every platform in config.json.

    python3 autopilot/publish.py photo
    python3 autopilot/publish.py video

Already-posted platforms are skipped, so a re-run only retries what failed. A failure on one platform does not stop
the others, and the job ends with an error so GitHub sends an email.
"""
import sys
import time

import approval
import platforms as P
from common import started, CONFIG, DRY, caption_for, item_for, log, media_dir, media_url, save_state, state, today
from tokens import threads_token


def main(kind):
    if not started():
        log('Autopilot not started yet (config.json start_date). Nothing to do.')
        return 0
    date = today()
    item = item_for(date)
    day = state('days').get(date, {})
    if not item or not day.get('prepared'):
        log('Nothing prepared for', date)
        return 0
    if approval.stopped(date):
        log('Owner said stop for', date)
        approval.note(date, f'⏸ {kind} रोका गया (stop)।', close=(kind == 'video'))
        return 0

    slug = item['slug']
    video_file = media_dir(date) / f'{slug}.mp4'
    video_url = media_url(date, f'{slug}.mp4')
    photo_url = media_url(date, f'{slug}.jpg')
    published = state('published', [])
    done = {(p['date'], p['kind'], p['platform']) for p in published}
    results, failed = [], []

    for platform in CONFIG['platforms'][kind]:
        if (date, kind, platform) in done:
            log('Already posted:', platform)
            continue
        try:
            if kind == 'video':
                if platform == 'youtube':
                    pid = P.youtube_short(str(video_file), item['title'], caption_for(item, 'youtube'), item.get('hashtags', []))
                elif platform == 'instagram':
                    pid = P.instagram_reel(video_url, caption_for(item, 'instagram'), item.get('ig_audio_id'))
                elif platform == 'facebook':
                    pid = P.facebook_reel(video_url, caption_for(item, 'facebook'))
                elif platform == 'threads':
                    pid = P.threads_post(threads_token(), caption_for(item, 'threads'), video_url=video_url)
            else:
                if platform == 'instagram':
                    pid = P.instagram_photo(photo_url, caption_for(item, 'instagram'))
                elif platform == 'facebook':
                    pid = P.facebook_photo(photo_url, caption_for(item, 'facebook'))
                elif platform == 'threads':
                    pid = P.threads_post(threads_token(), caption_for(item, 'threads'), image_url=photo_url)
            log('Posted', kind, 'on', platform, pid)
            results.append(f'✅ {platform}')
            if not DRY:
                published.append({'date': date, 'kind': kind, 'platform': platform, 'id': pid, 'slug': slug, 'at': int(time.time())})
                save_state('published', published)
        except Exception as e:  # noqa: BLE001
            log('FAILED on', platform, '-', e)
            results.append(f'❌ {platform}: {str(e)[:200]}')
            failed.append(platform)

    if results:
        approval.note(date, ('(dry run) ' if DRY else '') + f'{kind}: ' + ' · '.join(results), close=(kind == 'video' and not failed and not DRY))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
