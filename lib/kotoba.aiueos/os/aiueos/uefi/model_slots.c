#include "model_slots.h"

#define AIUEOS_MODEL_SLOT_VERSION 1U
#define AIUEOS_MODEL_SLOT_RECORD_HEADER 1U
#define AIUEOS_MODEL_SLOT_RECORD_SELECTOR 2U
#define AIUEOS_MODEL_SLOT_COMMITTED 1U

struct __attribute__((packed)) aiueos_model_slot_anchor {
  uint8_t magic[16];
  uint32_t version;
  uint32_t block_bytes;
  uint64_t partition_blocks;
  uint64_t slot_blocks;
  uint64_t data_lba[2];
  uint8_t reserved[452];
  uint32_t crc32;
};

struct __attribute__((packed)) aiueos_model_slot_record {
  uint8_t magic[16];
  uint32_t version;
  uint32_t kind;
  uint64_t generation;
  uint64_t artifact_bytes;
  uint32_t slot;
  uint32_t state;
  uint8_t artifact_sha256[32];
  uint8_t reserved[428];
  uint32_t crc32;
};

_Static_assert(sizeof(struct aiueos_model_slot_anchor) == AIUEOS_MODEL_SLOT_BLOCK_BYTES,
               "model-slot anchor must occupy one block");
_Static_assert(sizeof(struct aiueos_model_slot_record) == AIUEOS_MODEL_SLOT_BLOCK_BYTES,
               "model-slot record must occupy one block");

static const uint8_t anchor_magic[16] =
  {'A','I','U','E','O','S','-','M','O','D','E','L','-','A','B','1'};
static const uint8_t record_magic[16] =
  {'A','I','U','E','O','S','-','M','O','D','E','L','-','R','1','0'};

static void zero_bytes(void *destination, uint64_t bytes) {
  uint8_t *out = destination;
  while (bytes--) *out++ = 0;
}

static void copy_bytes(void *destination, const void *source, uint64_t bytes) {
  uint8_t *out = destination;
  const uint8_t *in = source;
  while (bytes--) *out++ = *in++;
}

static int bytes_equal(const void *left, const void *right, uint64_t bytes) {
  const uint8_t *a = left, *b = right;
  uint8_t difference = 0;
  while (bytes--) difference |= (uint8_t)(*a++ ^ *b++);
  return difference == 0;
}

uint32_t aiueos_model_slot_crc32(const void *input, uint64_t bytes) {
  const uint8_t *p = input;
  uint32_t crc = 0xffffffffU;
  while (bytes--) {
    crc ^= *p++;
    for (uint32_t bit = 0; bit < 8; bit++)
      crc = (crc >> 1) ^ (0xedb88320U & (uint32_t)(0U - (crc & 1U)));
  }
  return ~crc;
}

static uint32_t rotate_right(uint32_t value, uint32_t bits) {
  return (value >> bits) | (value << (32U - bits));
}

static void sha256_transform(struct aiueos_sha256_state *state,
                             const uint8_t block[64]) {
  static const uint32_t constants[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  };
  uint32_t words[64];
  for (uint32_t i = 0; i < 16; i++)
    words[i] = ((uint32_t)block[i*4] << 24) |
               ((uint32_t)block[i*4+1] << 16) |
               ((uint32_t)block[i*4+2] << 8) | block[i*4+3];
  for (uint32_t i = 16; i < 64; i++) {
    uint32_t s0 = rotate_right(words[i-15],7) ^ rotate_right(words[i-15],18) ^
                  (words[i-15] >> 3);
    uint32_t s1 = rotate_right(words[i-2],17) ^ rotate_right(words[i-2],19) ^
                  (words[i-2] >> 10);
    words[i] = words[i-16] + s0 + words[i-7] + s1;
  }
  uint32_t a=state->words[0],b=state->words[1],c=state->words[2],d=state->words[3];
  uint32_t e=state->words[4],f=state->words[5],g=state->words[6],h=state->words[7];
  for (uint32_t i = 0; i < 64; i++) {
    uint32_t s1=rotate_right(e,6)^rotate_right(e,11)^rotate_right(e,25);
    uint32_t t1=h+s1+((e&f)^((~e)&g))+constants[i]+words[i];
    uint32_t s0=rotate_right(a,2)^rotate_right(a,13)^rotate_right(a,22);
    uint32_t t2=s0+((a&b)^(a&c)^(b&c));
    h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
  }
  state->words[0]+=a;state->words[1]+=b;state->words[2]+=c;state->words[3]+=d;
  state->words[4]+=e;state->words[5]+=f;state->words[6]+=g;state->words[7]+=h;
}

static void sha256_init(struct aiueos_sha256_state *state) {
  static const uint32_t initial[8] = {
    0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
  };
  for (uint32_t i = 0; i < 8; i++) state->words[i] = initial[i];
  state->bytes = 0;
  state->pending_bytes = 0;
}

