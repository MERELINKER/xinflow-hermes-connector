"""Bounded media work inside the existing Hermes container; never changes gateway config."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, '/opt/data/lazy-packages')
sys.path.insert(0, '/opt/hermes')
MAX_BYTES = 6 * 1024 * 1024
MIMES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.m4a': 'audio/mp4', '.mp4': 'audio/mp4', '.webm': 'audio/webm'}


def data_url(path):
    from gateway.platforms.base import validate_media_delivery_path
    safe = validate_media_delivery_path(str(path))
    if not safe:
        raise ValueError('Media path denied')
    p = Path(safe)
    mime = MIMES.get(p.suffix.lower())
    if not mime or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError('Unsupported or oversized media')
    return {'type': mime.split('/')[0], 'name': p.name, 'dataUrl': 'data:' + mime + ';base64,' + base64.b64encode(p.read_bytes()).decode()}


def perform(body):
    action = body['action']
    if action == 'resolve':
        from gateway.platforms.base import MEDIA_TAG_CLEANUP_RE
        media = []
        def replace(match):
            if len(media) >= 4:
                return match.group(0)
            try:
                item = data_url(match.group('path'))
            except (OSError, ValueError):
                return match.group(0)
            if sum(len(x['dataUrl']) for x in media) + len(item['dataUrl']) > 12 * 1024 * 1024:
                return match.group(0)
            media.append(item)
            return ''
        text = MEDIA_TAG_CLEANUP_RE.sub(replace, body.get('text', ''))
        return {'text': text.strip(), 'media': media}
    if action == 'transcribe':
        import re
        match = re.fullmatch(r'data:(audio/(?:wav|x-wav|mpeg|mp3|mp4|m4a|x-m4a|ogg|webm|aac)|video/(?:mp4|webm));base64,([A-Za-z0-9+/]+={0,2})', body['dataUrl'])
        if not match:
            raise ValueError('Unsupported audio type')
        raw = base64.b64decode(match[2], validate=True)
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError('Audio exceeds 6 MB')
        suffix = {'mpeg': 'mp3', 'x-wav': 'wav', 'x-m4a': 'm4a'}.get(match[1].split('/')[1], match[1].split('/')[1])
        with tempfile.TemporaryDirectory(prefix='xinflow-audio-') as folder:
            p = Path(folder) / ('voice.' + suffix)
            p.write_bytes(raw)
            from tools.transcription_tools import transcribe_audio
            result = transcribe_audio(str(p), source='xinflow-plugin')
            if not result.get('success') or not result.get('transcript', '').strip():
                raise ValueError('语音识别失败，请检查Hermes服务器的STT配置')
            return {'text': result['transcript']}
    if action == 'speech':
        text = body.get('text', '')
        if not isinstance(text, str) or not text.strip() or len(text) > 12000:
            raise ValueError('Speech text must be 1-12000 characters')
        from hermes_cli.config import load_config
        config = load_config().get('tts') or {}
        if config.get('provider') == 'mimo':
            import urllib.request
            from dotenv import dotenv_values
            voice = config.get('mimo') or {}
            key = os.environ.get('MIMO_API_KEY') or dotenv_values('/opt/data/.env').get('MIMO_API_KEY')
            if not key:
                raise ValueError('服务器未配置MIMO_API_KEY')
            messages = []
            if voice.get('instructions'):
                messages.append({'role': 'user', 'content': voice['instructions']})
            messages.append({'role': 'assistant', 'content': text})
            payload = {'model': voice.get('model', 'mimo-v2.5-tts'), 'messages': messages, 'audio': {'format': 'wav', 'voice': voice.get('voice', 'mimo_default')}, 'stream': False}
            request = urllib.request.Request('https://api.xiaomimimo.com/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'api-key': key}, method='POST')
            with urllib.request.urlopen(request, timeout=120) as reply:
                result = json.load(reply)
            audio = result['choices'][0]['message']['audio']['data']
            raw = base64.b64decode(audio, validate=True)
            if not raw or len(raw) > MAX_BYTES:
                raise ValueError('音频超过6MB，请选择较短回复')
            return {'media': [{'type': 'audio', 'name': 'reply.wav', 'dataUrl': 'data:audio/wav;base64,' + audio}]}
        from tools.tts_tool import text_to_speech_tool
        with tempfile.TemporaryDirectory(prefix='xinflow-speech-') as folder:
            result = json.loads(text_to_speech_tool(text, output_path=folder + '/reply.mp3'))
            if not result.get('success'):
                raise ValueError('音频生成失败，请检查Hermes服务器的TTS服务')
            return {'media': [data_url(p) for p in result.get('file_paths', [result['file_path']])]}
    raise ValueError('Unknown media action')


if __name__ == '__main__':
    try:
        value = json.loads(sys.stdin.read(10 * 1024 * 1024))
        print(json.dumps(perform(value), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        sys.exit(1)
