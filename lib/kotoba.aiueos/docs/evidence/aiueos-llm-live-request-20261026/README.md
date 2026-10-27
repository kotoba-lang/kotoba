# Live Goal to native `llm-v1` request candidate

The user-v3 syscall handler now prepares a bounded `llm-v1` request from the
OS-copied Goal after consuming the current local-model choice. The model key,
empty system, prompt, selected-model key, header and result capacity occupy
disjoint subregions of one kernel-owned scratch page. The handler calls the
existing request-shape validator before the diagnostic one-token model.
This is a candidate connection of the live CPL3 request to the kit's byte
shape; it does not implement the kit's typed user value, wire-11 dispatch,
general model provider, human approval, or Itonami agent loop.

The signed Mac Amu F2 image `5635e728fc49e8d0c7ca3685b5c22ac72bd2d85fae3799a0af45204b8e5f0755`
reproduced the original 31-module user-v3 ELF/kernel/EFI. With the four new
LLM request modules, the same F2 reproduced the user ELF, then refused the
35-module kernel with E7104. A selfhosted diagnostic Amu F2
`531b465f8cbb328e05496123bfe65cbaa959d8f50d0764d65841435e2532c155`
reported the required cumulative text extent: 1,070,137 bytes against the
AIUEOS image's fixed 1,048,576-byte code/data boundary, an excess of 21,561
bytes before the final image was emitted. Its source changed only the E7104
detail in `seed/85-aiueos-project.kotoba`; its Mac F1 and F2 compiler
containers were byte identical. See [capacity-receipt.json](capacity-receipt.json)
for exact source and artifact digests.

Increasing the generic project image allocation did not remove E7104. The
AIUEOS image layout fixes data at the 1 MiB file boundary and preserves the
user-v3 virtual pages. Enlarging this cap alone would let code overlap data.
The next implementation must give native provider/validation code a separate
admitted region or version the kernel/data/user layout together. No QEMU boot
or scorecard point is claimed for this unbuilt candidate; the last passing
user-v3 QEMU proof belongs to the 31-module image.

## Text lower bound

The same diagnostic F2 compiled four temporary, **nonfunctional** source
variants in an isolated worktree. Replacing only the bridge body still needed
1,063,673 bytes; replacing only the request-shape body needed 1,065,065;
replacing the header and UTF-8 bodies needed 1,062,425. Replacing all four
new modules with minimal functions still needed 1,050,889 bytes, which is
2,313 bytes beyond the fixed boundary. These variants have no validation
semantics and were never booted. The source-bound [size-lower-bound.json](size-lower-bound.json)
records each failed compile. This rules out a behavior-preserving rewrite of
those four function bodies as the sole solution; the layout or component
placement must change.
