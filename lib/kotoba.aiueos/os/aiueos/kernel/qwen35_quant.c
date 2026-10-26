/* SPDX-License-Identifier: Apache-2.0
 *
 * The dequantization equations and codebook values in this file are adapted
 * from ggml-org/llama.cpp commit
 * 3173a56471c1753650cd806694145ffd6dcace67 (MIT license).  The surrounding
 * dispatcher is AIUEOS-specific and deliberately has no libc dependency.
 */
#include "qwen35_quant.h"
#include "qwen35_runtime.h"

#include <stdint.h>

#define QK8_0 32
#define QK_K 256
#define K_SCALE_SIZE 12
#define IQ3S_N_SCALE (QK_K / 64)
#define IQ1S_DELTA 0.125f

typedef uint16_t ggml_half;

typedef struct { ggml_half d; int8_t qs[QK8_0]; } block_q8_0;
typedef struct {
  uint8_t scales[QK_K / 16]; uint8_t qs[QK_K / 4];
  union { struct { ggml_half d, dmin; }; uint32_t dm; };
} block_q2_K;
typedef struct {
  uint8_t hmask[QK_K / 8]; uint8_t qs[QK_K / 4];
  uint8_t scales[12]; ggml_half d;
} block_q3_K;
typedef struct {
  union { struct { ggml_half d, dmin; }; uint32_t dm; };
  uint8_t scales[K_SCALE_SIZE]; uint8_t qs[QK_K / 2];
} block_q4_K;
typedef struct {
  union { struct { ggml_half d, dmin; }; uint32_t dm; };
  uint8_t scales[K_SCALE_SIZE]; uint8_t qh[QK_K / 8];
  uint8_t qs[QK_K / 2];
} block_q5_K;
typedef struct {
  uint8_t ql[QK_K / 2]; uint8_t qh[QK_K / 4];
  int8_t scales[QK_K / 16]; ggml_half d;
} block_q6_K;
typedef struct { ggml_half d; uint16_t qs[QK_K / 8]; } block_iq2_xxs;
typedef struct {
  ggml_half d; uint16_t qs[QK_K / 8]; uint8_t scales[QK_K / 32];
} block_iq2_xs;
typedef struct {
  ggml_half d; uint8_t qs[QK_K / 4]; uint8_t qh[QK_K / 32];
  uint8_t scales[QK_K / 32];
} block_iq2_s;
typedef struct { ggml_half d; uint8_t qs[3 * QK_K / 8]; } block_iq3_xxs;
typedef struct {
  ggml_half d; uint8_t qs[QK_K / 4]; uint8_t qh[QK_K / 32];
  uint8_t signs[QK_K / 8]; uint8_t scales[IQ3S_N_SCALE];
} block_iq3_s;
typedef struct {
  ggml_half d; uint8_t qs[QK_K / 8]; uint16_t qh[QK_K / 32];
} block_iq1_s;
typedef struct {
  uint8_t qs[QK_K / 8]; uint8_t qh[QK_K / 16];
  uint8_t scales[QK_K / 32];
} block_iq1_m;
typedef union { ggml_half f16; uint16_t u16; } iq1m_scale_t;
typedef struct {
  ggml_half d; uint16_t scales_h; uint8_t scales_l[QK_K / 64];
  uint8_t qs[QK_K / 2];
} block_iq4_xs;

