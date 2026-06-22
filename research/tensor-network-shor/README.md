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

## Layout

```
tnshor/
  mps.py          MPS engine: exact build, Schmidt spectra, gates (1q/2q/long-range
                  swap network), entropy, exact perfect sampling
  shor.py         wavefunction construction, QFT (gates + reference matrix),
                  continued-fraction period recovery, factoring
  experiment.py   analyze(), bond_sweep(), truncation_study()
tests/test_core.py  MPS↔statevector roundtrip, gate/QFT equivalence to machine
                    precision, sampling-distribution check, full Shor on N=15
run_demo.py       the four experiments + figure
```

## Run

```bash
pip install numpy           # matplotlib optional, only for the figure
python3 tests/test_core.py  # all green
python3 run_demo.py
```

## Scope / honesty

- Exact statevector reference caps practical sizes at ~20 qubits (`N ≲ 55`),
  which is plenty to *measure the laws*. The MPS engine itself is not capped —
  the point is precisely that the required bond dimension, not the code, is the
  wall.
- We build the post-modexp wavefunction directly and run the QFT on it as a gate
  sequence (this is what lets us watch the bond dimension evolve). A full
  gate-level modular-exponentiation compiler (adder networks) is the natural
  extension and would let the simulation never touch the `2^n` vector — but it
  cannot beat the `χ = r` lower bound established here.
- Noisy-circuit collapse (§5 D) — simulating decoherence to test whether a noisy
  quantum device retains a Shor advantage — is a clean follow-up: add a
  truncating/dephasing channel between gates and measure where `χ` stops growing.
