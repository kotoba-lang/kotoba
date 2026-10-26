;; A signed demo component. Its manifest carries an ed25519 signature over the
;; (id, wasm-sha256) binding; examples/signed/policy.edn registers the public key.
(module (func (export "main") (result i64) (i64.const 42)))