typedef char block_q8_0_size[(sizeof(block_q8_0) == 34) ? 1 : -1];
typedef char block_q2_K_size[(sizeof(block_q2_K) == 84) ? 1 : -1];
typedef char block_q3_K_size[(sizeof(block_q3_K) == 110) ? 1 : -1];
typedef char block_q4_K_size[(sizeof(block_q4_K) == 144) ? 1 : -1];
typedef char block_q5_K_size[(sizeof(block_q5_K) == 176) ? 1 : -1];
typedef char block_q6_K_size[(sizeof(block_q6_K) == 210) ? 1 : -1];
typedef char block_iq2_xxs_size[(sizeof(block_iq2_xxs) == 66) ? 1 : -1];
typedef char block_iq2_xs_size[(sizeof(block_iq2_xs) == 74) ? 1 : -1];
typedef char block_iq2_s_size[(sizeof(block_iq2_s) == 82) ? 1 : -1];
typedef char block_iq3_xxs_size[(sizeof(block_iq3_xxs) == 98) ? 1 : -1];
typedef char block_iq3_s_size[(sizeof(block_iq3_s) == 110) ? 1 : -1];
typedef char block_iq1_s_size[(sizeof(block_iq1_s) == 50) ? 1 : -1];
typedef char block_iq1_m_size[(sizeof(block_iq1_m) == 56) ? 1 : -1];
typedef char block_iq4_xs_size[(sizeof(block_iq4_xs) == 136) ? 1 : -1];

static void byte_copy(void * destination, const void * source, uint64_t bytes) {
  uint8_t * out = (uint8_t *)destination;
  const uint8_t * in = (const uint8_t *)source;
  for (uint64_t index = 0; index < bytes; index++) out[index] = in[index];
}

static float fp16_to_f32(ggml_half value) {
  uint32_t sign = ((uint32_t)value & 0x8000U) << 16;
  uint32_t exponent = ((uint32_t)value >> 10) & 0x1fU;
  uint32_t mantissa = (uint32_t)value & 0x3ffU;
  uint32_t bits;
  if (exponent == 0) {
    if (mantissa == 0) {
      bits = sign;
    } else {
      int32_t unbiased = -14;
      while ((mantissa & 0x400U) == 0) {
        mantissa <<= 1;
        unbiased--;
      }
      mantissa &= 0x3ffU;
      bits = sign | ((uint32_t)(unbiased + 127) << 23) | (mantissa << 13);
    }
  } else if (exponent == 31) {
    bits = sign | 0x7f800000U | (mantissa << 13);
  } else {
    bits = sign | ((exponent + 112U) << 23) | (mantissa << 13);
  }
  union { uint32_t u; float f; } converted = {bits};
  return converted.f;
}

#include "qwen35_quant_tables.inc"

