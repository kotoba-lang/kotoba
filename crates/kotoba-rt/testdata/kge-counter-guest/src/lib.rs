//! Real `kotoba:kge` `game` component (test fixture for kotoba-rt's
//! `WasmComponentSim`). **`no_std`** so the component imports NO `wasi:*` —
//! nondeterminism (wall-clock/random/sockets) is uninstantiable, not merely
//! unused. Deterministic counter sim: `acc[player] += (buttons + axes) * (tick+1)`.

#![no_std]
extern crate alloc;

#[allow(warnings)]
mod bindings;

use alloc::vec;
use alloc::vec::Vec;
use bindings::exports::kotoba::kge::kge::{Guest, Input};

#[global_allocator]
static ALLOC: dlmalloc::GlobalDlmalloc = dlmalloc::GlobalDlmalloc;

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

// Single-threaded wasm guest state.
static mut SEED: u64 = 0;
static mut ACC: Vec<i64> = Vec::new();

/// Fixed-point axis quantization WITHOUT std float methods (no `round`/libm):
/// clamp [-1,1], scale 1000, round-half-away-from-zero via ±0.5 truncation.
/// NaN/Inf → 0 so a malformed float can never reach state.
fn quantize_axis(v: f32) -> i64 {
    if !v.is_finite() {
        return 0;
    }
    let c = if v > 1.0 {
        1.0
    } else if v < -1.0 {
        -1.0
    } else {
        v
    };
    let scaled = c * 1000.0;
    (if scaled >= 0.0 { scaled + 0.5 } else { scaled - 0.5 }) as i64
}

struct Component;

impl Guest for Component {
    fn init(seed: u64, config: Vec<u8>) -> Result<(), alloc::string::String> {
        let n = if config.len() >= 4 {
            u32::from_le_bytes([config[0], config[1], config[2], config[3]]) as usize
        } else {
            2
        };
        unsafe {
            SEED = seed;
            ACC = vec![seed as i64; n];
        }
        Ok(())
    }

    fn step(tick: u64, inputs: Vec<Input>) -> Result<(), alloc::string::String> {
        let weight = (tick as i64).wrapping_add(1);
        unsafe {
            for inp in &inputs {
                let idx = inp.player as usize;
                if idx >= ACC.len() {
                    ACC.resize(idx + 1, SEED as i64); // dynamic capacity, seeded
                }
                let mut axis_sum: i64 = 0;
                for a in &inp.axes {
                    axis_sum = axis_sum.wrapping_add(quantize_axis(*a));
                }
                let delta = (inp.buttons as i64).wrapping_add(axis_sum).wrapping_mul(weight);
                ACC[idx] = ACC[idx].wrapping_add(delta);
            }
        }
        Ok(())
    }

    fn snapshot() -> Result<Vec<u8>, alloc::string::String> {
        unsafe {
            let mut out = Vec::with_capacity(8 + ACC.len() * 8);
            out.extend_from_slice(&SEED.to_le_bytes());
            for v in &ACC {
                out.extend_from_slice(&v.to_le_bytes());
            }
            Ok(out)
        }
    }

    fn restore(blob: Vec<u8>) -> Result<(), alloc::string::String> {
        if blob.len() < 8 {
            return Err(alloc::string::String::from("short snapshot"));
        }
        unsafe {
            SEED = u64::from_le_bytes(blob[0..8].try_into().unwrap());
            let body = &blob[8..];
            let n = body.len() / 8;
            ACC = (0..n)
                .map(|i| i64::from_le_bytes(body[i * 8..i * 8 + 8].try_into().unwrap()))
                .collect();
        }
        Ok(())
    }

    fn state_hash() -> Result<Vec<u8>, alloc::string::String> {
        Self::snapshot()
    }
}

bindings::export!(Component with_types_in bindings);
