#ifndef AIUEOS_UEFI_MODEL_SLOTS_H
#define AIUEOS_UEFI_MODEL_SLOTS_H

#include <stdint.h>

#define AIUEOS_MODEL_SLOT_BLOCK_BYTES 512U
#define AIUEOS_MODEL_SLOT_ANCHOR_LBA 0ULL
#define AIUEOS_MODEL_SLOT_SELECTOR0_LBA 1ULL
#define AIUEOS_MODEL_SLOT_SELECTOR1_LBA 2ULL
#define AIUEOS_MODEL_SLOT_HEADER0_LBA 3ULL
#define AIUEOS_MODEL_SLOT_HEADER1_LBA 4ULL

struct aiueos_model_slot_io {
  void *context;
  uint32_t block_bytes;
  uint32_t io_alignment;
  uint64_t block_count;
  int (*read_blocks)(void *context, uint64_t lba, uint64_t blocks, void *buffer);
  int (*write_blocks)(void *context, uint64_t lba, uint64_t blocks,
                      const void *buffer);
  int (*flush)(void *context);
};

struct aiueos_model_identity {
  uint64_t bytes;
  uint8_t sha256[32];
};

struct aiueos_model_slot_state {
  int active;
  uint32_t active_slot;
  uint64_t generation;
  struct aiueos_model_identity identity;
};

struct aiueos_sha256_state {
  uint32_t words[8];
  uint64_t bytes;
  uint8_t pending[64];
  uint32_t pending_bytes;
};

struct aiueos_model_slot_session {
  const struct aiueos_model_slot_io *io;
  struct aiueos_model_identity identity;
  uint64_t data_lba;
  uint64_t slot_blocks;
  uint64_t generation;
  uint64_t written_bytes;
  uint64_t written_blocks;
  uint32_t target_slot;
  uint32_t tail_bytes;
  uint8_t tail[AIUEOS_MODEL_SLOT_BLOCK_BYTES];
  struct aiueos_sha256_state sha;
};

enum aiueos_model_slot_begin_result {
  AIUEOS_MODEL_SLOT_BEGIN_ERROR = 0,
  AIUEOS_MODEL_SLOT_BEGIN_WRITE = 1,
  AIUEOS_MODEL_SLOT_BEGIN_ALREADY_ACTIVE = 2
};

int aiueos_model_slot_inspect(const struct aiueos_model_slot_io *io,
                              struct aiueos_model_slot_state *state);
int aiueos_model_slot_verify_active(const struct aiueos_model_slot_io *io,
                                    const struct aiueos_model_slot_state *state,
                                    void *scratch, uint64_t scratch_bytes);
int aiueos_model_slot_begin(const struct aiueos_model_slot_io *io,
                            const struct aiueos_model_identity *identity,
                            struct aiueos_model_slot_session *session,
                            struct aiueos_model_slot_state *before);
int aiueos_model_slot_append(struct aiueos_model_slot_session *session,
                             const void *bytes, uint64_t byte_count);
int aiueos_model_slot_commit(struct aiueos_model_slot_session *session,
                             void *scratch, uint64_t scratch_bytes,
                             struct aiueos_model_slot_state *after);
uint32_t aiueos_model_slot_crc32(const void *bytes, uint64_t byte_count);

#endif
