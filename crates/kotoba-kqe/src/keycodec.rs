//! Canonical order-preserving key encoding for Datomic index keys
//! (ADR-2606022150 §key-encoding).
//!
//! **This is deliberately NOT DAG-CBOR.** Block serialization uses canonical
//! DAG-CBOR (ADR-2606022150 D1); but a range index needs its *keys* to be
//! **bytewise-sortable == semantically sortable**, which DAG-CBOR does not give
//! (its major-type framing, length prefixes and CID tags do not preserve value
//! order). So the Prolly sort key is a separate, purpose-built encoding with four
//! properties:
//!
//!   1. **canonical** — exactly one byte string per value (`-0.0` is folded to
//!      `+0.0`; no alternative encodings);
//!   2. **type-tagged** — a leading tag byte segregates types into disjoint key
//!      ranges (Datomic-style), so a string is never compared against a number;
//!   3. **bytewise-sortable** — `memcmp(enc(a), enc(b))` == the value order of
//!      `a` vs `b` *within a type*, including the classic traps:
//!        - signed `i64` via **sign-bit flip** (so `-1 < 0 < 1`, not `+1 < -1`),
//!        - `f64`/`f32` via the **total-order transform** (negatives reversed +
//!          moved below positives), not raw IEEE-754 bits;
//!   4. **separator-safe** — variable-length text/bytes escape `0x00 → 0x00 0xFF`
//!      and terminate with `0x00 0x00`, so an embedded NUL can never forge a
//!      field boundary (the "why is `100` before `20`" / prefix-bleed class of
//!      bug). Fixed-width fields (CID 36 B, bool 1 B) need no terminator.
//!
//! Both the cold Prolly keys (`datom::*_key`) and the hot AVET index
//! (`arrangement`) route through here, so hot and cold order identically — the
//! single canonical encoding the derived-projection hot path requires.

use crate::datom::Value;

// Type tags. Cross-type order = tag order (type-segregated).
const T_CID: u8 = 0x01;
const T_INT: u8 = 0x02;
const T_FLOAT: u8 = 0x03;
const T_TEXT: u8 = 0x04;
const T_BOOL: u8 = 0x05;
const T_BYTES: u8 = 0x06;
const T_VECF32: u8 = 0x07;
const T_TENSOR: u8 = 0x08;
const T_ENC: u8 = 0x09;
const T_ENV: u8 = 0x0A;

const SIGN_BIT_64: u64 = 0x8000_0000_0000_0000;
const SIGN_BIT_32: u32 = 0x8000_0000;

/// Order-preserving 8-byte encoding of a signed `i64`: flip the sign bit so the
/// unsigned big-endian byte order matches signed value order across negatives.
#[inline]
fn int_key(n: i64) -> [u8; 8] {
    ((n as u64) ^ SIGN_BIT_64).to_be_bytes()
}

/// Total-order transform of an IEEE-754 `f64`: if negative (sign set) flip all
/// bits, else flip just the sign bit. Yields `memcmp` order == numeric order
/// across the whole line (NaN sorts to an end). `-0.0` is folded to `+0.0`.
#[inline]
fn float64_key(f: f64) -> [u8; 8] {
    let f = if f == 0.0 { 0.0 } else { f };
    let bits = f.to_bits();
    let x = if bits & SIGN_BIT_64 != 0 {
        !bits
    } else {
        bits | SIGN_BIT_64
    };
    x.to_be_bytes()
}

#[inline]
fn float32_key(f: f32) -> [u8; 4] {
    let f = if f == 0.0 { 0.0 } else { f };
    let bits = f.to_bits();
    let x = if bits & SIGN_BIT_32 != 0 {
        !bits
    } else {
        bits | SIGN_BIT_32
    };
    x.to_be_bytes()
}

/// Append a separator-safe encoding of arbitrary bytes: `0x00 → 0x00 0xFF`,
/// terminated by `0x00 0x00`. Preserves bytewise order and prefix-scan safety
/// (the `0x00 0x00` terminator sorts below any escaped `0x00 0xFF` continuation,
/// so `"a"` orders before `"a\0b"` and before `"ab"`).
pub fn push_ordered_bytes(buf: &mut Vec<u8>, s: &[u8]) {
    for &b in s {
        buf.push(b);
        if b == 0 {
            buf.push(0xFF);
        }
    }
    buf.push(0);
    buf.push(0);
}

