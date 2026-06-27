//! Media capability + effect plumbing (R1, ADR-2606272200 §3).
//!
//! `media-decode` / `media-encode` are the capability-gated native codec
//! boundary: each is a deny-by-default [`CapClass`] + a declared effect. These
//! tests assert, from both sides, that
//!   - a `media-*` call needs its grant (deny-by-default),
//!   - the decode/encode split is real (one does not confer the other),
//!   - per-codec (instance-level) grants are honoured (S4),
//!   - effect soundness (T2) rejects an under-declared `:effects` row,
//!   - a matching declaration + grant compiles to real wasm.

use kotoba_clj::policy::CapClass;
use kotoba_clj::{compile_safe_clj, CljError, Policy};

fn is_wasm(b: &[u8]) -> bool {
    b.starts_with(b"\0asm")
}

fn assert_policy_denied(res: Result<Vec<u8>, CljError>) {
    match res {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected CljError::Policy denial, got {other:?}"),
    }
}

const DECODE: &str = r#"(defn run [pkt] (media-decode "h264" pkt))"#;
const ENCODE: &str = r#"(defn run [frame] (media-encode "h265" frame))"#;

#[test]
fn media_decode_denied_without_grant() {
    assert_policy_denied(compile_safe_clj(DECODE, &Policy::deny_all()));
}

#[test]
fn media_decode_allowed_with_grant() {
    let policy = Policy::deny_all().grant_media_decode(["h264"]);
    let wasm = compile_safe_clj(DECODE, &policy).expect("granted media-decode must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn decode_grant_does_not_confer_encode() {
    // The decode/encode split is the point: decode authority must not encode.
    let policy = Policy::deny_all().grant_media_decode(["h264"]);
    assert_policy_denied(compile_safe_clj(ENCODE, &policy));
}

#[test]
fn encode_grant_does_not_confer_decode() {
    let policy = Policy::deny_all().grant_media_encode(["h265"]);
    assert_policy_denied(compile_safe_clj(DECODE, &policy));
}

#[test]
fn per_codec_grant_is_instance_scoped() {
    // S4: granting "av1" does not authorize decoding "h264".
    let policy = Policy::deny_all().grant_media_decode(["av1"]);
    assert_policy_denied(compile_safe_clj(DECODE, &policy));
}

#[test]
fn effect_soundness_rejects_under_declared_media() {
    // Declares pure but decodes → T2 under-declaration. Fires regardless of the
    // (here granted) capability — the effect gate runs first.
    let src = r#"(defn run {:effects #{}} [pkt] (media-decode "h264" pkt))"#;
    let policy = Policy::deny_all().grant_media_decode(["h264"]);
    match compile_safe_clj(src, &policy) {
        Err(CljError::Effect(_)) => {}
        other => panic!("expected CljError::Effect under-declaration, got {other:?}"),
    }
}

#[test]
fn declared_and_granted_media_compiles() {
    let src = r#"(defn run {:effects #{:media-decode}} [pkt] (media-decode "h264" pkt))"#;
    let policy = Policy::deny_all().grant_media_decode(["h264"]);
    let wasm = compile_safe_clj(src, &policy).expect("declared+used+granted must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn capclass_decode_and_encode_are_distinct() {
    assert_ne!(CapClass::MediaDecode, CapClass::MediaEncode);
}
