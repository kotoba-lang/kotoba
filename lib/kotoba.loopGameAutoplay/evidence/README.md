# evidence

One real run, 2026-08-08. Kept in git because a README that says "it works"
and a receipt that says what actually happened are different claims.

| file | what it is |
|---|---|
| `run-champion.edn` | the trained genome, with the search seed, evaluation seeds and episode length it was found under |
| `run-history.edn` | all 8 generations: best / mean / std / min / diversity / immigrants |
| `qualify-receipt.edn` | `hinshitsu` evidence + gate from the booted iPhone 17 (iOS 18.7, Safari 26.5) |
| `qualify-screenshot.png` | ~12 s in, the frame that proves the game was rendering |
| `qualify-final-frame.png` | 00:03 remaining — HP 102/140, Lv 3, 2393 killed, NIGHT RAGE |

The 318 MB video itself is not committed (see the workspace's large-binary
policy); the receipt records its size, duration and frame count.

## Read the history honestly

```
gen  best     mean    std    min    diversity  immigrants
0    1206.0   621.0   354.3  272.6  0.419      0
7    1208.0   824.8   352.8  237.4  0.297      0
```

The **best was already 1206 at generation 0** — one of sixteen random linear
policies already survived the full fifteen minutes on these two seeds. Eight
generations moved it to 1208. What moved was the *mean* (621 → 994.9 at gen 4
→ 824.8), and not monotonically.

So: the harness works end to end. **This task does not demonstrate that the
search beats random sampling**, and the numbers above are the reason to say so
rather than to imply otherwise. The collapse guard never fired either
(diversity never approached the 0.06 floor) — it is unit-tested, not exercised
here.
