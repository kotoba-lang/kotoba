# Tensor-Network Simulation of Shor's Algorithm

A small, exact, dependency-light (numpy-only) implementation that turns the
"attack Shor with tensor networks" thesis into runnable experiments. It builds
the Shor order-finding wavefunction, represents it as a Matrix Product State
(MPS), and **measures** where the bond dimension lives, how it scales with the
period, and how much truncation the period-recovery can survive.

The headline finding is reproduced exactly:

> The modular-exponentiation step entangles the control and work registers
> across a **single cut**, and the Schmidt rank at that cut equals the period
> `r`. So an MPS needs bond dimension `χ = r` there — polynomial only when `r`
> is small. For hard RSA instances `r ~ N`, the bond dimension is exponential
> in the qubit count, and there is no classical win.

```
LAW across all 153 instances:  χ(control|work) == r   -> True
```

## What it does

`python3 run_demo.py` runs four experiments and writes `bond_vs_period.png`:

1. **Single instance** `N=15, a=7`: prepares `|x>|a^x mod N>`, applies the QFT as
   real 1- and 2-qubit gates on the MPS, samples the control register, recovers
   `r=4` by continued fractions, and factors `15 → 3 × 5`.

2. **Where does the bond dimension live? (Q4)** — modexp confines entanglement to
   one cut of rank `r`; it is the **QFT** that pushes bond dimension up across
   the control register.

   | N | a | r | qubits | χ@cut (=r) | maxBond modexp | peak bond QFT |
   |---|---|---|--------|-----------|----------------|---------------|
   | 15 | 7 | 4 | 12 | 4 | 4 | 4 |
   | 21 | 2 | 6 | 15 | 6 | 6 | 63 |
   | 33 | 2 | 10 | 18 | 10 | 10 | 130 |
   | 35 | 2 | 12 | 18 | 12 | 12 | 132 |

3. **Bond dimension vs period (Q3)** — a sweep over semiprimes `{15,21,33,35,39,51,55}`
   and every valid base `a` (153 instances) confirms `χ(control|work) == r` and
   entanglement entropy `== log2(r)` *exactly*.

4. **Truncation tolerance (Q5/Q6)** — cap the bond dimension to `χ` and ask
   whether sampling still recovers the period. Fidelity rises monotonically with
   `χ`; recovery survives down to `χ ≈ r` because Shor needs only **one** clean
   sample, and breaks once `χ` is small enough to smear the phase peaks away.

   ```
   N=21 a=2 (true r=6):
    chi   fidelity  r_hat  factored?
      1    0.15494   None      False
      2    0.41301   None      False
      3    0.54465      6       True
      6    0.94401      6       True
     16    0.99999      6       True
   ```

![bond vs period](bond_vs_period.png)

## Why this is the honest picture

This maps directly onto the design note's seven points:

- **§3 bond dimension decides everything** — verified: `χ@cut = r` exactly.
- **§4 RSA-general is hard** — for cryptographic `N`, `ord_N(a)` is typically
  `Θ(N)`, so the cut needs exponential bond dimension. The code shows the
  mechanism on small `N`; the scaling argument does the rest.
- **§5 attack directions** — (A) we use the actual circuit structure rather than
  a generic 1D chain; (B) we sample only the measurement outcomes we need
  instead of materialising the full state; (C) the truncation study quantifies
  how approximation trades fidelity for the all-important phase-peak sharpness.
- **§7 the circularity** — recovering the period from the MPS still requires a
  bond dimension that already encodes `r`. No free lunch.

## Pushing toward RSA scale

`python3 run_rsa_scale.py` takes the honest scaling story all the way up. The key
upgrade is a **gate-free, statevector-free** construction: the pre-QFT state
`|x>|a^x mod N>` is written *directly* as an MPS of bond dimension exactly `r`
(a finite-state automaton along the qubit chain — see `tnshor/scalable.py`).
Cost is `O((t+m)·r²)`, polynomial in qubit count and in the period.

**Result A — breaking the 2ⁿ wall.** When `r` is small (which we *engineer*, since
finding a small-order base for a given modulus requires its factorisation), Shor
also only needs a small control register `t ≈ 2·log₂ r`. We factor large
semiprimes by simulating Shor circuits far beyond any state-vector simulator:

