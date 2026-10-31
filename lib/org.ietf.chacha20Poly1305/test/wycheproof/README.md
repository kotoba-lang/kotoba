# Wycheproof vectors (vendored, AWAI-117)

These files are copied unchanged from [C2SP/wycheproof](https://github.com/C2SP/wycheproof), `testvectors_v1/`, at commit `d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9`. Wycheproof is licensed under Apache-2.0.

`scripts/check-wycheproof-native.py` pins each file's sha256 and refuses a changed file. It runs every case through the native modules, along with mutants.

| file | sha256 |
|---|---|
| `chacha20_poly1305_test.json` | `fe61d25f90e1bde4461d00eafe61049e5f29bd999f36b766df9cda90906ad53d` |
| `xchacha20_poly1305_test.json` | `a79de072571b90eb40c3a63ce0c7f75dcb4b62323c8870228e1f61dcc61d63a9` |