static void dequantize_row_q8_0(const block_q8_0 * x, float * y, int64_t k) {
    static const int qk = QK8_0;


    const int nb = k / qk;

    for (int i = 0; i < nb; i++) {
        const float d = fp16_to_f32(x[i].d);

        for (int j = 0; j < qk; ++j) {
            y[i*qk + j] = x[i].qs[j]*d;
        }
    }
}
static inline void get_scale_min_k4(int j, const uint8_t * q, uint8_t * d, uint8_t * m) {
    if (j < 4) {
        *d = q[j] & 63; *m = q[j + 4] & 63;
    } else {
        *d = (q[j+4] & 0xF) | ((q[j-4] >> 6) << 4);
        *m = (q[j+4] >>  4) | ((q[j-0] >> 6) << 4);
    }
}
static void dequantize_row_q2_K(const block_q2_K * x, float * y, int64_t k) {
    const int nb = k / QK_K;

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);
        const float min = fp16_to_f32(x[i].dmin);

        const uint8_t * q = x[i].qs;

        int is = 0;
        float dl, ml;
        for (int n = 0; n < QK_K; n += 128) {
            int shift = 0;
            for (int j = 0; j < 4; ++j) {

                uint8_t sc = x[i].scales[is++];
                dl = d * (sc & 0xF); ml = min * (sc >> 4);
                for (int l = 0; l < 16; ++l) *y++ = dl * ((int8_t)((q[l] >> shift) & 3)) - ml;

                sc = x[i].scales[is++];
                dl = d * (sc & 0xF); ml = min * (sc >> 4);
                for (int l = 0; l < 16; ++l) *y++ = dl * ((int8_t)((q[l+16] >> shift) & 3)) - ml;

                shift += 2;
            }
            q += 32;
        }
    }
}
static void dequantize_row_q3_K(const block_q3_K * x, float * y, int64_t k) {
    const int nb = k / QK_K;

    const uint32_t kmask1 = 0x03030303;
    const uint32_t kmask2 = 0x0f0f0f0f;

    uint32_t aux[4];
    const int8_t * scales = (const int8_t*)aux;

    for (int i = 0; i < nb; i++) {

        const float d_all = fp16_to_f32(x[i].d);

        const uint8_t * q = x[i].qs;
        const uint8_t * hm = x[i].hmask;
        uint8_t m = 1;

        byte_copy(aux, x[i].scales, 12);
        uint32_t tmp = aux[2];
        aux[2] = ((aux[0] >> 4) & kmask2) | (((tmp >> 4) & kmask1) << 4);
        aux[3] = ((aux[1] >> 4) & kmask2) | (((tmp >> 6) & kmask1) << 4);
        aux[0] = (aux[0] & kmask2) | (((tmp >> 0) & kmask1) << 4);
        aux[1] = (aux[1] & kmask2) | (((tmp >> 2) & kmask1) << 4);

        int is = 0;
        float dl;
        for (int n = 0; n < QK_K; n += 128) {
            int shift = 0;
            for (int j = 0; j < 4; ++j) {

                dl = d_all * (scales[is++] - 32);
                for (int l = 0; l < 16; ++l) {
                    *y++ = dl * ((int8_t)((q[l+ 0] >> shift) & 3) - ((hm[l+ 0] & m) ? 0 : 4));
                }

                dl = d_all * (scales[is++] - 32);
                for (int l = 0; l < 16; ++l) {
                    *y++ = dl * ((int8_t)((q[l+16] >> shift) & 3) - ((hm[l+16] & m) ? 0 : 4));
                }

                shift += 2;
                m <<= 1;
            }
            q += 32;
        }

    }
}
static void dequantize_row_q4_K(const block_q4_K * x, float * y, int64_t k) {
    const int nb = k / QK_K;

    for (int i = 0; i < nb; i++) {
        const uint8_t * q = x[i].qs;

        const float d   = fp16_to_f32(x[i].d);
        const float min = fp16_to_f32(x[i].dmin);

        int is = 0;
        uint8_t sc, m;
        for (int j = 0; j < QK_K; j += 64) {
            get_scale_min_k4(is + 0, x[i].scales, &sc, &m);
            const float d1 = d * sc; const float m1 = min * m;
            get_scale_min_k4(is + 1, x[i].scales, &sc, &m);
            const float d2 = d * sc; const float m2 = min * m;
            for (int l = 0; l < 32; ++l) *y++ = d1 * (q[l] & 0xF) - m1;
            for (int l = 0; l < 32; ++l) *y++ = d2 * (q[l]  >> 4) - m2;
            q += 32; is += 2;
        }
    }
}
static void dequantize_row_q5_K(const block_q5_K * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    for (int i = 0; i < nb; i++) {
        const uint8_t * ql = x[i].qs;
        const uint8_t * qh = x[i].qh;

        const float d = fp16_to_f32(x[i].d);
        const float min = fp16_to_f32(x[i].dmin);

        int is = 0;
        uint8_t sc, m;
        uint8_t u1 = 1, u2 = 2;
        for (int j = 0; j < QK_K; j += 64) {
            get_scale_min_k4(is + 0, x[i].scales, &sc, &m);
            const float d1 = d * sc; const float m1 = min * m;
            get_scale_min_k4(is + 1, x[i].scales, &sc, &m);
            const float d2 = d * sc; const float m2 = min * m;
            for (int l = 0; l < 32; ++l) *y++ = d1 * ((ql[l] & 0xF) + (qh[l] & u1 ? 16 : 0)) - m1;
            for (int l = 0; l < 32; ++l) *y++ = d2 * ((ql[l]  >> 4) + (qh[l] & u2 ? 16 : 0)) - m2;
            ql += 32; is += 2;
            u1 <<= 2; u2 <<= 2;
        }
    }
}
static void dequantize_row_q6_K(const block_q6_K * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    for (int i = 0; i < nb; i++) {
        const float d = fp16_to_f32(x[i].d);

        const uint8_t * ql = x[i].ql;
        const uint8_t * qh = x[i].qh;
        const int8_t  * sc = x[i].scales;

        for (int n = 0; n < QK_K; n += 128) {
            for (int l = 0; l < 32; ++l) {
                int is = l/16;
                const int8_t q1 = (int8_t)((ql[l +  0] & 0xF) | (((qh[l] >> 0) & 3) << 4)) - 32;
                const int8_t q2 = (int8_t)((ql[l + 32] & 0xF) | (((qh[l] >> 2) & 3) << 4)) - 32;
                const int8_t q3 = (int8_t)((ql[l +  0]  >> 4) | (((qh[l] >> 4) & 3) << 4)) - 32;
                const int8_t q4 = (int8_t)((ql[l + 32]  >> 4) | (((qh[l] >> 6) & 3) << 4)) - 32;
                y[l +  0] = d * sc[is + 0] * q1;
                y[l + 32] = d * sc[is + 2] * q2;
                y[l + 64] = d * sc[is + 4] * q3;
                y[l + 96] = d * sc[is + 6] * q4;
            }
            y  += 128;
            ql += 64;
            qh += 32;
            sc += 8;
        }
    }
}
static void dequantize_row_iq2_xxs(const block_iq2_xxs * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    uint32_t aux32[2];
    const uint8_t * aux8 = (const uint8_t *)aux32;

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);

        for (int ib32 = 0; ib32 < QK_K/32; ++ib32) {
            byte_copy(aux32, x[i].qs + 4*ib32, 2*sizeof(uint32_t));
            const float db = d * (0.5f + (aux32[1] >> 28)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t * grid = (const uint8_t *)(iq2xxs_grid + aux8[l]);
                const uint8_t  signs = ksigns_iq2xs[(aux32[1] >> 7*l) & 127];
                for (int j = 0; j < 8; ++j) {
                    y[j] = db * grid[j] * (signs & kmask_iq2xs[j] ? -1.f : 1.f);
                }
                y += 8;
            }
        }
    }
}

