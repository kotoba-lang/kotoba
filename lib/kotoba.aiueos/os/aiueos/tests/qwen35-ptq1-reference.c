/* SPDX-License-Identifier: Apache-2.0 */
#include <stdint.h>
#include <string.h>

typedef uint16_t ggml_half;
typedef struct { uint8_t qs[24]; uint8_t qh[2]; ggml_half d; } block_ptq1_0;

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

static void dequantize_row_ptq1_0(const block_ptq1_0 *x, float *y,
                                  int64_t elements) {
  static const uint32_t pow3[5] = {1U, 3U, 9U, 27U, 81U};
  const int64_t blocks = elements / 128;
  for (int64_t block = 0; block < blocks; block++) {
    const float d = fp16_to_f32(x[block].d);
    for (uint32_t e = 0; e < 128U; e++) {
      uint8_t packed;
      uint32_t n;
      if (e < 80U) {
        packed = x[block].qs[e % 16U];
        n = e / 16U;
      } else if (e < 120U) {
        uint32_t q = e - 80U;
        packed = x[block].qs[16U + q % 8U];
        n = q / 8U;
      } else {
        uint32_t q = e - 120U;
        packed = x[block].qh[q % 2U];
        n = q / 2U;
      }
      uint32_t trit = (((((uint32_t)packed * pow3[n]) & 0xffU) * 3U) >> 8);
      y[block * 128 + e] = (float)((int32_t)trit - 1) * d;
    }
  }
}

/* Isolated C reference for the PTQ1_0 format used by the AIUEOS C path. */
int aiueos_qwen35_dequantize_row(uint32_t type, const uint8_t *data,
                                  uint64_t elements, float *output) {
  if (type != 143U || !data || !output || elements == 0 ||
      elements % 128U != 0 || elements > 0x7fffffffULL) return 0;
  dequantize_row_ptq1_0((const block_ptq1_0 *)data, output,
                        (int64_t)elements);
  return 1;
}
