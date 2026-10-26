#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../uefi/model_slots.h"

#define BLOCKS 512U

struct __attribute__((packed)) test_anchor {
  uint8_t magic[16];
  uint32_t version;
  uint32_t block_bytes;
  uint64_t partition_blocks;
  uint64_t slot_blocks;
  uint64_t data_lba[2];
  uint8_t reserved[452];
  uint32_t crc32;
};

static uint8_t disk[BLOCKS * AIUEOS_MODEL_SLOT_BLOCK_BYTES];
static uint64_t fail_write_lba = UINT64_MAX;

static int read_blocks(void *unused, uint64_t lba, uint64_t blocks, void *buffer) {
  (void)unused;
  if (!blocks || lba >= BLOCKS || blocks > BLOCKS - lba) return 0;
  memcpy(buffer, disk + lba * AIUEOS_MODEL_SLOT_BLOCK_BYTES,
         blocks * AIUEOS_MODEL_SLOT_BLOCK_BYTES);
  return 1;
}

static int write_blocks(void *unused, uint64_t lba, uint64_t blocks,
                        const void *buffer) {
  (void)unused;
  if (!blocks || lba >= BLOCKS || blocks > BLOCKS - lba || lba == fail_write_lba)
    return 0;
  memcpy(disk + lba * AIUEOS_MODEL_SLOT_BLOCK_BYTES, buffer,
         blocks * AIUEOS_MODEL_SLOT_BLOCK_BYTES);
  return 1;
}

static int flush(void *unused) { (void)unused; return 1; }

static int expect(int condition, const char *message) {
  if (!condition) fprintf(stderr, "model-slot test failed: %s\n", message);
  return condition;
}

static void format_anchor(void) {
  static const uint8_t magic[16] =
    {'A','I','U','E','O','S','-','M','O','D','E','L','-','A','B','1'};
  struct test_anchor anchor;
  memset(&anchor, 0, sizeof(anchor));
  memcpy(anchor.magic, magic, sizeof(magic));
  anchor.version = 1;
  anchor.block_bytes = AIUEOS_MODEL_SLOT_BLOCK_BYTES;
  anchor.partition_blocks = BLOCKS;
  anchor.slot_blocks = 128;
  anchor.data_lba[0] = 16;
  anchor.data_lba[1] = 256;
  anchor.crc32 = aiueos_model_slot_crc32(&anchor, sizeof(anchor));
  memcpy(disk, &anchor, sizeof(anchor));
}

int main(void) {
  static const uint8_t abc_sha[32] = {
    0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
    0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad
  };
  static const uint8_t hello_sha[32] = {
    0xb9,0x4d,0x27,0xb9,0x93,0x4d,0x3e,0x08,0xa5,0x2e,0x52,0xd7,0xda,0x7d,0xab,0xfa,
    0xc4,0x84,0xef,0xe3,0x7a,0x53,0x80,0xee,0x90,0x88,0xf7,0xac,0xe2,0xef,0xcd,0xe9
  };
  struct aiueos_model_slot_io io = {
    .block_bytes = AIUEOS_MODEL_SLOT_BLOCK_BYTES, .block_count = BLOCKS,
    .read_blocks = read_blocks, .write_blocks = write_blocks, .flush = flush
  };
  struct aiueos_model_identity first = {.bytes = 3}, second = {.bytes = 11};
  memcpy(first.sha256, abc_sha, 32);
  memcpy(second.sha256, hello_sha, 32);
  struct aiueos_model_slot_session session;
  struct aiueos_model_slot_state before, after;
  uint8_t scratch[4096], old_slot[AIUEOS_MODEL_SLOT_BLOCK_BYTES];
  format_anchor();
  if (!expect(aiueos_model_slot_begin(&io, &first, &session, &before) ==
              AIUEOS_MODEL_SLOT_BEGIN_WRITE, "first import plan") ||
      !expect(aiueos_model_slot_append(&session, "abc", 3), "first append") ||
      !expect(aiueos_model_slot_commit(&session, scratch, sizeof(scratch), &after),
              "first commit") ||
      !expect(after.active_slot == 0 && after.generation == 1, "first selector")) return 1;
  memcpy(old_slot, disk + 16 * AIUEOS_MODEL_SLOT_BLOCK_BYTES, sizeof(old_slot));

  if (!expect(aiueos_model_slot_begin(&io, &second, &session, &before) ==
              AIUEOS_MODEL_SLOT_BEGIN_WRITE && session.target_slot == 1,
              "inactive slot update plan") ||
      !expect(aiueos_model_slot_append(&session, "hello world", 11), "second append")) return 1;
  fail_write_lba = AIUEOS_MODEL_SLOT_SELECTOR0_LBA;
  if (!expect(!aiueos_model_slot_commit(&session, scratch, sizeof(scratch), &after),
              "interrupted selector commit refused") ||
      !expect(aiueos_model_slot_inspect(&io, &after) && after.active_slot == 0 &&
              after.generation == 1, "last-known-good survives interruption")) return 1;

  fail_write_lba = UINT64_MAX;
  if (!expect(aiueos_model_slot_begin(&io, &second, &session, &before) ==
              AIUEOS_MODEL_SLOT_BEGIN_WRITE, "retry plan") ||
      !expect(aiueos_model_slot_append(&session, "hello world", 11), "retry append") ||
      !expect(aiueos_model_slot_commit(&session, scratch, sizeof(scratch), &after),
              "retry commit") ||
      !expect(after.active_slot == 1 && after.generation == 2, "slot B active") ||
      !expect(aiueos_model_slot_verify_active(&io, &after, scratch, sizeof(scratch)),
              "active slot full readback") ||
      !expect(!memcmp(old_slot, disk + 16 * AIUEOS_MODEL_SLOT_BLOCK_BYTES,
                     sizeof(old_slot)), "slot A byte-identical")) return 1;

  disk[AIUEOS_MODEL_SLOT_SELECTOR0_LBA * AIUEOS_MODEL_SLOT_BLOCK_BYTES] ^= 1;
  if (!expect(aiueos_model_slot_inspect(&io, &after) && after.active_slot == 0 &&
              after.generation == 1, "corrupt latest selector falls back")) return 1;
  puts("AIUEOS_MODEL_SLOTS_MODEL_OK layout=ab inactive-write=1 readback=sha256 atomic-selector=1 fallback=last-known-good");
  return 0;
}