static void sha256_update(struct aiueos_sha256_state *state,
                          const void *input, uint64_t bytes) {
  const uint8_t *p = input;
  state->bytes += bytes;
  while (bytes) {
    uint32_t room = 64U - state->pending_bytes;
    uint32_t take = bytes < room ? (uint32_t)bytes : room;
    copy_bytes(state->pending + state->pending_bytes, p, take);
    state->pending_bytes += take;
    p += take;
    bytes -= take;
    if (state->pending_bytes == 64U) {
      sha256_transform(state, state->pending);
      state->pending_bytes = 0;
    }
  }
}

static void sha256_finish(struct aiueos_sha256_state *state, uint8_t digest[32]) {
  uint64_t bits = state->bytes * 8ULL;
  state->pending[state->pending_bytes++] = 0x80;
  if (state->pending_bytes > 56U) {
    while (state->pending_bytes < 64U) state->pending[state->pending_bytes++] = 0;
    sha256_transform(state, state->pending);
    state->pending_bytes = 0;
  }
  while (state->pending_bytes < 56U) state->pending[state->pending_bytes++] = 0;
  for (int i = 7; i >= 0; i--)
    state->pending[state->pending_bytes++] = (uint8_t)(bits >> (i * 8));
  sha256_transform(state, state->pending);
  for (uint32_t i = 0; i < 8; i++) {
    digest[i*4]=(uint8_t)(state->words[i]>>24);
    digest[i*4+1]=(uint8_t)(state->words[i]>>16);
    digest[i*4+2]=(uint8_t)(state->words[i]>>8);
    digest[i*4+3]=(uint8_t)state->words[i];
  }
}

static int io_sane(const struct aiueos_model_slot_io *io) {
  return io && io->block_bytes == AIUEOS_MODEL_SLOT_BLOCK_BYTES &&
         io->block_count > AIUEOS_MODEL_SLOT_HEADER1_LBA &&
         io->read_blocks && io->write_blocks && io->flush;
}

static int read_anchor(const struct aiueos_model_slot_io *io,
                       struct aiueos_model_slot_anchor *anchor) {
  if (!io_sane(io) || !io->read_blocks(io->context, AIUEOS_MODEL_SLOT_ANCHOR_LBA,
                                       1, anchor)) return 0;
  uint32_t stored = anchor->crc32;
  anchor->crc32 = 0;
  uint32_t measured = aiueos_model_slot_crc32(anchor, sizeof(*anchor));
  anchor->crc32 = stored;
  if (!bytes_equal(anchor->magic, anchor_magic, sizeof(anchor_magic)) ||
      anchor->version != AIUEOS_MODEL_SLOT_VERSION ||
      anchor->block_bytes != io->block_bytes || stored != measured ||
      anchor->partition_blocks != io->block_count || !anchor->slot_blocks)
    return 0;
  for (uint32_t slot = 0; slot < 2; slot++) {
    uint64_t first = anchor->data_lba[slot];
    if (first <= AIUEOS_MODEL_SLOT_HEADER1_LBA ||
        first >= io->block_count || anchor->slot_blocks > io->block_count - first)
      return 0;
  }
  uint64_t a_end = anchor->data_lba[0] + anchor->slot_blocks;
  uint64_t b_end = anchor->data_lba[1] + anchor->slot_blocks;
  if (!(a_end <= anchor->data_lba[1] || b_end <= anchor->data_lba[0])) return 0;
  return 1;
}

static int record_valid(const struct aiueos_model_slot_record *record,
                        uint32_t kind, uint32_t slot) {
  struct aiueos_model_slot_record copy;
  copy_bytes(&copy, record, sizeof(copy));
  uint32_t stored = copy.crc32;
  copy.crc32 = 0;
  return bytes_equal(copy.magic, record_magic, sizeof(record_magic)) &&
         copy.version == AIUEOS_MODEL_SLOT_VERSION && copy.kind == kind &&
         copy.slot == slot && slot < 2 && copy.state == AIUEOS_MODEL_SLOT_COMMITTED &&
         copy.generation && copy.artifact_bytes && stored ==
           aiueos_model_slot_crc32(&copy, sizeof(copy));
}

static int identity_equal(const struct aiueos_model_identity *left,
                          const struct aiueos_model_identity *right) {
  return left->bytes == right->bytes &&
         bytes_equal(left->sha256, right->sha256, sizeof(left->sha256));
}

