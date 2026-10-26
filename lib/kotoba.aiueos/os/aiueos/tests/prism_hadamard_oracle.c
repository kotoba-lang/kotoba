/* Oracle for `qwen35-hadamard.kotoba` (ADR-0222 stage A item 2).
 *
 * The activation-side transform Prism's llama.cpp applies around a folded
 * Bonsai weight, as its CPU backend computes it, so that the object's
 * contract vectors are that engine's own bytes and not a re-derivation.
 *
 * Reference: PrismML-Eng/llama.cpp @ 9a9394a895b96003ca842a6041cb28ac49a108f7
 * (release prism-b10709-9a9394a).
 *   forward (before a folded mul_mat), src/llama-graph.cpp build_lora_mm:
 *     [perm_rep > 1: reshape [hd, nk, rep] -> permute(0,2,1,3) -> [hd, rep, nk]]
 *     ggml_mul(cur, signs)            signs are f32 +-1.0
 *     llama_mul_mat_hadamard(cur, rot)   -> CPU: ggml_compute_forward_fwht over rows of 1024
 *   inverse (after the token_embd lookup), build_inp_embd:
 *     llama_mul_mat_hadamard(cur, rot); ggml_mul(cur, signs)
 * The FWHT loop below is ggml/src/ggml-cpu/ops.cpp:11890
 * `ggml_compute_forward_fwht_impl<float>` with the SIMD passes removed: the
 * SIMD pass computes u + v and u + v*(-1.0f), which are the scalar pass's
 * u + v and u - v bit for bit, so the scalar loop over the whole row is the
 * same function.
 *
 *   cc -std=c11 -O2 -Wall -Wextra -Werror -o prism_hadamard_oracle prism_hadamard_oracle.c
 *   ./prism_hadamard_oracle <mode 0|1> <width> <hd> <nk> <rep> <signs-hex int32 LE> <x-hex f32 LE>
 * prints the transformed row as hex (f32 LE). */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void fwht_row(float * dst_row, const float * src_row, int64_t n) {
    const float scale = 1.0f / sqrtf((float)n);
    for (int64_t j = 0; j < n; j++) {
        dst_row[j] = src_row[j] * scale;
    }
    for (int64_t len = 1; len < n; len <<= 1) {
        for (int64_t i = 0; i < n; i += 2 * len) {
            for (int64_t j = 0; j < len; j++) {
                float u = dst_row[i + j];
                float v = dst_row[i + len + j];
                dst_row[i + j] = u + v;
                dst_row[i + len + j] = u - v;
            }
        }
    }
}

static int hexval(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }
static uint8_t * unhex(const char * s, size_t * n) {
    *n = strlen(s) / 2;
    uint8_t * b = malloc(*n);
    for (size_t i = 0; i < *n; i++) b[i] = (uint8_t)(hexval(s[2*i]) * 16 + hexval(s[2*i+1]));
    return b;
}

int main(int argc, char ** argv) {
    if (argc != 8) { fprintf(stderr, "usage: mode width hd nk rep signs-hex x-hex\n"); return 2; }
    const int mode = atoi(argv[1]);
    const int64_t width = atoll(argv[2]);
    const int64_t hd = atoll(argv[3]), nk = atoll(argv[4]), rep = atoll(argv[5]);
    size_t ns, nx;
    uint8_t * sb = unhex(argv[6], &ns);
    uint8_t * xb = unhex(argv[7], &nx);
    if ((int64_t)ns != width * 4 || (int64_t)nx != width * 4 || width % 1024 != 0) {
        fprintf(stderr, "lengths: signs %zu x %zu width %lld\n", ns, nx, (long long)width); return 2;
    }
    if (rep > 1 && hd * nk * rep != width) { fprintf(stderr, "bad permutation geometry\n"); return 2; }
    int32_t * signs = malloc(width * 4); memcpy(signs, sb, width * 4);
    float * x = malloc(width * 4); memcpy(x, xb, width * 4);
    float * y = malloc(width * 4);
    float * out = malloc(width * 4);
    for (int64_t d = 0; d < width; d++) {
        if (signs[d] != 1 && signs[d] != -1) { fprintf(stderr, "sign not +-1 at %lld\n", (long long)d); return 2; }
    }
    if (mode == 0) {
        /* permute: dst index d takes source h + hd*(nk_i + nk*rep_i) */
        for (int64_t d = 0; d < width; d++) {
            int64_t src = d;
            if (rep > 1) {
                int64_t h = d % hd, q = d / hd, rep_i = q % rep, nk_i = q / rep;
                src = h + hd * (nk_i + nk * rep_i);
            }
            y[d] = x[src] * (float)signs[d];          /* ggml_mul(cur, signs) */
        }
        for (int64_t b = 0; b < width / 1024; b++) fwht_row(out + b * 1024, y + b * 1024, 1024);
    } else {
        for (int64_t b = 0; b < width / 1024; b++) fwht_row(y + b * 1024, x + b * 1024, 1024);
        for (int64_t d = 0; d < width; d++) out[d] = y[d] * (float)signs[d];
    }
    const uint8_t * o = (const uint8_t *)out;
    for (int64_t i = 0; i < width * 4; i++) printf("%02x", o[i]);
    printf("\n");
    return 0;
}
