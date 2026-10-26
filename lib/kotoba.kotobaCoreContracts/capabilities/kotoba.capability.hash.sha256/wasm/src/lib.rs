//! Reference wasm core for actor:host field `sha256_hex`.
//!
//! ABI (kototama.tender / actor-host.js):
//!   (ptr, len, out_ptr, out_cap) -> bytes_written | -1
//!
//! Reads `len` bytes at linear-memory offset `ptr`, writes 64 lowercase
//! hex ASCII bytes at `out_ptr` when `out_cap >= 64`.

#![no_std]
#![allow(clippy::missing_safety_doc)]

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
    0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
    0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
    0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
];

struct Sha256 {
    h: [u32; 8],
    /// Message length so far, in bits.
    bit_len: u64,
    block: [u8; 64],
    block_len: usize,
}

impl Sha256 {
    fn new() -> Self {
        Self {
            h: [
                0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
                0x1f83d9ab, 0x5be0cd19,
            ],
            bit_len: 0,
            block: [0; 64],
            block_len: 0,
        }
    }

    fn update(&mut self, data: *const u8, mut len: usize) {
        self.bit_len = self.bit_len.wrapping_add((len as u64).wrapping_mul(8));
        let mut off = 0usize;
        while len > 0 {
            let space = 64 - self.block_len;
            let take = if len < space { len } else { space };
            unsafe {
                core::ptr::copy_nonoverlapping(
                    data.add(off),
                    self.block.as_mut_ptr().add(self.block_len),
                    take,
                );
            }
            self.block_len += take;
            off += take;
            len -= take;
            if self.block_len == 64 {
                let block = self.block;
                self.compress(&block);
                self.block_len = 0;
            }
        }
    }

    fn finalize(mut self) -> [u8; 32] {
        let bit_len = self.bit_len;
        // Append 0x80 then zeros to reach 56 mod 64, then 8-byte BE bit length.
        let one = [0x80u8];
        self.update(one.as_ptr(), 1);
        let zero = [0u8; 1];
        while self.block_len != 56 {
            self.update(zero.as_ptr(), 1);
            // update adds to bit_len — restore after padding dance
        }
        self.bit_len = bit_len; // restore true message bit length
        let mut len_be = [0u8; 8];
        let mut i = 0;
        while i < 8 {
            len_be[7 - i] = ((bit_len >> (8 * i)) & 0xff) as u8;
            i += 1;
        }
        // length field must not be counted into bit_len again
        let saved = self.bit_len;
        self.update(len_be.as_ptr(), 8);
        self.bit_len = saved;

        let mut out = [0u8; 32];
        let mut i = 0;
        while i < 8 {
            let word = self.h[i];
            out[i * 4] = (word >> 24) as u8;
            out[i * 4 + 1] = (word >> 16) as u8;
            out[i * 4 + 2] = (word >> 8) as u8;
            out[i * 4 + 3] = word as u8;
            i += 1;
        }
        out
    }

    fn compress(&mut self, block: &[u8; 64]) {
        let mut w = [0u32; 64];
        let mut i = 0;
        while i < 16 {
            let j = i * 4;
            w[i] = ((block[j] as u32) << 24)
                | ((block[j + 1] as u32) << 16)
                | ((block[j + 2] as u32) << 8)
                | (block[j + 3] as u32);
            i += 1;
        }
        i = 16;
        while i < 64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
            i += 1;
        }
        let mut a = self.h[0];
        let mut b = self.h[1];
        let mut c = self.h[2];
        let mut d = self.h[3];
        let mut e = self.h[4];
        let mut f = self.h[5];
        let mut g = self.h[6];
        let mut h = self.h[7];
        i = 0;
        while i < 64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = h
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
            i += 1;
        }
        self.h[0] = self.h[0].wrapping_add(a);
        self.h[1] = self.h[1].wrapping_add(b);
        self.h[2] = self.h[2].wrapping_add(c);
        self.h[3] = self.h[3].wrapping_add(d);
        self.h[4] = self.h[4].wrapping_add(e);
        self.h[5] = self.h[5].wrapping_add(f);
        self.h[6] = self.h[6].wrapping_add(g);
        self.h[7] = self.h[7].wrapping_add(h);
    }
}

fn hex_encode(digest: &[u8; 32], out: &mut [u8; 64]) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut i = 0;
    while i < 32 {
        out[i * 2] = HEX[(digest[i] >> 4) as usize];
        out[i * 2 + 1] = HEX[(digest[i] & 0x0f) as usize];
        i += 1;
    }
}

/// Digest bytes at `data`/`len` into 64 lowercase hex chars at `out`.
unsafe fn digest_hex(data: *const u8, len: usize, out: *mut u8) {
    let mut hasher = Sha256::new();
    hasher.update(data, len);
    let digest = hasher.finalize();
    let mut hex = [0u8; 64];
    hex_encode(&digest, &mut hex);
    core::ptr::copy_nonoverlapping(hex.as_ptr(), out, 64);
}

/// `(ptr, len, out_ptr, out_cap) -> 64 | -1`
#[no_mangle]
pub extern "C" fn sha256_hex(ptr: i32, len: i32, out_ptr: i32, out_cap: i32) -> i32 {
    if ptr < 0 || len < 0 || out_ptr < 0 || out_cap < 64 {
        return -1;
    }
    unsafe {
        digest_hex(ptr as usize as *const u8, len as usize, out_ptr as usize as *mut u8);
    }
    64
}
