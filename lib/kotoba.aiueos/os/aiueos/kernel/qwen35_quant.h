/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_QWEN35_QUANT_H
#define AIUEOS_QWEN35_QUANT_H

#include <stdint.h>

int aiueos_qwen35_dequantize_row(uint32_t type, const uint8_t * data,
                                  uint64_t elements, float * output);
uint64_t aiueos_qwen35_quant_row_bytes(uint32_t type, uint64_t elements);

#endif
