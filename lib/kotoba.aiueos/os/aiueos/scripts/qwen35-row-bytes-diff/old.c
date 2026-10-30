/* kernel/qwen35_quant.c's aiueos_qwen35_quant_row_bytes before JUN-554 moved it to kotoba/qwen35-row-bytes.o, verbatim
   (only renamed). */
#include <stdint.h>
#include "qwen35_runtime.h"
#define aiueos_qwen35_quant_row_bytes old_row_bytes
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

