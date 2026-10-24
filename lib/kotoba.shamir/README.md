# shamir

Shamir secret sharing over GF(2^8) (AES polynomial), byte-wise, in pure
kotoba. Used by [nafuda](../nafuda) to back up a root key to guardians.

```clojure
(require '[shamir.core :as s])
(def shares (s/split secret 3 5 random-bytes))  ; any 3 of 5
(s/combine (take 3 shares))                    ; => secret
```

`combine` cannot detect a wrong share; keep a hash of the secret beside the
shares (nafuda does).

```sh
npm test
```
