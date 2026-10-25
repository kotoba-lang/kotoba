# paillier

`kotoba-lang/paillier` is the JVM cryptographic primitive for exact additive
homomorphic integer computation. It owns Paillier keys, randomized ciphertexts,
homomorphic addition and public-scalar multiplication, EDN-safe wire forms, and
bounded encrypted matrix/vector evaluation.

The library is deliberately separate from [`kotoba-lang/num`](https://github.com/kotoba-lang/num):
`num` owns portable numerical arrays and execution backends, while Paillier owns
key material, ciphertext validity, modular arithmetic, and the security boundary.
Inference systems are consumers, not the owner of the primitive.

## Use

```clojure
(require '[paillier.core :as phe])

(def keys (phe/generate-keypair))          ; 2048-bit production minimum
(def pk (:public-key keys))
(def encrypted-x (mapv #(phe/encrypt pk %) [3 -2]))
(def result (phe/encrypted-matvec pk [[2 5]] encrypted-x [7]
                                     {:input-bound 3}))

(mapv #(phe/decrypt (:private-key keys) %) (:ciphertexts result))
;;=> [3]                                   ; 2*3 + 5*(-2) + 7
```

`:input-bound` is mandatory and public. Before evaluation, the library computes
the worst-case signed output bound for every row and rejects any operation that
could wrap the Paillier plaintext modulus. Results are rerandomized by default.

## Security boundary

- Production key generation enforces a 2048-bit minimum. Smaller keys require
  the explicit `:allow-insecure-test-key? true` escape.
- The public wire form contains the modulus and fingerprint only. The private
  factors, lambda, and mu never have a serializer.
- Ciphertexts are validated for key identity, range, and membership in the
  invertible residue group before use.
- Paillier is malleable additive PHE, not FHE and not CCA-secure. It cannot
  multiply two encrypted values or evaluate nonlinear Transformer layers.
- JVM `BigInteger` is not claimed constant-time. Authenticate protocol envelopes,
  do not expose a decryption oracle, and do not treat this library as a hardened
  side-channel boundary.

The versioned wire scheme is `:paillier-phe-v1`.

## Verify

```sh
kbb -M:test
kbb -M:lint
```

The tests cover signed and randomized encryption, exact homomorphic operations,
encrypted matrix/vector parity, public-only serialization, malformed ciphertext
rejection, dimension mismatch, missing bounds, and modular-wrap rejection.

Licensed under Apache-2.0.

