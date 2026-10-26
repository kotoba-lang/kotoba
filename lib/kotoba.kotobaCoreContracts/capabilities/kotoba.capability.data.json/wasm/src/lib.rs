//! Reference wasm core for actor:host fields `json_encode` + `json_extract_field`.
//!
//! json_encode(pairs_ptr, pairs_len, out_ptr, out_cap) -> bytes_written | -1
//!   Input: flat key\\tvalue pairs, LF-separated. Flat string→string only.
//!
//! json_extract_field(json_ptr, json_len, field_ptr, field_len, out_ptr, out_cap)
//!   -> bytes_written | -1
//!   Bounded scan for `"field":"value"` (optional whitespace after colon).

#![no_std]

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

const MAX_PAIRS: usize = 64;
const MAX_KEY: usize = 256;
const MAX_VAL: usize = 1024;

struct Pair {
    k_off: usize,
    k_len: usize,
    v_off: usize,
    v_len: usize,
}

fn parse_pairs(input: &[u8], pairs: &mut [Pair; MAX_PAIRS]) -> i32 {
    let mut n = 0usize;
    let mut i = 0usize;
    let len = input.len();
    while i < len {
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

fn json_escape_write(out: &mut [u8], pos: &mut usize, src: &[u8]) -> bool {
    let mut i = 0;
    while i < src.len() {
        let c = src[i];
        let esc: &[u8] = match c {
            b'"' => b"\\\"",
            b'\\' => b"\\\\",
            b'\n' => b"\\n",
            b'\r' => b"\\r",
            b'\t' => b"\\t",
            _ => {
                if *pos >= out.len() {
                    return false;
                }
                out[*pos] = c;
                *pos += 1;
                i += 1;
                continue;
            }
        };
        if *pos + esc.len() > out.len() {
            return false;
        }
        let mut e = 0;
        while e < esc.len() {
            out[*pos] = esc[e];
            *pos += 1;
            e += 1;
        }
        i += 1;
    }
    true
}

fn write_json_string(out: &mut [u8], pos: &mut usize, src: &[u8]) -> bool {
    if *pos >= out.len() {
        return false;
    }
    out[*pos] = b'"';
    *pos += 1;
    if !json_escape_write(out, pos, src) {
        return false;
    }
    if *pos >= out.len() {
        return false;
    }
    out[*pos] = b'"';
    *pos += 1;
    true
}

fn encode_object(input: &[u8], pairs: &[Pair], n: usize, out: &mut [u8]) -> i32 {
    let mut pos = 0usize;
    if pos >= out.len() {
        return -1;
    }
    out[pos] = b'{';
    pos += 1;
    let mut i = 0;
    while i < n {
        if i > 0 {
            if pos >= out.len() {
                return -1;
            }
            out[pos] = b',';
            pos += 1;
        }
        let p = &pairs[i];
        let k = &input[p.k_off..p.k_off + p.k_len];
        let v = &input[p.v_off..p.v_off + p.v_len];
        if !write_json_string(out, &mut pos, k) {
            return -1;
        }
        if pos >= out.len() {
            return -1;
        }
        out[pos] = b':';
        pos += 1;
        if !write_json_string(out, &mut pos, v) {
            return -1;
        }
        i += 1;
    }
    if pos >= out.len() {
        return -1;
    }
    out[pos] = b'}';
    pos += 1;
    pos as i32
}

#[no_mangle]
pub extern "C" fn json_encode(pairs_ptr: i32, pairs_len: i32, out_ptr: i32, out_cap: i32) -> i32 {
    if pairs_ptr < 0 || pairs_len < 0 || out_ptr < 0 || out_cap < 0 {
        return -1;
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
    encode_object(input, &pairs, n as usize, out)
}

fn find_string_field(json: &[u8], field: &[u8], out: &mut [u8]) -> i32 {
    // Scan for "field"
    let mut i = 0usize;
    while i + field.len() + 2 <= json.len() {
        if json[i] == b'"' {
            let mut ok = true;
            let mut j = 0;
            while j < field.len() {
                if json[i + 1 + j] != field[j] {
                    ok = false;
                    break;
                }
                j += 1;
            }
            if ok && json[i + 1 + field.len()] == b'"' {
                // skip whitespace then colon
                let mut k = i + 2 + field.len();
                while k < json.len() && (json[k] == b' ' || json[k] == b'\t' || json[k] == b'\n' || json[k] == b'\r')
                {
                    k += 1;
                }
                if k >= json.len() || json[k] != b':' {
                    i += 1;
                    continue;
                }
                k += 1;
                while k < json.len() && (json[k] == b' ' || json[k] == b'\t' || json[k] == b'\n' || json[k] == b'\r')
                {
                    k += 1;
                }
                if k >= json.len() || json[k] != b'"' {
                    i += 1;
                    continue;
                }
                k += 1; // start of value
                let mut pos = 0usize;
                while k < json.len() {
                    let c = json[k];
                    if c == b'"' {
                        return pos as i32;
                    }
                    if c == b'\\' {
                        k += 1;
                        if k >= json.len() {
                            return -1;
                        }
                        let e = match json[k] {
                            b'"' => b'"',
                            b'\\' => b'\\',
                            b'n' => b'\n',
                            b'r' => b'\r',
                            b't' => b'\t',
                            b'/' => b'/',
                            _ => return -1,
                        };
                        if pos >= out.len() {
                            return -1;
                        }
                        out[pos] = e;
                        pos += 1;
                        k += 1;
                        continue;
                    }
                    if pos >= out.len() {
                        return -1;
                    }
                    out[pos] = c;
                    pos += 1;
                    k += 1;
                }
                return -1;
            }
        }
        i += 1;
    }
    -1
}

#[no_mangle]
pub extern "C" fn json_extract_field(
    json_ptr: i32,
    json_len: i32,
    field_ptr: i32,
    field_len: i32,
    out_ptr: i32,
    out_cap: i32,
) -> i32 {
    if json_ptr < 0
        || json_len < 0
        || field_ptr < 0
        || field_len < 0
        || out_ptr < 0
        || out_cap < 0
    {
        return -1;
    }
    let json =
        unsafe { core::slice::from_raw_parts(json_ptr as usize as *const u8, json_len as usize) };
    let field =
        unsafe { core::slice::from_raw_parts(field_ptr as usize as *const u8, field_len as usize) };
    let out =
        unsafe { core::slice::from_raw_parts_mut(out_ptr as usize as *mut u8, out_cap as usize) };
    find_string_field(json, field, out)
}
