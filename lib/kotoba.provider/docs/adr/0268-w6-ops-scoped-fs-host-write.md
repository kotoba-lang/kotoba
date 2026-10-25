# ADR 0268: T8.3 scoped-fs guest host_write_edn (wire 19 write slice)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0255 scoped-fs W4; ADR 0267 host_read_edn first slice

## Context

ADR 0267 shipped scoped-fs `host_read_edn` only. Write remained deferred.
`fs/transact` (wire **19**) is the single capability for both read and write;
write needs a guest encode + cap-forward surface matching read.

## Decision

1. Extend **scoped-fs-w4-host-edn**:
   - `fs_req_write_rec_kv_edn` / `fs_reply_written_rec_kv_edn` pure codecs
   - `host_write_edn` = encode write request then `(typed-cap-call 19 …)`
   - `main` pure → **-2512** (read+write+written+fail-closed)
2. edn-codec: inject mode `:fs-written`; `scoped-fs-w4-host-write-edn` /
   deny-closed.
3. Does **not** flip `:wasm-aot :implemented` — host store remains authority.

## Evidence

- Package sha `b36dda82…`; browser-host main → -2512; write inject tests

## Related

- Closes scoped-fs guest host write residual from ADR 0267
