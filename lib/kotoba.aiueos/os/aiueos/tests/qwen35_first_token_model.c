/* SPDX-License-Identifier: Apache-2.0 */
#include "qwen35_infer.h"
#include "qwen35_runtime.h"

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static void progress(uint32_t completed, uint32_t total, int output_head) {
  fprintf(stderr, "AIUEOS_QWEN35_MODEL_PROGRESS layers=%u/%u output=%d\n",
          completed, total, output_head);
}

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  int descriptor = open(argv[1], O_RDONLY);
  struct stat status;
  if (descriptor < 0 || fstat(descriptor, &status) != 0 ||
      (uint64_t)status.st_size != AIUEOS_QWEN35_ARTIFACT_BYTES)
    return 3;
  const uint8_t *bytes = mmap(0, (size_t)status.st_size, PROT_READ,
                              MAP_PRIVATE, descriptor, 0);
  if (bytes == MAP_FAILED) return 4;
  struct aiueos_qwen35_model *model = calloc(1, sizeof(*model));
  void *workspace = aligned_alloc(16, AIUEOS_QWEN35_WORKSPACE_BYTES);
  if (!model || !workspace) return 5;
  if (!aiueos_qwen35_model_parse(bytes, (uint64_t)status.st_size,
                                  (uint64_t)status.st_size, model))
    return 6;
  struct aiueos_qwen35_first_token_result result;
  if (!aiueos_qwen35_first_token(model, AIUEOS_QWEN35_BOS_TOKEN,
                                  workspace, AIUEOS_QWEN35_WORKSPACE_BYTES,
                                  progress, &result))
    return 7;
  printf("AIUEOS_QWEN35_FIRST_TOKEN_MODEL_OK bos=%u token=%u logit=%.9g "
         "second=%u second-logit=%.9g\n",
         AIUEOS_QWEN35_BOS_TOKEN, result.token, result.logit,
         result.second_token, result.second_logit);
  return result.token == AIUEOS_QWEN35_REFERENCE_FIRST_TOKEN ? 0 : 8;
}
