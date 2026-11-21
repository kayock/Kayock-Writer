"""Mock OpenAI-compatible provider for offline testing and demos.

Implements /health, /v1/models, and /v1/chat/completions. Responses are
deterministic, shaped by keyword inspection of the request (title requests
get a short title; selection-workshop requests get three <<<ALT>>>
passages; polish requests return visibly edited text; everything else gets
a creative-looking passage echoing the requested theme/voice).
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _craft_text(payload: dict) -> str:
    messages = payload.get('messages') or []
    system = ''
    user = ''
    for m in messages:
        if m.get('role') == 'system' and not system:
            system = str(m.get('content') or '')
        elif m.get('role') == 'user' and not user:
            user = str(m.get('content') or '')
    combined = (system + '\n' + user)

    # Title request?
    if system.startswith('You title poems') or system.startswith('You title short stories'):
        theme = ''
        m = re.search(r'Theme: (.*)', user)
        if m:
            theme = m.group(1).strip()
        words = [w for w in re.findall(r"[A-Za-z']+", theme)][:3] or ['Quiet', 'Signal']
        return 'The ' + ' '.join(w.capitalize() for w in words) + ' Reminder'

    # Selection workshop: three alternatives separated by <<<ALT>>>
    if 'Selected Lines and Stanza Workshop' in system:
        sel = ''
        m = re.search(r'SELECTED PASSAGE TO REPLACE:\n(.*?)\n\nAFTER', user, re.S)
        if m:
            sel = m.group(1).strip()
        lines = [ln for ln in sel.splitlines() if ln.strip()] or ['the quiet line']
        alts = []
        for n in range(3):
            alts.append('\n'.join(f'{ln} (reworked {n + 1})' for ln in lines[:2] or lines))
        return '\n<<<ALT>>>\n'.join(alts)

    # Weaver planner: JSON source map
    if 'Weaver planning stage' in system:
        titles = re.findall(r'SOURCE \d+ — (.*)', user)
        roles = [{'title': t.strip(), 'role': 'Contributes imagery.'} for t in titles[:4]]
        return json.dumps({'suggested_title': 'Woven Threads', 'shared_threads': ['memory', 'hunger'],
                           'structure': 'Three movements.', 'source_roles': roles,
                           'passage_plan': ['Start', 'Turn']})

    # Polisher: return the submitted work with a visible edit
    if 'Polisher' in system:
        m = re.search(r'POEM:\n(.*)$', user, re.S) or re.search(
            r'SUBMITTED SHORT STORY — PRIMARY AUTHORITY:\n(.*)$', user, re.S)
        body = (m.group(1) if m else 'text to polish').strip()
        if 'RETRY REQUIREMENT' in user:
            return body + ' Revised once more for rhythm and clarity.'
        return body.replace('.', '. Lightly polished', 1) + '\n\n(A polished pass touched the phrasing.)'

    # Weaver generation: return clean work (no annotations)
    if 'The Weaver' in system and 'planning stage' not in system:
        if 'Twine output' in system or 'Twee' in system:
            return ':: Start\n\nThe road opens.\n\n:: Turning\n\nThe stars lean closer.'
        return 'Woven prose begins here, threading both sources into one voice. ' \
               'The images braid; the ending lands softly.'

    # Creator (poem or story): compose something responsive
    voice_line = ''
    m = re.search(r'Creative voice profile: (.*)', user)
    if m:
        voice_line = f'— in the {m.group(1).strip()} voice'
    theme = ''
    m = re.search(r'Theme: (.*)', user)
    if m:
        theme = m.group(1).strip()
    if 'Short Story Creator' in system:
        body = (f'The night {theme or "of the promise"} arrived early{voice_line}. '
                'Marcus counted the streetlights twice and waited anyway. '
                'When the door finally opened, the room behind it was smaller than memory, '
                'and the man inside it was not. That was the turn: the stranger set down '
                'the lantern, said the debt was paid, and left before dawn took the porch.')
        return body
    lines = [
        f'{theme or "The hour"} came back for me tonight,',
        'the way old songs return without asking,',
        'and I let it in like family,',
        'because some hungers are just love wearing work clothes.',
        'I have buried gods and carried cities,',
        'but the porch light still wins the argument.',
        'So once more I answer the door,',
        'and eternity answers back.',
    ]
    return '\n'.join(lines)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/health'):
            self._json({'ok': True})
        elif self.path.startswith('/v1/models'):
            self._json({'object': 'list', 'data': [{'id': 'mock-model'}]})
        else:
            self._json({'error': 'not found'}, code=404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        payload = json.loads(raw.decode('utf-8') or '{}')
        text = _craft_text(payload)
        self._json({
            'id': 'mock', 'object': 'chat.completion',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': text}}],
        })


def start_mock_server(host='127.0.0.1', port=0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MockHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == '__main__':
    srv = start_mock_server('127.0.0.1', 8907)
    print('Mock model endpoint on http://127.0.0.1:8907 (Ctrl+C to stop)')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