int aiueos_model_slot_inspect(const struct aiueos_model_slot_io *io,
                              struct aiueos_model_slot_state *state) {
  struct aiueos_model_slot_anchor anchor;
  if (!state || !read_anchor(io, &anchor)) return 0;
  zero_bytes(state, sizeof(*state));
  for (uint32_t copy = 0; copy < 2; copy++) {
    struct aiueos_model_slot_record selector, header;
    uint64_t selector_lba = AIUEOS_MODEL_SLOT_SELECTOR0_LBA + copy;
    if (!io->read_blocks(io->context, selector_lba, 1, &selector) ||
        !record_valid(&selector, AIUEOS_MODEL_SLOT_RECORD_SELECTOR, selector.slot))
      continue;
    uint64_t header_lba = AIUEOS_MODEL_SLOT_HEADER0_LBA + selector.slot;
    if (!io->read_blocks(io->context, header_lba, 1, &header) ||
        !record_valid(&header, AIUEOS_MODEL_SLOT_RECORD_HEADER, selector.slot) ||
        header.generation != selector.generation ||
        header.artifact_bytes != selector.artifact_bytes ||
        !bytes_equal(header.artifact_sha256, selector.artifact_sha256, 32))
      continue;
    if (header.artifact_bytes > anchor.slot_blocks * io->block_bytes) continue;
    if (!state->active || selector.generation > state->generation) {
      state->active = 1;
      state->active_slot = selector.slot;
      state->generation = selector.generation;
      state->identity.bytes = selector.artifact_bytes;
      copy_bytes(state->identity.sha256, selector.artifact_sha256, 32);
    }
  }
  return 1;
}

int aiueos_model_slot_verify_active(const struct aiueos_model_slot_io *io,
                                    const struct aiueos_model_slot_state *state,
                                    void *scratch, uint64_t scratch_bytes) {
  struct aiueos_model_slot_anchor anchor;
  if (!state || !state->active || state->active_slot >= 2 || !scratch ||
      !read_anchor(io, &anchor) || !scratch_bytes ||
      scratch_bytes % io->block_bytes ||
      state->identity.bytes > anchor.slot_blocks * io->block_bytes) return 0;
  uint64_t max_blocks = scratch_bytes / io->block_bytes;
  uint64_t lba = anchor.data_lba[state->active_slot];
  uint64_t remaining = state->identity.bytes;
  struct aiueos_sha256_state sha;
  sha256_init(&sha);
  while (remaining) {
    uint64_t blocks = (remaining + io->block_bytes - 1) / io->block_bytes;
    if (blocks > max_blocks) blocks = max_blocks;
    if (!io->read_blocks(io->context, lba, blocks, scratch)) return 0;
    uint64_t available = blocks * io->block_bytes;
    uint64_t take = remaining < available ? remaining : available;
    sha256_update(&sha, scratch, take);
    remaining -= take;
    lba += blocks;
  }
  uint8_t digest[32];
  sha256_finish(&sha, digest);
  return bytes_equal(digest, state->identity.sha256, sizeof(digest));
}

int aiueos_model_slot_begin(const struct aiueos_model_slot_io *io,
                            const struct aiueos_model_identity *identity,
                            struct aiueos_model_slot_session *session,
                            struct aiueos_model_slot_state *before) {
  struct aiueos_model_slot_anchor anchor;
  struct aiueos_model_slot_state current;
  if (!identity || !identity->bytes || !session || !before ||
      !read_anchor(io, &anchor) ||
      identity->bytes > anchor.slot_blocks * io->block_bytes ||
      !aiueos_model_slot_inspect(io, &current))
    return AIUEOS_MODEL_SLOT_BEGIN_ERROR;
  copy_bytes(before, &current, sizeof(current));
  if (current.active && identity_equal(&current.identity, identity))
    return AIUEOS_MODEL_SLOT_BEGIN_ALREADY_ACTIVE;
  zero_bytes(session, sizeof(*session));
  session->io = io;
  copy_bytes(&session->identity, identity, sizeof(*identity));
  session->target_slot = current.active ? current.active_slot ^ 1U : 0U;
  session->generation = current.active ? current.generation + 1ULL : 1ULL;
  if (!session->generation) return AIUEOS_MODEL_SLOT_BEGIN_ERROR;
  session->data_lba = anchor.data_lba[session->target_slot];
  session->slot_blocks = anchor.slot_blocks;
  sha256_init(&session->sha);
  return AIUEOS_MODEL_SLOT_BEGIN_WRITE;
}

