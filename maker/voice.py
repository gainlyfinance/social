"""Hindi voice-over for the videos.

Google Cloud Text-to-Speech (key in GOOGLE_TTS_KEY). Each scene's line is read separately, so the video can give
every scene the time its sentence needs. Sarvam AI can be added the same way later.
"""
import base64
import io
import json
import os
import urllib.request
import wave

import numpy as np

SR = 44100
API = 'https://texttospeech.googleapis.com/v1'


def _post(path, payload, key):
    req = urllib.request.Request(f'{API}/{path}?key={key}', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def hindi_voices(key=None):
    key = key or os.environ['GOOGLE_TTS_KEY']
    with urllib.request.urlopen(f'{API}/voices?languageCode=hi-IN&key={key}', timeout=30) as r:
        return sorted((v['name'], v.get('ssmlGender', '')) for v in json.loads(r.read().decode()).get('voices', []))


def speak(text, voice, key=None):
    """One sentence as a float array at 44.1 kHz, mono."""
    key = key or os.environ['GOOGLE_TTS_KEY']
    res = _post('text:synthesize', {
        'input': {'text': text},
        'voice': {'languageCode': 'hi-IN', 'name': voice},
        'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': SR},
    }, key)
    with wave.open(io.BytesIO(base64.b64decode(res['audioContent']))) as w:
        rate, ch = w.getframerate(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if ch > 1:
        data = data.reshape(-1, ch).mean(1)
    if rate != SR:
        data = np.interp(np.arange(0, len(data) * SR / rate) * rate / SR, np.arange(len(data)), data)
    # Trim silence at both ends so the scene timing is tight.
    loud = np.where(np.abs(data) > 0.01)[0]
    return data[loud[0]: loud[-1] + 1] if len(loud) else data
