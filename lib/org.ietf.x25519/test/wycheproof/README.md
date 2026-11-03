# Wycheproof vectors (vendored, AWAI-117)

These files are copied unchanged from [C2SP/wycheproof](https://github.com/C2SP/wycheproof), `testvectors_v1/`, at commit `d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9`. Wycheproof is licensed under Apache-2.0.

`scripts/check-wycheproof-native.py` pins each file's sha256 and refuses a changed file. It runs every case through the native modules, along with mutants.

| file | sha256 |
|---|---|
| `x25519_test.json` | `35c3f5231cf25cc640b524d403461deee9e49441d5d915a3a25b2c8ff5adbe7d` |
