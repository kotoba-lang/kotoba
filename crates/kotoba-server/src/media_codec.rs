//! Real media codec wired into the WASM runtime via [`kotoba_runtime::WasmExecutor::with_codec`]
//! (ADR-2606272200 §3, utsushi R1).
//!
//! The codec logic lives in the dependency-light `kotoba-media` crate (pure-Rust, no
//! wasmtime); this module is the thin adapter that lifts it into the runtime's
//! type-erased [`CodecFn`] and maps [`MediaOp`] → `kotoba_media::{decode,encode}`.
//! It is injected into `KotobaState.executor` so that policy-granted `.kotoba` guests
//! calling `media.decode` / `media.encode` transform real bytes (R1: MJPEG decode).

use std::sync::Arc;

use kotoba_runtime::host::{CodecFn, MediaOp};

/// Build the production [`CodecFn`] backed by `kotoba-media`. Decode dispatches to the
/// real pure-Rust decoders (currently MJPEG); encode is reported as unsupported in R1.
pub fn codec_fn() -> CodecFn {
    Arc::new(|op, codec, bytes| match op {
        MediaOp::Decode => kotoba_media::decode(codec, bytes),
        MediaOp::Encode => kotoba_media::encode(codec, bytes),
    })
}

#[cfg(test)]
mod tests {
    use kotoba_runtime::host::MediaOp;

    #[test]
    fn codec_fn_dispatches_and_propagates_errors() {
        // The real MJPEG decode round-trip is covered by `kotoba-media`'s own tests;
        // here we only assert the adapter wires decode/encode and surfaces errors.
        let f = super::codec_fn();
        assert!(f(MediaOp::Decode, "mjpeg", &[1, 2, 3]).is_err()); // not a JPEG → decode error
        assert!(f(MediaOp::Encode, "mjpeg", &[1, 2, 3]).is_err()); // encode unsupported in R1
        assert!(f(MediaOp::Decode, "av1", &[]).is_err()); // unsupported codec
    }
}
