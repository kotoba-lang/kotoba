# alternate two prompts on one resident guest: the rewind must give the single-prompt answers each time (TEST HARNESS).
# python3 resident_mix.py <loader> <resident.bin> <offset> [isa] [prefill-bucket]
import subprocess, sys, os, struct
loader, binf, off = sys.argv[1:4]; isa = sys.argv[4] if len(sys.argv) > 4 else "x86_64"
PB = int(sys.argv[5]) if len(sys.argv) > 5 else 0   # prefill bucket: prompt chunks of PB tokens per message
env = dict(os.environ, KEXE_RESULT_TYPE="string", KEXE_STRUCTURED_REPORT="1", KEXE_FUEL="1000000000", KEXE_WALL_SECONDS="86400", KEXE_STRING_POOL="1073741824", KEXE_PAIRS="67108864")
p = subprocess.Popen([loader, binf, off, "0", isa, "42,33,41,37,39"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, bufsize=0)
def step(tok, reset):
    p.stdin.write(f"{tok},{1 if reset else 0}".encode()); p.stdin.flush()
    ns, idhex = p.stdout.readline().decode().strip().split("|"); return struct.unpack("<I", bytes.fromhex(idhex))[0]
def msg(toks, reset):
    p.stdin.write((",".join(str(t) for t in toks) + f",{1 if reset else 0}").encode()); p.stdin.flush()
    ns, idhex = p.stdout.readline().decode().strip().split("|"); return struct.unpack("<I", bytes.fromhex(idhex))[0]
def run(ids, ntok):
    out = []; i = 0
    while PB and len(ids) - i >= PB: am = msg(ids[i:i + PB], i == 0); i += PB
    for j in range(i, len(ids)): am = step(ids[j], j == 0)
    out.append(am)
    for _ in range(ntok - 1): am = step(am, False); out.append(am)
    return out
A = ([760, 6511, 314, 9338, 369], 8, [128186, 116769, 166224, 2752, 2752, 132819, 176133, 4032])   # oracle, tick 37
B = ([9707, 198, 220], 2, [169222, 169484])                                                                   # oracle, tick 36
ok = 0; n = 0
for ids, ntok, exp in [A, B, A, B, B, A]:
    got = run(ids, ntok); n += 1; ok += got == exp
    print(("OK  " if got == exp else "BAD ") + str(got))
print(f"MIXED\t{ok}/{n} requests equal to the single-prompt oracle")
p.stdin.close(); p.wait()
