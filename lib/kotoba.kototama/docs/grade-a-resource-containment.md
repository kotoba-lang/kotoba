# Grade A resource containment

Grade A gap T-04 is enforced by two independent layers:

- `open-session` caps Wasm instructions (fuel), linear-memory growth, HTTP and
  LLM call counts, and cumulative storage input/output bytes.
- `run-main-bounded` adds a positive wall-clock deadline, cancellation of the
  worker, and non-queuing concurrency admission through a shared fair
  semaphore.

The bounded runner rejects saturation and invalid deadlines before parsing or
executing the guest. On expiry it cancels the Java Future with interruption;
the instruction listener remains the CPU-loop backstop when guest code does
not enter an interruptible host operation.

Verification:

```sh
kbb -M:test -n kototama.tender-test
```

The production fleet entry point uses `run-report-bounded` with
`:profile :production`; an unbounded execution helper is no longer its default.

T-04 remains `in-progress`: qualification still needs malicious multi-guest
stress tests plus proof that every injected provider obeys cancellation and
output-size limits.
