# Where the CAVP vectors come from

The files under `test/sha3/cavp/` are generated from NIST's Cryptographic Algorithm
Validation Program (CAVP) SHA-3 byte-oriented test vectors by
`tools/import_cavp.py`. They are data; nothing in them is executed.

| Archive | Source | Bytes | SHA-256 |
|---|---|---|---|
| `sha-3bytetestvectors.zip` (CAVS 19.0, `SHA3AllBytes1-28-16`) | https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/sha3/sha-3bytetestvectors.zip | 2,801,880 | `cd07701af2e47f5cc889d642528b4bf11f8b6eb55797c7307a96828ed8d8fc8c` |
| `shakebytetestvectors.zip` (CAVS 19.0, `SHAKE3AllBytesGT`) | https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/sha3/shakebytetestvectors.zip | 2,116,268 | `debfebc3157b3ceea002b84ca38476420389a3bf7e97dc5f53ea4689a16de4c7` |

Downloaded 2026-10-23, extracted into their own directories, and read as text only.

## What was kept (the full files are 4-5 MB each)

| File | Kept | Why |
|---|---|---|
| `SHA3_{224,256,384,512}ShortMsg` | all entries (145, 137, 105, 73) | Message lengths 0 up to one full rate block (144, 136, 104, 72 bytes), so every padding boundary, including the one-byte-room case, is covered. |
| `SHA3_*LongMsg` | first 5 | Many blocks. |
| `SHA3_*Monte` | the seed and the first 3 checkpoints (3,000 chained hashes) | Chaining catches state-carrying bugs a single vector cannot. |
| `SHAKE{128,256}ShortMsg` | all entries (337, 273) | As above, with the fixed output length of the file. |
| `SHAKE*LongMsg` | first 5 | |
| `SHAKE*VariableOut` | every 4th entry whose output length is a whole number of bytes (282, 312) | These squeeze across the rate boundary, which is what ML-KEM and ML-DSA do. |

Not used: the SHAKE Monte Carlo files, and `VariableOut` entries whose output
length is not a multiple of 8 bits (the library is byte-oriented).

## Regenerate

```sh
mkdir /tmp/rsp && unzip sha-3bytetestvectors.zip -d /tmp/rsp && unzip shakebytetestvectors.zip -d /tmp/rsp
python3 -I tools/import_cavp.py /tmp/rsp test/sha3/cavp
```

## Independent confirmation

Besides CAVP, `tools/sweep.cljk` prints the library's output for message lengths
0-420 (every padding boundary of all six functions) and for output lengths up to
1000 bytes, and `tools/oracle_sweep.py` recomputes each line with Python's
`hashlib`. Last run: 2,048 lines, 0 mismatches.