int aiueos_model_slot_append(struct aiueos_model_slot_session *session,
                             const void *input, uint64_t bytes) {
  if (!session || !session->io || (!input && bytes) ||
      bytes > session->identity.bytes - session->written_bytes) return 0;
  const uint8_t *p = input;
  sha256_update(&session->sha, input, bytes);
  session->written_bytes += bytes;
  while (bytes) {
    if (!session->tail_bytes && bytes >= AIUEOS_MODEL_SLOT_BLOCK_BYTES &&
        (!session->io->io_alignment ||
         !((uintptr_t)p % session->io->io_alignment))) {
      uint64_t blocks = bytes / AIUEOS_MODEL_SLOT_BLOCK_BYTES;
      if (blocks > session->slot_blocks - session->written_blocks)
        blocks = session->slot_blocks - session->written_blocks;
      if (!blocks || !session->io->write_blocks(session->io->context,
            session->data_lba + session->written_blocks, blocks, p)) return 0;
      uint64_t consumed = blocks * AIUEOS_MODEL_SLOT_BLOCK_BYTES;
      session->written_blocks += blocks;
      p += consumed;
      bytes -= consumed;
      continue;
    }
    uint32_t room = AIUEOS_MODEL_SLOT_BLOCK_BYTES - session->tail_bytes;
    uint32_t take = bytes < room ? (uint32_t)bytes : room;
    copy_bytes(session->tail + session->tail_bytes, p, take);
    session->tail_bytes += take;
    p += take;
    bytes -= take;
    if (session->tail_bytes == AIUEOS_MODEL_SLOT_BLOCK_BYTES) {
      if (session->written_blocks >= session->slot_blocks ||
          !session->io->write_blocks(session->io->context,
             session->data_lba + session->written_blocks, 1, session->tail)) return 0;
      session->written_blocks++;
      session->tail_bytes = 0;
    }
  }
  return 1;
}

static void build_record(struct aiueos_model_slot_record *record, uint32_t kind,
                         const struct aiueos_model_slot_session *session) {
  zero_bytes(record, sizeof(*record));
  copy_bytes(record->magic, record_magic, sizeof(record_magic));
  record->version = AIUEOS_MODEL_SLOT_VERSION;
  record->kind = kind;
  record->generation = session->generation;
  record->artifact_bytes = session->identity.bytes;
  record->slot = session->target_slot;
  record->state = AIUEOS_MODEL_SLOT_COMMITTED;
  copy_bytes(record->artifact_sha256, session->identity.sha256, 32);
  record->crc32 = aiueos_model_slot_crc32(record, sizeof(*record));
}

int aiueos_model_slot_commit(struct aiueos_model_slot_session *session,
                             void *scratch, uint64_t scratch_bytes,
                             struct aiueos_model_slot_state *after) {
  if (!session || !session->io || !scratch || !after ||
      session->written_bytes != session->identity.bytes ||
      scratch_bytes < session->io->block_bytes ||
      scratch_bytes % session->io->block_bytes) return 0;
  if (session->tail_bytes) {
    zero_bytes(session->tail + session->tail_bytes,
               AIUEOS_MODEL_SLOT_BLOCK_BYTES - session->tail_bytes);
    if (session->written_blocks >= session->slot_blocks ||
        !session->io->write_blocks(session->io->context,
          session->data_lba + session->written_blocks, 1, session->tail)) return 0;
    session->written_blocks++;
    session->tail_bytes = 0;
  }
  uint8_t digest[32];
  struct aiueos_sha256_state written_sha = session->sha;
  sha256_finish(&written_sha, digest);
  if (!bytes_equal(digest, session->identity.sha256, 32) ||
      !session->io->flush(session->io->context)) return 0;

  struct aiueos_model_slot_state candidate;
  zero_bytes(&candidate, sizeof(candidate));
  candidate.active = 1;
  candidate.active_slot = session->target_slot;
  candidate.generation = session->generation;
  copy_bytes(&candidate.identity, &session->identity, sizeof(candidate.identity));
  if (!aiueos_model_slot_verify_active(session->io, &candidate, scratch, scratch_bytes))
    return 0;

  struct aiueos_model_slot_record record, verify;
  build_record(&record, AIUEOS_MODEL_SLOT_RECORD_HEADER, session);
  uint64_t header_lba = AIUEOS_MODEL_SLOT_HEADER0_LBA + session->target_slot;
  if (!session->io->write_blocks(session->io->context, header_lba, 1, &record) ||
      !session->io->flush(session->io->context) ||
      !session->io->read_blocks(session->io->context, header_lba, 1, &verify) ||
      !bytes_equal(&record, &verify, sizeof(record))) return 0;

  build_record(&record, AIUEOS_MODEL_SLOT_RECORD_SELECTOR, session);
  uint64_t selector_lba = AIUEOS_MODEL_SLOT_SELECTOR0_LBA +
                          (session->generation & 1ULL);
  if (!session->io->write_blocks(session->io->context, selector_lba, 1, &record) ||
      !session->io->flush(session->io->context) ||
      !session->io->read_blocks(session->io->context, selector_lba, 1, &verify) ||
      !bytes_equal(&record, &verify, sizeof(record))) return 0;
  return aiueos_model_slot_inspect(session->io, after) && after->active &&
         after->active_slot == session->target_slot &&
         after->generation == session->generation &&
         identity_equal(&after->identity, &session->identity);
}
