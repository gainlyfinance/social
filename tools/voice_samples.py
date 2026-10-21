"""Makes the same video with several Google Hindi voices, so the owner can pick one. Run by "Voice samples".

    python3 tools/voice_samples.py queue/samples.json out/ sip-5000-10-saal
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'maker'))
import voice  # noqa: E402


def pick(voices):
    """Two female and two male Chirp 3 HD voices (the most natural), and one of each from Neural2 or WaveNet."""
    out = []
    for family, per_gender in (('Chirp3-HD', 2), ('Neural2', 1), ('Wavenet', 1)):
        for gender in ('FEMALE', 'MALE'):
            got = [n for n, g in voices if family in n and g == gender][:per_gender]
            out += got
        if family == 'Neural2' and any('Neural2' in n for n in out):
            break
    return out


def main():
    queue, outdir, slug = sys.argv[1], sys.argv[2], sys.argv[3]
    voices = voice.hindi_voices()
    print('Hindi voices available:', len(voices))
    chosen = pick(voices)
    print('Making samples with:', ', '.join(chosen))
    for name in chosen:
        env = dict(os.environ, VOICE=name, VOICE_IN_NAME='1')
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), '..', 'maker', 'make.py'), queue, outdir, slug],
                       env=env, check=True)


if __name__ == '__main__':
    main()
