# kotoba-lang/ioplan

**T5 library — turning a list of I/O requests into the list the device actually wants.**

Four transformations, and which of them apply is a property of the **device**
rather than a preference:

1. **align** to whole device blocks — a device cannot transfer half a block;
2. **merge** touching requests, up to the maximum transfer;
3. **order** them — or, on a device with no seek cost, deliberately do not;
4. **batch** to the queue depth.

## The third one is where the wrong intuition lives

An elevator sort is *the* canonical I/O optimization, and on an NVMe device it
is **harmful**: it spends CPU and latency reducing a cost that is zero, and it
destroys the submission order the caller chose.

```clojure
(io/plan mach :disk scattered)  ;=> :order [0 40960 61440 81920]  :reordered? true
(io/plan mach :nvme scattered)  ;=> :order [40960 4096 81920 0 61440]  :reordered? false
```

Same requests, opposite treatment, and nothing in the call site decides it —
`machine.core/reorderable?` reads it off the device's `:seek-cost`. A plan
cannot apply a rotating-disk optimization to flash by inheritance.

The same distinction runs through **merging**. On a seeking device the whole
list is sorted first, so any two requests that touch find each other, and the
merge gap is one block wide because skipping a hole costs a seek while reading
through it costs only bandwidth. On a zero-seek device that sort would be a
reordering by the back door — so only submission-order neighbours combine, and
the gap is zero.

The bug this shape invites, found by the tests: a merge predicate that only
checks the *upper* bound (`offset ≤ prev-end + gap`) is harmless on a sorted
list and silently absorbs a request that lies *before* `prev` on the unsorted
one. Both bounds are checked.

## Amplification is made visible, not added

```clojure
(io/plan mach :nvme [{:id :a :op :read :offset 100 :bytes 100}])
;=> :bytes-requested 100  :bytes-transferred 4096  :read-amplification 40.96
```

The device was always going to move a whole block. A plan reporting 100 is
lying about the bandwidth it will consume — and a factor of 40 is worth seeing
before optimizing anything else.

Writes get the same treatment: a 512-byte write to a 4 KiB-block device is a
read-modify-write, `:write-amplification 8.0`. A read-only workload reports no
write amplification at all rather than a meaningless `1.0`.

## `explain`

```
device nvme (nvme, block 4096B, queue 4, seek-cost none)
5 requests -> 5 commands (0 merged) in 2 batches
moved 20480B for 20480B asked (amplification 1.0)
not reordered: this device charges nothing for seeking, so submission order stands
```

The last line exists because the useful thing to record is often what the
planner **declined** to do.

## Details worth stating

- **C-SCAN, not SCAN.** One ascending sweep. A bidirectional sweep starves
  whichever end the head is walking away from, and the starved request is
  usually the interactive one.
- **Merging never crosses an op boundary.** A read absorbed into a write would
  return bytes nobody read.
- **Merging never exceeds `:max-transfer-bytes`.** A command the device cannot
  express is not a plan. 64 contiguous blocks against a 128 KiB maximum come
  out as two commands, not one impossible one.
- **`:reordered?` is computed from submission rank**, not from offset lists —
  once merging changes the command count, comparing offsets cannot answer the
  question.
- **`:model` travels with the plan** and names what it does not model:
  controller queueing, garbage collection, thermal throttling, on-device cache,
  rotational latency, cross-channel parallelism.

## Test

```sh
kbb -M:test
```

Pure `.cljc`. Depends only on
[`kotoba-lang/machine`](https://github.com/kotoba-lang/machine). See
ADR-2608030200 in the superproject.
