# N concurrent completion requests against the shell (TEST HARNESS): per-request ids / wall and the aggregate sequence-tokens per second
# python3 load_check.py <url> <N> <max_tokens>
import sys, json, time, threading, urllib.request
url, n, ntok = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
prompts = ["The capital of France is", "Hello", "The capital of France is", "Hello"] * 8
res = [None] * n
def go(i):
    body = json.dumps({"prompt": prompts[i], "max_tokens": ntok, "temperature": 0}).encode()
    t0 = time.time(); r = urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"})); j = json.load(r)
    res[i] = (time.time() - t0, j["choices"][0]["token_ids"], j["usage"]["prompt_tokens"] + j["usage"]["completion_tokens"])
t0 = time.time(); ths = [threading.Thread(target=go, args=(i,)) for i in range(n)]
[t.start() for t in ths]; [t.join() for t in ths]; wall = time.time() - t0
toks = sum(r[2] for r in res)
for i, r in enumerate(res): print(f"req {i}: {r[0]:.3f} s  {r[1]}")
print(f"LOAD\tN={n}\twall {wall:.3f} s\tsequence-tokens {toks}\t{toks/wall:.1f} seq-tokens/s")
