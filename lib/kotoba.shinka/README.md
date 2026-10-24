# shinka（進化）

**`shinka` is population search: a genome is a vector of doubles, and a
generation is `ask` → evaluate → `tell`.** Zero-dependency portable `.cljc`,
byte-identical on the JVM and on ClojureScript.

The name is 進化 (evolution). It holds no domain: it does not know what a
policy, a game, or a fitness is — the caller evaluates, `shinka` only decides
who reproduces.

```clojure
(require '[shinka.evolve :as evolve])

(def s0 (evolve/init {:spec {:dim 8 :lo -1.0 :hi 1.0} :population 40 :seed 2026}))

(let [{:keys [genomes]} (evolve/ask s0)          ; 40 genomes to score
      fitnesses         (map score genomes)      ; sync, async, remote, resumed
      [s1 record]       (evolve/tell s0 fitnesses)]
  (:best-fitness record))
```

## Why it exists

Two searchers already existed in this workspace and neither could do the job:

| | what it is | why it was not enough |
|---|---|---|
| [`shugyo.policy/random-search`](https://github.com/kotoba-lang/com-nvidia-isaac-lab) | ARS-lite hill climbing over a `LinearPolicy` | perturbs **one** incumbent — no population, no recombination |
| [`sha256d.evolve`](https://github.com/kotoba-lang/sha256d) | co-scientist tournament with persisted Elo | a **closed, finite** gene pool of hand-verified variants, not a continuous space |

The missing operator is **crossover**. Mutation-only search is the right shape
when the space is one basin; it is the wrong shape when good solutions are
assembled from parts discovered independently. A behaviour policy is exactly
that — "kite away from the nearest threat" and "walk toward the pickup" are
separate genes, and a mutation-only search has to rediscover them *together*.

`shinka` is not a replacement for either. `shugyo.policy` still owns what a
policy **is** (`a = W·obs + b`, `act-batch`, `rescale-to-limits`); `shinka`
owns only how a population moves.

## The API is ask/tell, on purpose

The obvious signature is `(run spec evaluate generations)`. It was written
first and thrown away: it forces the evaluator to be synchronous, and the
evaluator this library was built for is a game episode inside a browser page —
a promise.

An API that takes a fitness *function* only works where fitness is a value. An
API that hands you genomes and accepts fitnesses back works from any host, in
any order, across a process boundary, and can be resumed from a crash by
replaying recorded fitnesses. `evolve/run` still exists for the synchronous
case and is built **on** ask/tell, so it cannot drift from the async path.

## Namespaces

| ns | what it owns |
|---|---|
| `shinka.rng` | deterministic splittable xorshift32; `[value state']`, never mutation |
| `shinka.genome` | the box spec, random genomes, `clamp`, `distance`, `diversity` |
| `shinka.variation` | `tournament`, `elites`, uniform / BLX-α crossover, gaussian `mutate` |
| `shinka.evolve` | `init` / `ask` / `tell` / `best` / `run`, and the generation record |

## Two decisions worth knowing before you tune it

**Sigma is a fraction of each gene's own width.** `:sigma 0.1` moves a gene
bounded to `[-1,1]` by ~0.2 and a gene bounded to `[-100,100]` by ~20. A sigma
in raw units would tune only the widest gene, and the test
`mutation-sigma-scales-with-gene-width` pins this.

**Collapse is measured, not assumed.** `sha256d.evolve` found that a
population collapses onto two candidates on ranking *noise* and then stops
searching — once every member carries the elites' shared genes, mutation alone
cannot recover the lost ones. `shinka` watches mean pairwise distance and, when
it falls under `:diversity-floor`, replaces the worst offspring with fresh
random immigrants and records how many. A run that never reports immigrants and
never improves is not converged; it is stuck, and the record says which.

## Determinism is the product

The same seed replays the same run — **and the JVM and ClojureScript produce
the identical stream**. `shinka.core-test` pins the first draws as literals
that were produced by running both hosts and comparing, not by copying one.

This is why the RNG is xorshift32 rather than a 64-bit generator: `js/Number`
cannot hold 64 bits, so a 64-bit LCG needs 16-bit limb emulation in
ClojureScript, and "both hosts agree" then rests on hand-rolled arithmetic.
xorshift32 uses only shifts and xor, so parity is structural.

The cost, stated plainly: period 2^32−1, not cryptographic. For population
search — where the requirement is reproducibility and decorrelation, not
unpredictability — that is enough.

## Test

Both hosts run the **same** namespace. Either alone is not the gate.

```bash
kbb -M:test                              # JVM
kbb --backend sci --classpath src:test run-tests.cljk      # ClojureScript
```

25 tests, 77 assertions, 0 failures on both (2026-08-08). Verified to actually
fail: changing one shift constant in `shinka.rng` turns 8 assertions red on
both hosts and exits non-zero.

## License

Apache License 2.0.
