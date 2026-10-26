"""Local Hugging Face dedicated Endpoint relay. Tokens never enter browser storage."""
import json, os, sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, sys.argv[1])
try:
    endpoint = sys.argv[3].rstrip('/')
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'https' or not parsed.hostname or
        not parsed.hostname.endswith('.endpoints.huggingface.cloud') or
        parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port):
        raise ValueError('expected HTTPS Hugging Face dedicated Endpoint URL')
    token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGING_FACE_HUB_TOKEN')
    token_file = Path(os.environ.get('HF_TOKEN_PATH', str(Path(os.environ.get('HF_HOME', str(Path.home()/'.cache/huggingface')))/'token')))
    if not token:
        token = token_file.read_text().strip()
    if not token:
        raise ValueError('HF_TOKEN or HF_TOKEN_PATH is required')
    import httpx
    payload = json.loads(sys.stdin.buffer.read(1048577))
    if payload.get('model') != sys.argv[2]:
        raise ValueError('model differs from selected qualification route')
    url = endpoint + ('/chat/completions' if endpoint.endswith('/v1') else '/v1/chat/completions')
    with httpx.stream('POST', url, headers={'Authorization': 'Bearer ' + token},
                      json=payload, timeout=httpx.Timeout(120, connect=15), follow_redirects=False) as response:
        metadata = {'status': response.status_code, 'contentType': response.headers.get('content-type', 'application/json')}
        sys.stdout.buffer.write((json.dumps(metadata) + '\n').encode())
        sys.stdout.buffer.flush()
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > 16 * 1024 * 1024:
                raise ValueError('upstream stream exceeds relay byte limit')
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
except BaseException as error:
    # Do not print request objects, config, exceptions carrying URLs/credentials, or headers.
    sys.stderr.write(type(error).__name__ + '\n')
    sys.exit(1)
