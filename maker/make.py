"""Makes the picture post and the vertical video for each queue item.

    python3 maker/make.py queue/samples.json out/            all items
    python3 maker/make.py queue/samples.json out/ <slug>     one item

For each item: out/<slug>.jpg (1080x1350 feed picture) and out/<slug>.mp4 (1080x1920, 25 fps, H.264 + AAC, with our
own background music). The voice step comes later: when an item has a "voice" file, it is mixed in and the music
is lowered under it.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import music  # noqa: E402

FPS = 25


def card(page, item, out):
    page.set_viewport_size({'width': 1080, 'height': 1350})
    page.add_init_script(f'window.ITEM = {json.dumps(item, ensure_ascii=False)}; window.MODE = "card";')
    page.goto((HERE / 'template.html').as_uri())
    page.evaluate('window.READY')
    page.screenshot(path=str(out), type='jpeg', quality=92)


def video(page, item, out):
    page.set_viewport_size({'width': 1080, 'height': 1920})
    page.add_init_script(f'window.ITEM = {json.dumps(item, ensure_ascii=False)}; window.MODE = "video";')
    page.goto((HERE / 'template.html').as_uri())
    page.evaluate('window.READY')
    duration = page.evaluate('window.DURATION')
    frames = int(duration * FPS)

    with tempfile.TemporaryDirectory() as tmp:
        silent = pathlib.Path(tmp) / 'video.mp4'
        enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg',
                                '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                                '-movflags', '+faststart', str(silent)], stdin=subprocess.PIPE)
        for f in range(frames):
            page.evaluate(f'renderAt({f / FPS})')
            enc.stdin.write(page.screenshot(type='jpeg', quality=90))
        enc.stdin.close()
        if enc.wait() != 0:
            raise SystemExit('ffmpeg failed while encoding frames')

        wav = pathlib.Path(tmp) / 'music.wav'
        music.write(music.make(item.get('mood', 'calm'), item['slug'], duration + 0.5), wav)
        voice = item.get('voice')
        if voice:
            # Voice on top, music ducked to about a fifth under it.
            audio = ['-i', str(wav), '-i', voice, '-filter_complex',
                     '[1:a]volume=1.0[v];[0:a]volume=0.22[m];[m][v]amix=inputs=2:duration=first:dropout_transition=0[a]', '-map', '0:v', '-map', '[a]']
            cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-i', str(silent)] + audio
        else:
            cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-i', str(silent), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-filter:a', 'volume=0.8']
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out)]
        subprocess.run(cmd, check=True)


def main():
    queue = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3] if len(sys.argv) > 3 else None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for item in queue:
            if only and item['slug'] != only:
                continue
            for kind, fn, ext in (('card', card, 'jpg'), ('video', video, 'mp4')):
                page = browser.new_page()
                fn(page, item, out / f"{item['slug']}.{ext}")
                page.close()
            print(item['slug'])
        browser.close()


if __name__ == '__main__':
    main()