// ====================== 2.3125 bpw (de)-quantization

static void dequantize_row_iq2_xs(const block_iq2_xs * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    float db[2];

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);

        for (int ib32 = 0; ib32 < QK_K/32; ++ib32) {
            db[0] = d * (0.5f + (x[i].scales[ib32] & 0xf)) * 0.25f;
            db[1] = d * (0.5f + (x[i].scales[ib32] >>  4)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t * grid = (const uint8_t *)(iq2xs_grid + (x[i].qs[4*ib32 + l] & 511));
                const uint8_t  signs = ksigns_iq2xs[x[i].qs[4*ib32 + l] >> 9];
                for (int j = 0; j < 8; ++j) {
                    y[j] = db[l/2] * grid[j] * (signs & kmask_iq2xs[j] ? -1.f : 1.f);
                }
                y += 8;
            }
        }
    }
}

// ====================== 2.5625 bpw (de)-quantization

static void dequantize_row_iq2_s(const block_iq2_s * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    float db[2];

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);
        const uint8_t * qs = x[i].qs;
        const uint8_t * qh = x[i].qh;
        const uint8_t * signs = qs + QK_K/8;

        for (int ib32 = 0; ib32 < QK_K/32; ++ib32) {
            db[0] = d * (0.5f + (x[i].scales[ib32] & 0xf)) * 0.25f;
            db[1] = d * (0.5f + (x[i].scales[ib32] >>  4)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const float dl = db[l/2];
                const uint8_t * grid = (const uint8_t *)(iq2s_grid + (qs[l] | (qh[ib32] << (8-2*l) & 0x300)));
                for (int j = 0; j < 8; ++j) {
                    y[j] = dl * grid[j] * (signs[l] & kmask_iq2xs[j] ? -1.f : 1.f);
                }
                y += 8;
            }
            qs += 4;
            signs += 4;
        }
    }
}