/// Append a separator-safe encoding of a UTF-8 string (no leading type tag —
/// used for the attribute segment of composite keys, which is a bare keyword).
pub fn push_ordered_str(buf: &mut Vec<u8>, s: &str) {
    push_ordered_bytes(buf, s.as_bytes());
}

/// Append the canonical, order-preserving, type-tagged encoding of `value`.
pub fn push_value(buf: &mut Vec<u8>, value: &Value) {
    match value {
        Value::Cid(cid) => {
            buf.push(T_CID);
            buf.extend_from_slice(&cid.0); // fixed 36 B
        }
        Value::Integer(n) => {
            buf.push(T_INT);
            buf.extend_from_slice(&int_key(*n));
        }
        Value::Float(f) => {
            buf.push(T_FLOAT);
            buf.extend_from_slice(&float64_key(*f));
        }
        Value::Text(s) => {
            buf.push(T_TEXT);
            push_ordered_str(buf, s);
        }
        Value::Bool(b) => {
            buf.push(T_BOOL);
            buf.push(u8::from(*b)); // fixed 1 B
        }
        Value::Bytes(bytes) => {
            buf.push(T_BYTES);
            push_ordered_bytes(buf, bytes);
        }
        Value::VectorF32(vec) => {
            buf.push(T_VECF32);
            // Vectors are embeddings, not range-ordered; encode the float-key
            // bytes through the escape so an embedded 0x00 can't forge the
            // terminator. Order across vectors is stable/canonical, not semantic.
            let mut raw = Vec::with_capacity(vec.len() * 4);
            for f in vec {
                raw.extend_from_slice(&float32_key(*f));
            }
            push_ordered_bytes(buf, &raw);
        }
        Value::TensorCid { cid, .. } => {
            buf.push(T_TENSOR);
            buf.extend_from_slice(&cid.0); // fixed 36 B
        }
        Value::Encrypted { ct_cid, .. } => {
            buf.push(T_ENC);
            buf.extend_from_slice(&ct_cid.0); // fixed 36 B
        }
        Value::Enveloped { ct_cid, .. } => {
            buf.push(T_ENV);
            buf.extend_from_slice(&ct_cid.0); // fixed 36 B
        }
    }
}

