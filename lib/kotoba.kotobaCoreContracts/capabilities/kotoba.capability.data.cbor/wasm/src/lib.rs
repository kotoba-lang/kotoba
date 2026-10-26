//! Reference wasm core for actor:host field `cbor_encode`.
//!
//! ABI: (pairs_ptr, pairs_len, out_ptr, out_cap) -> bytes_written | -1
//! Input: flat key\\tvalue pairs, LF-separated (UTF-8). Flat string→string only
//! (dotted-path nesting is host/JVM extension; not required for ABI packaging).

#![no_std]

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

const MAX_PAIRS: usize = 64;
const MAX_KEY: usize = 256;
const MAX_VAL: usize = 1024;
const MAX_OUT: usize = 8192;

struct Pair {
    k_off: usize,
    k_len: usize,
    v_off: usize,
    v_len: usize,
}

fn write_head(out: &mut [u8], pos: &mut usize, major: u8, n: usize) -> bool {
    if n < 24 {
        if *pos >= out.len() {
            return false;
        }
        out[*pos] = (major << 5) | (n as u8);
        *pos += 1;
        true
    } else if n < 256 {
        if *pos + 2 > out.len() {
            return false;
        }
        out[*pos] = (major << 5) | 24;
        out[*pos + 1] = n as u8;
        *pos += 2;
        true
    } else if n < 65536 {
        if *pos + 3 > out.len() {
            return false;
        }
        out[*pos] = (major << 5) | 25;
        out[*pos + 1] = ((n >> 8) & 0xff) as u8;
        out[*pos + 2] = (n & 0xff) as u8;
        *pos += 3;
        true
    } else {
        false
    }
}

fn write_text(out: &mut [u8], pos: &mut usize, src: &[u8]) -> bool {
    if !write_head(out, pos, 3, src.len()) {
        return false;
    }
    if *pos + src.len() > out.len() {
        return false;
    }
    unsafe {
        core::ptr::copy_nonoverlapping(src.as_ptr(), out.as_mut_ptr().add(*pos), src.len());
    }
    *pos += src.len();
    true
}

/// Parse flat pairs into offsets; returns pair count or -1 on error.
fn parse_pairs(input: &[u8], pairs: &mut [Pair; MAX_PAIRS]) -> i32 {
    let mut n = 0usize;
    let mut i = 0usize;
    let len = input.len();
    while i < len {
        // skip empty lines
        if input[i] == b'\n' {
            i += 1;
            continue;
        }
        let line_start = i;
        while i < len && input[i] != b'\n' {
            i += 1;
        }
        let line_end = i;
        if i < len && input[i] == b'\n' {
            i += 1;
        }
        // find tab
        let mut tab = None;
        let mut j = line_start;
        while j < line_end {
            if input[j] == b'\t' {
                tab = Some(j);
                break;
            }
            j += 1;
        }
        let tab = match tab {
            Some(t) => t,
            None => return -1,
        };
        let k_off = line_start;
        let k_len = tab - line_start;
        let v_off = tab + 1;
        let v_len = line_end - v_off;
        if k_len == 0 || k_len > MAX_KEY || v_len > MAX_VAL {
            return -1;
        }
        // reject dotted keys in reference wasm (host may accept)
        let mut d = 0;
        while d < k_len {
            if input[k_off + d] == b'.' {
                return -1;
            }
            d += 1;
        }
        if n >= MAX_PAIRS {
            return -1;
        }
        pairs[n] = Pair {
            k_off,
            k_len,
            v_off,
            v_len,
        };
        n += 1;
    }
    n as i32
}

fn encode_map(input: &[u8], pairs: &[Pair], n: usize, out: &mut [u8]) -> i32 {
    let mut pos = 0usize;
    if !write_head(out, &mut pos, 5, n) {
        return -1;
    }
    let mut i = 0;
    while i < n {
        let p = &pairs[i];
        let k = &input[p.k_off..p.k_off + p.k_len];
        let v = &input[p.v_off..p.v_off + p.v_len];
        if !write_text(out, &mut pos, k) {
            return -1;
        }
        if !write_text(out, &mut pos, v) {
            return -1;
        }
        i += 1;
    }
    pos as i32
}

#[no_mangle]
pub extern "C" fn cbor_encode(pairs_ptr: i32, pairs_len: i32, out_ptr: i32, out_cap: i32) -> i32 {
    if pairs_ptr < 0 || pairs_len < 0 || out_ptr < 0 || out_cap < 0 {
        return -1;
    }
    if (out_cap as usize) > MAX_OUT {
        // allow large caps; we only need the slice length
    }
    let input = unsafe {
        core::slice::from_raw_parts(pairs_ptr as usize as *const u8, pairs_len as usize)
    };
    let out = unsafe {
        core::slice::from_raw_parts_mut(out_ptr as usize as *mut u8, out_cap as usize)
    };
    let mut pairs: [Pair; MAX_PAIRS] = unsafe { core::mem::zeroed() };
    let n = parse_pairs(input, &mut pairs);
    if n < 0 {
        return -1;
    }
    let n = n as usize;
    let written = encode_map(input, &pairs, n, out);
    if written < 0 || (written as usize) > (out_cap as usize) {
        return -1;
    }
    written
}