// ====================== 3.0625 bpw (de)-quantization

static void dequantize_row_iq3_xxs(const block_iq3_xxs * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    uint32_t aux32;

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);
        const uint8_t * qs = x[i].qs;
        const uint8_t * scales_and_signs = qs + QK_K/4;

        for (int ib32 = 0; ib32 < QK_K/32; ++ib32) {
            byte_copy(&aux32, scales_and_signs + 4*ib32, sizeof(uint32_t));
            const float db = d * (0.5f + (aux32 >> 28)) * 0.5f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t  signs = ksigns_iq2xs[(aux32 >> 7*l) & 127];
                const uint8_t * grid1 = (const uint8_t *)(iq3xxs_grid + qs[2*l+0]);
                const uint8_t * grid2 = (const uint8_t *)(iq3xxs_grid + qs[2*l+1]);
                for (int j = 0; j < 4; ++j) {
                    y[j+0] = db * grid1[j] * (signs & kmask_iq2xs[j+0] ? -1.f : 1.f);
                    y[j+4] = db * grid2[j] * (signs & kmask_iq2xs[j+4] ? -1.f : 1.f);
                }
                y += 8;
            }
            qs += 8;
        }
    }
}

// ====================== 3.3125 bpw (de)-quantization

static void dequantize_row_iq3_s(const block_iq3_s * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);
        const uint8_t * qs = x[i].qs;
        const uint8_t * qh = x[i].qh;
        const uint8_t * signs = x[i].signs;

        for (int ib32 = 0; ib32 < QK_K/32; ib32 += 2) {
            const float db1 = d * (1 + 2*(x[i].scales[ib32/2] & 0xf));
            const float db2 = d * (1 + 2*(x[i].scales[ib32/2] >>  4));
            for (int l = 0; l < 4; ++l) {
                const uint8_t * grid1 = (const uint8_t *)(iq3s_grid + (qs[2*l+0] | ((qh[0] << (8-2*l)) & 256)));
                const uint8_t * grid2 = (const uint8_t *)(iq3s_grid + (qs[2*l+1] | ((qh[0] << (7-2*l)) & 256)));
                for (int j = 0; j < 4; ++j) {
                    y[j+0] = db1 * grid1[j] * (signs[l] & kmask_iq2xs[j+0] ? -1.f : 1.f);
                    y[j+4] = db1 * grid2[j] * (signs[l] & kmask_iq2xs[j+4] ? -1.f : 1.f);
                }
                y += 8;
            }
            qs += 8;
            signs += 4;
            for (int l = 0; l < 4; ++l) {
                const uint8_t * grid1 = (const uint8_t *)(iq3s_grid + (qs[2*l+0] | ((qh[1] << (8-2*l)) & 256)));
                const uint8_t * grid2 = (const uint8_t *)(iq3s_grid + (qs[2*l+1] | ((qh[1] << (7-2*l)) & 256)));
                for (int j = 0; j < 4; ++j) {
                    y[j+0] = db2 * grid1[j] * (signs[l] & kmask_iq2xs[j+0] ? -1.f : 1.f);
                    y[j+4] = db2 * grid2[j] * (signs[l] & kmask_iq2xs[j+4] ? -1.f : 1.f);
                }
                y += 8;
            }
            qh += 2;
            qs += 8;
            signs += 4;
        }
    }
}

// ====================== 1.5625 bpw (de)-quantization

