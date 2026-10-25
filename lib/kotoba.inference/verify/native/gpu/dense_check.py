# Compares dense_ref.npz (f64 oracle, dense_ref.py) against a CPU-only llama-server -- a TEST ORACLE's check, not tooling.
#   python3 dense_check.py <server-url> <dense_ref.npz>
# (a) greedy continuation ids: POST /completion temperature 0, prompt = the oracle's forced ids, n_predict = generated count
# (b) last prompt position: POST /completion n_predict 1 with n_probs = vocab -> full logprob vector; reports top-1 match,
#     KL(llama || oracle), KL(oracle || llama) (llama's f32 logprobs renormalised first; the raw mass is printed),
#     max |delta logprob| and the rank of llama's top-1 in the oracle.
# Exit 0 = both compared and continuation matches; 1 = compared, mismatch; 2 = could not compare (says why).
import sys, json, urllib.request, numpy as np
def refuse(msg): sys.stdout.flush(); print("REFUSE", msg, file=sys.stderr, flush=True); sys.exit(2)   # 2 = could not compare
url, npz = sys.argv[1], sys.argv[2]
r = np.load(npz); prompt = [int(t) for t in r["prompt"]]; tokens = [int(t) for t in r["tokens"]]; argmaxes = [int(t) for t in r["argmaxes"]]
logits = r["logits"]; P = len(prompt); n_gen = len(tokens) - P
if n_gen < 1: refuse("oracle generated no tokens (steps <= len(prompt) - 1)")
oracle_cont = tokens[P:]
def post(body, timeout=600):
    req = urllib.request.Request(url + "/completion", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try: return json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception as e: refuse(f"llama-server unreachable or errored: {e}")
c = post({"prompt": prompt, "n_predict": n_gen, "temperature": 0, "cache_prompt": False, "return_tokens": True})
llama_cont = [int(t) for t in c.get("tokens", [])]
if len(llama_cont) != n_gen: refuse(f"llama-server returned {len(llama_cont)} tokens (wanted {n_gen}); content={c.get('content')!r}")
print(f"prompt ids        {prompt}")
print(f"oracle argmax/step {argmaxes}  (steps 0..{P - 2} are forced-prompt positions)")
print(f"oracle continuation {oracle_cont}")
print(f"llama continuation  {llama_cont}  content={c['content']!r}")
cont_match = oracle_cont == llama_cont
print("continuation", "MATCH" if cont_match else f"MISMATCH at step {next(i for i in range(n_gen) if oracle_cont[i] != llama_cont[i])}")
vocab = logits.shape[1]
d = post({"prompt": prompt, "n_predict": 1, "temperature": 0, "n_probs": vocab, "cache_prompt": False})
tl = d["completion_probabilities"][0]["top_logprobs"]
if len(tl) != vocab: refuse(f"llama-server returned {len(tl)} logprobs, vocab is {vocab}: cannot compute KL over the full distribution")
lp_l = np.full(vocab, np.nan); ids = np.array([t["id"] for t in tl]); lp_l[ids] = [t["logprob"] for t in tl]
if np.isnan(lp_l).any(): refuse("llama logprob vector has holes")
mass_l = float(np.exp(lp_l).sum())            # llama-server's f32 softmax does not sum to exactly 1 over 100k+ entries
lp_l = lp_l - np.log(mass_l)                  # renormalise so KL is well defined (both KLs must come out >= 0)
z = logits[P - 1]; lp_o = z - z.max(); lp_o -= np.log(np.exp(lp_o).sum())
p_l = np.exp(lp_l); p_o = np.exp(lp_o)
kl_lo = float(np.sum(p_l * (lp_l - lp_o))); kl_ol = float(np.sum(p_o * (lp_o - lp_l)))
top_l = int(ids[0]); top_o = int(np.argmax(z)); rank_in_o = int(np.sum(z > z[top_l]))
order_o = np.argsort(-z)[:5]; order_l = ids[:5]
print(f"last prompt position: llama top-1 {top_l} (logprob {lp_l[top_l]:.4f})  oracle top-1 {top_o} (logprob {lp_o[top_o]:.4f})  -> {'MATCH' if top_l == top_o else 'MISMATCH'}")
print(f"  oracle top5 {[(int(i), round(float(lp_o[i]), 4)) for i in order_o]}")
print(f"  llama  top5 {[(int(i), round(float(lp_l[i]), 4)) for i in order_l]}")
print(f"  llama logprob mass before renormalisation {mass_l:.8f} (deficit {mass_l - 1:+.3e})")
print(f"  KL(llama||oracle) {kl_lo:.3e} nats  KL(oracle||llama) {kl_ol:.3e} nats  max|dlogprob| {float(np.max(np.abs(lp_l - lp_o))):.3e} "
      f"(over top-100 by llama: {float(np.max(np.abs(lp_l[ids[:100]] - lp_o[ids[:100]]))):.3e})  llama top-1 rank in oracle {rank_in_o}")
sys.exit(0 if cont_match and top_l == top_o else 1)