| bits(N) | qubits n | state-vector would need | χ | factored | time |
|--------:|---------:|------------------------:|--:|:--------:|-----:|
| 48 | 61 | 2⁶¹ amps | 6 | ✓ | 0.4 s |
| 96 | 111 | 2¹¹¹ amps | 12 | ✓ | 1.4 s |
| 128 | 141 | 2¹⁴¹ amps | 6 | ✓ | 0.9 s |
| 160 | 173 | 2¹⁷³ amps | 6 | ✓ | 0.9 s |

A **160-bit semiprime factored via a ~173-qubit Shor circuit on a laptop in under
a second** — `2¹⁷³` amplitudes is utterly impossible to store; the MPS uses
kilobytes because χ = r.

**The two RSA walls (both measured, then extrapolated).**

- **Wall 1 — period.** For a *random* base, `r = ord_N(a) ~ Θ(N)`, so the
  control|work bond `χ = r` is exponential in the qubit count. Measured:
  `log₂(r)` tracks `log₂(N)`.
- **Wall 2 — QFT.** If you do *not* know `r` is small you must use the full
  `t = 2·log₂ N` register, and the QFT's **intermediate** bond dimension explodes
  `~2^{0.6t}` even though the input (χ=r) and output are low rank. Measured
  directly: peak QFT bond 32 → 1080 as `t` goes 8 → 20 at fixed `r=6`.

![rsa scale](rsa_scale.png)

**Extrapolation to RSA-2048:** best case `χ ~ 2²⁰⁴⁷`, MPS `~2⁴¹⁰⁸` bytes — versus
`~2²⁶⁶` atoms in the observable universe. Classically impossible. Tensor networks
move the wall from *qubit count* to *period r* (plus QFT depth); RSA stays safe
because you cannot get a small-`r` handle, or shrink `t`, without already knowing
`p` and `q`.

## Layout

```
tnshor/
  mps.py          MPS engine: exact build, Schmidt spectra, gates (1q/2q/long-range
                  swap network), entropy, exact perfect sampling
  shor.py         wavefunction construction, QFT (gates: O(t^3) swap-network +
                  O(t^2) linear-nearest-neighbor), continued-fraction recovery
                  (denominator bound min(N, sqrt(Q))), factoring
  scalable.py     gate-free MPS build of |x>|a^x mod N> (bond == r, no 2^n),
                  factor_scalable(), resource models
  numtheory.py    Miller-Rabin, primes p≡1 mod d, element_of_order, CRT, and
                  make_small_order_instance() (engineered factorable small-r N)
  experiment.py   analyze(), bond_sweep(), truncation_study()
tests/
  test_core.py      MPS↔statevector roundtrip, gate/QFT equivalence, sampling, N=15
  test_scalable.py  direct build == statevector, large-bit-width engineered factor
run_demo.py       four small-scale experiments + bond_vs_period.png
run_rsa_scale.py  scalable large-N factoring, the two walls, RSA-2048 extrapolation
```

## Run

```bash
pip install numpy           # matplotlib optional, only for the figures
python3 tests/test_core.py
python3 tests/test_scalable.py
python3 run_demo.py
python3 run_rsa_scale.py
```

## Scope / honesty

- `run_demo.py` uses an exact state-vector reference (≤ ~20 qubits, `N ≲ 55`) to
  *prove the laws* and validate the MPS engine to machine precision.
- `run_rsa_scale.py` never forms a `2^n` vector: `scalable.py` builds the MPS
  directly, so the only limits are the period `r` and the control size `t`. This
  is what lets it factor 160-bit semiprimes (~173 qubits).
- The large-`N` wins are **engineered** small-order instances. This is not a
  crack: obtaining a small-order base for a *given* RSA modulus requires its
  factorisation already (the circularity from the design note's §7). For a random
  base both walls are exponential, as measured and extrapolated.
- The scalable path replaces a full gate-level modular-exponentiation compiler
  (adder networks) with an exact automaton construction of the same state — it
  cannot beat the `χ = r` lower bound, which is the whole point.
- Noisy-circuit collapse (§5 D) — add a truncating/dephasing channel between gates
  and measure where `χ` stops growing — is the natural next experiment.
