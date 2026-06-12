//! Browser Web Worker entry — wasm-bindgen exports for WebGPU inference

#[cfg(target_arch = "wasm32")]
mod worker;

#[cfg(target_arch = "wasm32")]
pub use worker::*;