static void dequantize_row_iq1_s(const block_iq1_s * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    for (int i = 0; i < nb; i++) {

        const float d = fp16_to_f32(x[i].d);
        const uint8_t  * qs = x[i].qs;
        const uint16_t * qh = x[i].qh;

        for (int ib = 0; ib < QK_K/32; ++ib) {
            const float dl = d * (2*((qh[ib] >> 12) & 7) + 1);
            const float delta = qh[ib] & 0x8000 ? -IQ1S_DELTA : IQ1S_DELTA;
            for (int l = 0; l < 4; ++l) {
                const int8_t * grid = (const int8_t *)(iq1s_grid + (qs[l] | (((qh[ib] >> 3*l) & 7) << 8)));
                for (int j = 0; j < 8; ++j) {
                    y[j] = dl * (grid[j] + delta);
                }
                y += 8;
            }
            qs += 4;
        }
    }
}

static void dequantize_row_iq1_m(const block_iq1_m * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    float delta[4];
    uint16_t idx[4];

    iq1m_scale_t scale;

    for (int i = 0; i < nb; i++) {

        const uint16_t * sc = (const uint16_t *)x[i].scales;
        scale.u16 = (sc[0] >> 12) | ((sc[1] >> 8) & 0x00f0) | ((sc[2] >> 4) & 0x0f00) | (sc[3] & 0xf000);
        const float d = fp16_to_f32(scale.f16);

        const uint8_t * qs = x[i].qs;
        const uint8_t * qh = x[i].qh;

        for (int ib = 0; ib < QK_K/32; ++ib) {
            const float dl1 = d * (2*((sc[ib/2] >> (6*(ib%2)+0)) & 0x7) + 1);
            const float dl2 = d * (2*((sc[ib/2] >> (6*(ib%2)+3)) & 0x7) + 1);

            idx[0] = qs[0] | ((qh[0] << 8) & 0x700);
            idx[1] = qs[1] | ((qh[0] << 4) & 0x700);
            idx[2] = qs[2] | ((qh[1] << 8) & 0x700);
            idx[3] = qs[3] | ((qh[1] << 4) & 0x700);
            delta[0] = qh[0] & 0x08 ? -IQ1S_DELTA : IQ1S_DELTA;
            delta[1] = qh[0] & 0x80 ? -IQ1S_DELTA : IQ1S_DELTA;
            delta[2] = qh[1] & 0x08 ? -IQ1S_DELTA : IQ1S_DELTA;
            delta[3] = qh[1] & 0x80 ? -IQ1S_DELTA : IQ1S_DELTA;
            for (int l = 0; l < 2; ++l) {
                const int8_t * grid = (const int8_t *)(iq1s_grid + idx[l]);
                for (int j = 0; j < 8; ++j) {
                    y[j] = dl1 * (grid[j] + delta[l]);
                }
                y += 8;
            }
            for (int l = 2; l < 4; ++l) {
                const int8_t * grid = (const int8_t *)(iq1s_grid + idx[l]);
                for (int j = 0; j < 8; ++j) {
                    y[j] = dl2 * (grid[j] + delta[l]);
                }
                y += 8;
            }
            qs += 4;
            qh += 2;
        }
    }
}

static void dequantize_row_iq4_xs(const block_iq4_xs * x, float * y, int64_t k) {
    const int64_t nb = k / QK_K;

    for (int i = 0; i < nb; i++) {

        const uint8_t * qs = x[i].qs;

        const float d = fp16_to_f32(x[i].d);

        for (int ib = 0; ib < QK_K/32; ++ib) {
            const int ls = ((x[i].scales_l[ib/2] >> 4*(ib%2)) & 0xf) | (((x[i].scales_h >> 2*ib) & 3) << 4);
            const float dl = d * (ls - 32);
            for (int j = 0; j < 16; ++j) {
                y[j+ 0] = dl * kvalues_iq4nl[qs[j] & 0xf];
                y[j+16] = dl * kvalues_iq4nl[qs[j] >>  4];
            }
            y  += 32;
            qs += 16;
        }
    }
}

