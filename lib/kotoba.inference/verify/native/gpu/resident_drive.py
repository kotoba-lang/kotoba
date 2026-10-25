# drive a resident guest over its stdin/stdout pipe: prompt ids, then feed each argmax back (TEST HARNESS beside the
# oracle, not tooling; the serving shell is serve_http.cljk). python3 resident_drive.py <loader> <resident.bin> <offset> <ids> <ntok> [requests] [isa]
import subprocess, sys, os, time, struct
loader, binf, off, plen_ids, ntok, reqs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6]) if len(sys.argv) > 6 else 1
isa = sys.argv[7] if len(sys.argv) > 7 else "x86_64"
PB = int(sys.argv[8]) if len(sys.argv) > 8 else 0   # prefill bucket of the guest (prefill:<P>): the prompt goes in chunks of P tokens, one message each
# T top_p seed (iteration 50): the last prompt token and every generated token go as the 5-word sampled message
SAMPLE = (float(sys.argv[9]), float(sys.argv[10]), int(sys.argv[11], 0)) if len(sys.argv) > 11 else None
def bits(f): return struct.unpack("<I", struct.pack("<f", f))[0]
env = dict(os.environ, KEXE_RESULT_TYPE="string", KEXE_STRUCTURED_REPORT="1", KEXE_FUEL="1000000000", KEXE_WALL_SECONDS="86400", KEXE_STRING_POOL="16777216", KEXE_PAIRS="4194304")
t0 = time.time()
p = subprocess.Popen([loader, binf, off, "0", isa, "42,33,41,37,39"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, bufsize=0)
def step(tok, reset, sampled=False):
    tail = f",{bits(SAMPLE[0])},{bits(SAMPLE[1])},{SAMPLE[2]}" if (sampled and SAMPLE) else ""
    p.stdin.write(f"{tok},{1 if reset else 0}{tail}".encode()); p.stdin.flush()
    line = p.stdout.readline().decode().strip()
    ns, idhex = line.split("|"); return int(ns), struct.unpack("<I", bytes.fromhex(idhex))[0]
def prefill(toks, reset):   # exactly PB tokens: one batched step
    p.stdin.write((",".join(str(t) for t in toks) + f",{1 if reset else 0}").encode()); p.stdin.flush()
    line = p.stdout.readline().decode().strip()
    ns, idhex = line.split("|"); return int(ns), struct.unpack("<I", bytes.fromhex(idhex))[0]
first = None
for r in range(reqs):
    ids = [int(t) for t in plen_ids.split(",")]; out = []; nss = []; tr = time.time()
    i = 0
    while PB and len(ids) - i > PB:   # strictly more than a chunk left: the last prompt token is always a single (sampled) message
        ns, am = prefill(ids[i:i + PB], i == 0); nss.append(ns); i += PB
    for j in range(i, len(ids)):
        ns, am = step(ids[j], j == 0, sampled=(j == len(ids) - 1)); nss.append(ns)
    out.append(am)
    for _ in range(ntok - 1):
        ns, am = step(am, False, sampled=True); nss.append(ns); out.append(am)
    print(f"request {r}: generated {','.join(map(str, out))}  steps {len(nss)}  gpu ms total {sum(nss)/1e6:.1f}  wall {time.time()-tr:.3f} s" + ("" if first is None else ("  same" if out == first else "  DIFFERENT")))
    if first is None: first = out; print(f"first request wall since process start {time.time()-t0:.2f} s")
p.stdin.close(); rest = p.stdout.read().decode(); p.wait(); print(rest.strip()[-300:])