/// Standalone canonical key for a single value (hot AVET BTreeMap inner key).
pub fn value_key(value: &Value) -> Vec<u8> {
    let mut buf = Vec::new();
    push_value(&mut buf, value);
    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    fn enc(v: &Value) -> Vec<u8> {
        value_key(v)
    }
    // Assert encoded byte order matches the intended semantic order.
    fn assert_lt(a: Value, b: Value) {
        assert!(
            enc(&a) < enc(&b),
            "enc({a:?}) should sort before enc({b:?})\n  {:?}\n  {:?}",
            enc(&a),
            enc(&b)
        );
    }

    #[test]
    fn integers_sort_numerically_including_negatives() {
        // The classic "100 before 20" and negative traps.
        assert_lt(Value::Integer(20), Value::Integer(100));
        assert_lt(Value::Integer(-1), Value::Integer(0));
        assert_lt(Value::Integer(0), Value::Integer(1));
        assert_lt(Value::Integer(-100), Value::Integer(-20));
        assert_lt(Value::Integer(i64::MIN), Value::Integer(i64::MAX));
        assert_lt(Value::Integer(-1), Value::Integer(1));
    }

    #[test]
    fn floats_sort_numerically_including_negatives_and_zero() {
        assert_lt(Value::Float(-1.0), Value::Float(0.0));
        assert_lt(Value::Float(0.0), Value::Float(1.0));
        assert_lt(Value::Float(-100.0), Value::Float(-20.0));
        assert_lt(Value::Float(20.0), Value::Float(100.0));
        assert_lt(Value::Float(f64::NEG_INFINITY), Value::Float(0.0));
        assert_lt(Value::Float(0.0), Value::Float(f64::INFINITY));
        // -0.0 and +0.0 are folded to one canonical encoding.
        assert_eq!(enc(&Value::Float(-0.0)), enc(&Value::Float(0.0)));
    }

    #[test]
    fn integer_encoding_is_monotone_over_a_full_sweep() {
        // Generalises the pairwise checks: an ascending value sequence must encode
        // to an ascending key sequence end-to-end (no inversion hides between the
        // spot-checks), spanning the i64 extremes.
        let ascending = [
            i64::MIN,
            i64::MIN + 1,
            -(1i64 << 40),
            -1_000_000,
            -1,
            0,
            1,
            1_000_000,
            1i64 << 40,
            i64::MAX - 1,
            i64::MAX,
        ];
        for w in ascending.windows(2) {
            assert!(
                enc(&Value::Integer(w[0])) < enc(&Value::Integer(w[1])),
                "integer key encoding must be monotone: {} then {}",
                w[0],
                w[1]
            );
        }
    }

    #[test]
    fn float_encoding_is_monotone_including_subnormals_and_extremes() {
        let subnormal = f64::from_bits(1); // smallest positive subnormal (~5e-324)
        let ascending = [
            f64::NEG_INFINITY,
            f64::MIN, // most-negative finite (~-1.8e308)
            -1.0,
            -f64::MIN_POSITIVE, // smallest-magnitude negative normal
            -subnormal,
            0.0,
            subnormal,
            f64::MIN_POSITIVE,
            1.0,
            f64::MAX,
            f64::INFINITY,
        ];
        for w in ascending.windows(2) {
            assert!(
                enc(&Value::Float(w[0])) < enc(&Value::Float(w[1])),
                "float key encoding must be monotone: {} then {}",
                w[0],
                w[1]
            );
        }
    }

    #[test]
    fn nan_encodes_deterministically_and_to_an_end() {
        // A NaN in an index key must not panic and must encode deterministically.
        let k1 = enc(&Value::Float(f64::NAN));
        let k2 = enc(&Value::Float(f64::NAN));
        assert_eq!(k1, k2, "NaN must encode deterministically");
        assert_ne!(k1, enc(&Value::Float(0.0)), "NaN must not collide with 0.0");
        // The doc promises NaN sorts to an end; the std positive NaN (sign clear)
        // lands above +INFINITY rather than wedging between finite values.
        assert!(
            k1 > enc(&Value::Float(f64::INFINITY)),
            "positive NaN must sort to the high end, not among finite values"
        );
    }

    #[test]
    fn text_is_separator_safe_against_embedded_nul() {
        // "a" < "a\0b" < "ab": the terminator must not be forgeable by a NUL.
        assert_lt(Value::Text("a".into()), Value::Text("a\u{0}b".into()));
        assert_lt(Value::Text("a\u{0}b".into()), Value::Text("ab".into()));
        // Distinct strings never collide.
        assert_ne!(
            enc(&Value::Text("a\u{0}".into())),
            enc(&Value::Text("a".into()))
        );
    }

    #[test]
    fn bytes_with_embedded_nul_are_unambiguous() {
        assert_ne!(
            enc(&Value::Bytes(vec![0x00])),
            enc(&Value::Bytes(vec![0x00, 0x00]))
        );
        assert_lt(Value::Bytes(vec![1]), Value::Bytes(vec![1, 0]));
    }

    #[test]
    fn types_are_segregated_into_disjoint_ranges() {
        // A huge integer never sorts among strings; bool never collides with float.
        assert_lt(Value::Integer(i64::MAX), Value::Float(f64::NEG_INFINITY));
        assert_lt(Value::Float(f64::INFINITY), Value::Text(String::new()));
        // Previously everything-but-{cid,text,int,enc} collapsed to "?" — now distinct.
        assert_ne!(enc(&Value::Bool(true)), enc(&Value::Float(1.0)));
        assert_ne!(enc(&Value::Bool(false)), enc(&Value::Bytes(vec![])));
    }

    #[test]
    fn encrypted_and_enveloped_keys_are_distinct_but_ct_stable() {
        let ct = kotoba_core::KotobaCid::from_bytes(b"ct");
        let policy = kotoba_core::KotobaCid::from_bytes(b"policy");
        let manifest = kotoba_core::KotobaCid::from_bytes(b"manifest");
        let encrypted = enc(&Value::Encrypted {
            ct_cid: ct.clone(),
            policy_cid: policy,
        });
        let enveloped = enc(&Value::Enveloped {
            ct_cid: ct,
            manifest_cid: manifest,
        });
        assert_ne!(encrypted, enveloped);
        assert_eq!(encrypted.len(), 1 + 36);
        assert_eq!(enveloped.len(), 1 + 36);
    }

    #[test]
    fn encoding_is_canonical_and_deterministic() {
        let v = Value::Text("紡ぎ".into());
        assert_eq!(enc(&v), enc(&v.clone()));
        let n = Value::Integer(42);
        assert_eq!(enc(&n), enc(&Value::Integer(42)));
    }
}