uint64_t aiueos_qwen35_quant_row_bytes(uint32_t type, uint64_t elements) {
  if (!elements) return 0;
  switch (type) {
    case AIUEOS_GGML_F32:
      return elements > UINT64_MAX / 4 ? 0 : elements * 4;
    case AIUEOS_GGML_Q8_0:
      return elements % 32 ? 0 : (elements / 32) * 34;
    case AIUEOS_GGML_Q2_K:
      return elements % 256 ? 0 : (elements / 256) * 84;
    case AIUEOS_GGML_Q3_K:
      return elements % 256 ? 0 : (elements / 256) * 110;
    case AIUEOS_GGML_Q4_K:
      return elements % 256 ? 0 : (elements / 256) * 144;
    case AIUEOS_GGML_Q5_K:
      return elements % 256 ? 0 : (elements / 256) * 176;
    case AIUEOS_GGML_Q6_K:
      return elements % 256 ? 0 : (elements / 256) * 210;
    case AIUEOS_GGML_IQ2_XXS:
      return elements % 256 ? 0 : (elements / 256) * 66;
    case AIUEOS_GGML_IQ2_XS:
      return elements % 256 ? 0 : (elements / 256) * 74;
    case AIUEOS_GGML_IQ3_XXS:
      return elements % 256 ? 0 : (elements / 256) * 98;
    case AIUEOS_GGML_IQ1_S:
      return elements % 256 ? 0 : (elements / 256) * 50;
    case AIUEOS_GGML_IQ3_S:
      return elements % 256 ? 0 : (elements / 256) * 110;
    case AIUEOS_GGML_IQ2_S:
      return elements % 256 ? 0 : (elements / 256) * 82;
    case AIUEOS_GGML_IQ4_XS:
      return elements % 256 ? 0 : (elements / 256) * 136;
    case AIUEOS_GGML_IQ1_M:
      return elements % 256 ? 0 : (elements / 256) * 56;
    default:
      return 0;
  }
}

int aiueos_qwen35_dequantize_row(uint32_t type, const uint8_t * data,
                                  uint64_t elements, float * output) {
  if (!data || !output || !aiueos_qwen35_quant_row_bytes(type, elements) ||
      elements > 0x7fffffffULL) return 0;
  switch (type) {
    case AIUEOS_GGML_F32:
      byte_copy(output, data, elements * sizeof(float));
      return 1;
    case AIUEOS_GGML_Q8_0:
      dequantize_row_q8_0((const block_q8_0 *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_Q2_K:
      dequantize_row_q2_K((const block_q2_K *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_Q3_K:
      dequantize_row_q3_K((const block_q3_K *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_Q4_K:
      dequantize_row_q4_K((const block_q4_K *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_Q5_K:
      dequantize_row_q5_K((const block_q5_K *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_Q6_K:
      dequantize_row_q6_K((const block_q6_K *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ2_XXS:
      dequantize_row_iq2_xxs((const block_iq2_xxs *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ2_XS:
      dequantize_row_iq2_xs((const block_iq2_xs *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ3_XXS:
      dequantize_row_iq3_xxs((const block_iq3_xxs *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ1_S:
      dequantize_row_iq1_s((const block_iq1_s *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ3_S:
      dequantize_row_iq3_s((const block_iq3_s *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ2_S:
      dequantize_row_iq2_s((const block_iq2_s *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ4_XS:
      dequantize_row_iq4_xs((const block_iq4_xs *)data, output, (int64_t)elements);
      return 1;
    case AIUEOS_GGML_IQ1_M:
      dequantize_row_iq1_m((const block_iq1_m *)data, output, (int64_t)elements);
      return 1;
    default:
      return 0;
  }
}
