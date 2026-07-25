#!/usr/bin/env python3
"""Submit the jungle base-loop generation to OpenRouter's video API and wait.

Flow (per openrouter.ai/docs video-generation): POST /api/v1/videos ->
{id, polling_url} -> poll until status=completed -> download unsigned_urls[0].

Key: $OPENROUTER_API_KEY, or an OPENROUTER_API_KEY= line in
/home/tlister/llm-agent/.env. Conditioning rides inline as base64 data URIs.

Loop strategies (the 2026-07-24 rework — same-image first+last made the
model minimize motion and every theme read as a still):
  clip A: --frame <canvas> --no-last-frame          (free-running motion)
  clip B: --frame <A's final frame> --last-frame <canvas>   (bridges home)
prep_loop.py --clip-b stitches A+B into one loop whose seam lands on the
canvas arrangement with motion intact. --last-frame defaults to --frame,
which reproduces the old closed-loop behavior.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://openrouter.ai/api/v1/videos'
ENV_FILE = '/home/tlister/llm-agent/.env'


def api_key():
    k = os.environ.get('OPENROUTER_API_KEY', '')
    if not k and os.path.exists(ENV_FILE):
        for line in open(ENV_FILE):
            line = line.strip()
            if line.startswith('OPENROUTER_API_KEY='):
                k = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not k:
        sys.exit('no OPENROUTER_API_KEY in env or ' + ENV_FILE)
    return k


def call(url, key, payload=None, raw=False):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}'})
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(payload).encode()
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    return body if raw else json.loads(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='bytedance/seedance-2.0')
    ap.add_argument('--size', default='960x720')
    ap.add_argument('--duration', type=int, default=12)
    ap.add_argument('--seed', type=int, default=20260724)
    ap.add_argument('--frame', default=os.path.join(HERE, 'jungle_base_960x720.png'))
    ap.add_argument('--last-frame', default=None,
                    help='last_frame image; default = --frame (closed loop)')
    ap.add_argument('--prompt-file', default=os.path.join(HERE, 'prompt.txt'))
    ap.add_argument('--out', default=os.path.join(HERE, 'clip_raw.mp4'))
    ap.add_argument('--no-last-frame', action='store_true',
                    help='condition on first_frame only')
    ap.add_argument('--text-only', action='store_true',
                    help='no frame conditioning (new scene from prompt alone)')
    ap.add_argument('--poll-s', type=int, default=15)
    ap.add_argument('--timeout-s', type=int, default=900)
    args = ap.parse_args()

    key = api_key()
    payload = {
        'model': args.model,
        'prompt': open(args.prompt_file).read().strip(),
        'size': args.size,
        'duration': args.duration,
        'seed': args.seed,
        'generate_audio': False,
        # slug guess; unmatched provider options are dropped harmlessly
        'provider': {'options': {'bytedance': {'parameters': {'watermark': False}}}},
    }
    if not args.text_only:
        def data_uri(path):
            return ('data:image/png;base64,'
                    + base64.b64encode(open(path, 'rb').read()).decode())
        frames = [{'type': 'image_url', 'image_url': {'url': data_uri(args.frame)},
                   'frame_type': 'first_frame'}]
        if not args.no_last_frame:
            frames.append({'type': 'image_url',
                           'image_url': {'url': data_uri(args.last_frame or args.frame)},
                           'frame_type': 'last_frame'})
        payload['frame_images'] = frames

    log = {'payload_sans_images': {k: v for k, v in payload.items()
                                   if k != 'frame_images'}}
    try:
        sub = call(API, key, payload)
    except urllib.error.HTTPError as e:
        sys.exit(f"submit failed {e.code}: {e.read().decode()[:800]}")
    log['submit'] = sub
    if 'id' not in sub:  # transient provider hiccup — rerun the submit
        sys.exit(f"submit response missing id: {json.dumps(sub)[:800]}")
    print('job', sub.get('id'), sub.get('status'))
    poll_url = sub.get('polling_url') or f"{API}/{sub['id']}"

    t0 = time.time()
    st = {}
    while time.time() - t0 < args.timeout_s:
        time.sleep(args.poll_s)
        st = call(poll_url, key)
        print(f"  {int(time.time() - t0)}s status={st.get('status')}")
        if st.get('status') in ('completed', 'failed'):
            break
    log['final'] = st
    stem = os.path.splitext(os.path.basename(args.out))[0]
    json.dump(log, open(os.path.join(HERE, f'job_log_{stem}.json'), 'w'), indent=1)
    if st.get('status') != 'completed':
        sys.exit(f"not completed: {json.dumps(st)[:800]}")

    # the "unsigned" URL is the /content endpoint and still wants auth
    urls = st.get('unsigned_urls') or [f"{poll_url}/content"]
    data = call(urls[0], key, raw=True)
    open(args.out, 'wb').write(data)
    print(f"wrote {args.out} ({len(data)/1e6:.1f} MB)")
    for k in ('usage', 'cost', 'total_cost'):
        if k in st:
            print(k, st[k])


if __name__ == '__main__':
    main()
