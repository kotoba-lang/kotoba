/* SPDX-License-Identifier: Apache-2.0 */
/* The Bonsai profile of `aiueos_qwen35_model_translate`, graded (ADR-0222).
 *
 * `tests/qwen35_runtime_model.c` grades the Qwen3.8 profile by comparing the
 * translation against the C reference parser in the same binary. There is no
 * C reference parser for Ternary Bonsai 2 27B PTQ1_0 and there will not be
 * one: the parser moved into three Kotoba objects (ADR-0145) before this
 * artifact existed, and writing a second C parser to check the first would be
 * writing the thing ADR-0145 deleted.
 *
 * So the two sides of this gate come from two different places and neither is
 * this file:
 *
 *   THE INPUT is the 144-byte and 28,160-byte workspaces of
 *   `qwen35-gguf-kv-scan.kotoba` and `qwen35-tensor-table-bind.kotoba`,
 *   carried in their contracts as `:expect-plan-hex`, computed independently
 *   in python from the real artifact header, and pinned to what the objects
 *   actually produce by `run-task.cljk bonsai-admission-contracts` (the KIR
 *   oracle over the sha256-pinned first 11,120,992 bytes of the public file).
 *
 *   THE EXPECTATION is `contracts/bonsai2-qwen35-runtime-v1.edn`, the graph
 *   contract, derived from the same artifact by a different route and held to
 *   its own arithmetic by `test/aiueos/bonsai2_qwen35_contract_test.cljk`.
 *
 * `scripts/smoke-bonsai-runtime-translation.cljk` decodes the first and
 * renders the second into the expectations file this program reads, so no
 * number below is typed in this file. What is asserted here is that the 851
 * records land in the 851 struct fields the graph contract names, with its
 * dimensions and its ggml types, and that the extents still tile the artifact
 * after the translation's `file_offset - data_offset` subtraction.
 *
 * The controls are the point of the second half. Nine of them: one that
 * corrupts a record and requires the walk to NAME the field, and eight that
 * each drive one refusal of the translation and require its reason literal.
 * A translation that cannot go red is not evidence that it went green for a
 * reason -- and five of those eight reasons were added by this change, so
 * "the code is there" is exactly what they must not be taken for.
 *
 * `translate` never dereferences its `bytes` argument -- it records it, and
 * `aiueos_qwen35_model_bind` is the function that reads through it -- so this
 * gate passes a one-byte stand-in and does not call bind. Binding the Bonsai
 * artifact needs the artifact, which is 5.9 GB and not on this machine.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../kernel/qwen35_runtime.h"

#define KV_PLAN_BYTES 144U
#define TT_PLAN_BYTES 28160U
#define TT_SLOT_BYTES 32U

static int failures;

static int check(int condition, const char *name) {
  if (condition) return 1;
  fprintf(stderr, "FAIL %s\n", name);
  failures++;
  return 0;
}

static uint8_t *read_file(const char *path, uint64_t *length) {
  FILE *file = fopen(path, "rb");
  if (!file || fseek(file, 0, SEEK_END) != 0) return 0;
  long end = ftell(file);
  if (end <= 0 || fseek(file, 0, SEEK_SET) != 0) return 0;
  uint8_t *bytes = malloc((size_t)end);
  if (!bytes || fread(bytes, 1, (size_t)end, file) != (size_t)end) {
    free(bytes);
    fclose(file);
    return 0;
  }
  fclose(file);
  *length = (uint64_t)end;
  return bytes;
}

/* ------------------------------------------------------- the expectations
 *
 * Two line shapes, both written by the driver out of the graph contract:
 *
 *   n <name> <value>
 *   role <linear|full|every|model> <name> <ndims> <d0> <d1> <ggml-type>
 *
 * Every scalar this program knows must be present, and every scalar the file
 * carries must be consumed: a name this program does not ask about is an
 * expectation that silently did not run, which is the failure mode a gate
 * cannot have. */

#define MAX_SCALARS 64U
#define MAX_ROLES 32U
#define MAX_ROLE_IDS 32U

struct scalar { char name[48]; uint64_t value; int used; };
struct role_line {
  char kind[16];
  char name[48];
  uint32_t dimension_count;
  uint64_t d0, d1;
  uint32_t type;
  int used;
};

struct role_id { uint32_t id; char name[48]; };

static struct scalar scalars[MAX_SCALARS];
static uint32_t scalar_count;
static struct role_line roles[MAX_ROLES];
static uint32_t role_count;
static struct role_id role_ids[MAX_ROLE_IDS];
static uint32_t role_id_count;

static uint64_t expect_scalar(const char *name) {
  for (uint32_t i = 0; i < scalar_count; i++)
    if (strcmp(scalars[i].name, name) == 0) {
      scalars[i].used = 1;
      return scalars[i].value;
    }
  fprintf(stderr, "FAIL the expectations do not name %s\n", name);
  failures++;
  return (uint64_t)-1;
}

static int load_expectations(const char *path) {
  FILE *file = fopen(path, "r");
  if (!file) return 0;
  char line[256];
  while (fgets(line, sizeof(line), file)) {
    if (line[0] == '#' || line[0] == '\n') continue;
    char kind[16];
    if (sscanf(line, "%15s", kind) != 1) continue;
    if (strcmp(kind, "n") == 0) {
      if (scalar_count >= MAX_SCALARS) { fclose(file); return 0; }
      struct scalar *s = &scalars[scalar_count];
      if (sscanf(line, "n %47s %llu", s->name,
                 (unsigned long long *)&s->value) != 2) { fclose(file); return 0; }
      scalar_count++;
    } else if (strcmp(kind, "role") == 0) {
      if (role_count >= MAX_ROLES) { fclose(file); return 0; }
      struct role_line *r = &roles[role_count];
      unsigned long long d0 = 0, d1 = 0;
      unsigned ndims = 0, type = 0;
      if (sscanf(line, "role %15s %47s %u %llu %llu %u", r->kind, r->name,
                 &ndims, &d0, &d1, &type) != 6) { fclose(file); return 0; }
      r->dimension_count = ndims;
      r->d0 = d0;
      r->d1 = d1;
      r->type = type;
      role_count++;
    } else if (strcmp(kind, "id") == 0) {
      if (role_id_count >= MAX_ROLE_IDS) { fclose(file); return 0; }
      struct role_id *r = &role_ids[role_id_count];
      unsigned id = 0;
      if (sscanf(line, "id %u %47s", &id, r->name) != 2) { fclose(file); return 0; }
      r->id = id;
      role_id_count++;
    } else { fclose(file); return 0; }
  }
  fclose(file);
  return 1;
}

static const char *role_name(uint32_t id) {
  for (uint32_t i = 0; i < role_id_count; i++)
    if (role_ids[i].id == id) return role_ids[i].name;
  return 0;
}

/* ------------------------------------------------------------ role -> field
 *
 * Which field of `struct aiueos_qwen35_layer` (or of the model, for the three
 * whole-model tensors) each role of the graph contract must have landed in.
 * The names are the contract's, so a contract that grows a role fails here as
 * an unconsumed expectation rather than passing unnoticed. */

struct role_field { const char *name; size_t offset; };

static const struct role_field every_layer_fields[] = {
  {"attn_norm.weight", offsetof(struct aiueos_qwen35_layer, attention_norm)},
  {"post_attention_norm.weight",
   offsetof(struct aiueos_qwen35_layer, post_attention_norm)},
  {"ffn_down.weight", offsetof(struct aiueos_qwen35_layer, ffn_down)},
  {"ffn_gate.weight", offsetof(struct aiueos_qwen35_layer, ffn_gate)},
  {"ffn_up.weight", offsetof(struct aiueos_qwen35_layer, ffn_up)}
};

static const struct role_field linear_fields[] = {
  {"attn_gate.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.gate)},
  {"attn_qkv.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.qkv)},
  {"ssm_a", offsetof(struct aiueos_qwen35_layer, mixer.linear.a)},
  {"ssm_alpha.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.alpha)},
  {"ssm_beta.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.beta)},
  {"ssm_conv1d.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.conv1d)},
  {"ssm_dt.bias", offsetof(struct aiueos_qwen35_layer, mixer.linear.dt_bias)},
  {"ssm_norm.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.norm)},
  {"ssm_out.weight", offsetof(struct aiueos_qwen35_layer, mixer.linear.output)}
};

static const struct role_field full_fields[] = {
  {"attn_k.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.key)},
  {"attn_k_norm.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.key_norm)},
  {"attn_output.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.output)},
  {"attn_q.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.query_gate)},
  {"attn_q_norm.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.query_norm)},
  {"attn_v.weight", offsetof(struct aiueos_qwen35_layer, mixer.full.value)}
};

static const struct role_field model_fields[] = {
  {"token_embd.weight", offsetof(struct aiueos_qwen35_model, token_embedding)},
  {"output_norm.weight", offsetof(struct aiueos_qwen35_model, output_norm)},
  {"output.weight", offsetof(struct aiueos_qwen35_model, output)}
};

static size_t field_offset(const struct role_field *table, size_t count,
                           const char *name) {
  for (size_t i = 0; i < count; i++)
    if (strcmp(table[i].name, name) == 0) return table[i].offset;
  return (size_t)-1;
}

static const struct aiueos_qwen35_tensor *tensor_at(const void *base,
                                                    size_t offset) {
  return (const struct aiueos_qwen35_tensor *)((const uint8_t *)base + offset);
}

/* ------------------------------------------------------------- the walk
 *
 * Every tensor the graph contract names, in the field the translation put it
 * in. Returns the number of disagreements and names the first, because a
 * count alone cannot be told from a corrupted record's count. `visited`
 * answers the other half: how many struct fields carry a tensor at all, so
 * that 851 records landing in 850 fields plus one overwrite is a failure and
 * not a silent tie. */
static int walk_roles(const struct aiueos_qwen35_model *model,
                      int *visited, char *named, size_t named_size) {
  int differences = 0;
  int seen = 0;
  if (named_size) named[0] = 0;
  for (uint32_t layer = 0; layer < AIUEOS_QWEN35_TRUNK_LAYER_COUNT; layer++) {
    const struct aiueos_qwen35_layer *l = &model->layers[layer];
    int linear = l->linear_attention != 0;
    for (uint32_t r = 0; r < role_count; r++) {
      const struct role_line *role = &roles[r];
      const struct role_field *table;
      size_t table_count;
      if (strcmp(role->kind, "every") == 0) {
        table = every_layer_fields;
        table_count = sizeof(every_layer_fields) / sizeof(every_layer_fields[0]);
      } else if (strcmp(role->kind, "linear") == 0) {
        if (!linear) continue;
        table = linear_fields;
        table_count = sizeof(linear_fields) / sizeof(linear_fields[0]);
      } else if (strcmp(role->kind, "full") == 0) {
        if (linear) continue;
        table = full_fields;
        table_count = sizeof(full_fields) / sizeof(full_fields[0]);
      } else {
        continue;
      }
      size_t at = field_offset(table, table_count, role->name);
      if (at == (size_t)-1) {
        if (named_size && !named[0])
          snprintf(named, named_size, "no field for role %s", role->name);
        differences++;
        continue;
      }
      const struct aiueos_qwen35_tensor *t = tensor_at(l, at);
      seen++;
      if (t->dimension_count != role->dimension_count ||
          t->dimensions[0] != role->d0 ||
          t->dimensions[1] != (role->dimension_count == 2 ? role->d1 : 0) ||
          t->type != role->type) {
        if (named_size && !named[0])
          snprintf(named, named_size, "blk.%u.%s", layer, role->name);
        differences++;
      }
    }
  }
  for (uint32_t r = 0; r < role_count; r++) {
    const struct role_line *role = &roles[r];
    if (strcmp(role->kind, "model") != 0) continue;
    size_t at = field_offset(model_fields,
                             sizeof(model_fields) / sizeof(model_fields[0]),
                             role->name);
    if (at == (size_t)-1) {
      if (named_size && !named[0])
        snprintf(named, named_size, "no field for role %s", role->name);
      differences++;
      continue;
    }
    const struct aiueos_qwen35_tensor *t = tensor_at(model, at);
    seen++;
    if (t->dimension_count != role->dimension_count ||
        t->dimensions[0] != role->d0 ||
        t->dimensions[1] != (role->dimension_count == 2 ? role->d1 : 0) ||
        t->type != role->type) {
      if (named_size && !named[0]) snprintf(named, named_size, "%s", role->name);
      differences++;
    }
  }
  if (visited) *visited = seen;
  return differences;
}

static uint32_t plan_u32(const uint8_t *plan, uint64_t offset) {
  const uint8_t *p = plan + offset;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void plan_put_u32(uint8_t *plan, uint64_t offset, uint32_t value) {
  plan[offset] = (uint8_t)(value & 0xffU);
  plan[offset + 1] = (uint8_t)((value >> 8) & 0xffU);
  plan[offset + 2] = (uint8_t)((value >> 16) & 0xffU);
  plan[offset + 3] = (uint8_t)((value >> 24) & 0xffU);
}

/* ------------------------------------------------------ the identity walk
 *
 * `walk_roles` above grades the struct against the graph contract's SHAPES,
 * and two roles can share a shape: `ffn_gate.weight` and `ffn_up.weight` are
 * both 5120 x 17408 PTQ1_0, so a translation that put each record in the
 * other's field would pass it. What tells them apart is the record itself --
 * its file offset is unique -- and the name the object gave that record's
 * role id.
 *
 * So this walk goes the other way: for every slot of the workspace, take the
 * role id and the layer the OBJECT wrote, turn the id into the object's own
 * name (decoded from its literal tables by the driver, not transcribed), and
 * require the field that name implies to hold exactly this record. That
 * grades `qwen35_slot`, the id -> field table, which nothing else here does.
 *
 * It is deliberately blind to the graph contract, and `walk_roles` is
 * deliberately blind to the workspace: the corrupted-record control below
 * goes red in `walk_roles` and stays green here (the struct still agrees with
 * the workspace it was built from), and a swapped field table goes red here
 * and stays green there. */
static int walk_slots(const struct aiueos_qwen35_model *model,
                      const uint8_t *tt_plan, uint64_t count,
                      uint64_t data_offset, int *visited,
                      char *named, size_t named_size) {
  int differences = 0;
  int seen = 0;
  if (named_size) named[0] = 0;
  for (uint64_t index = 0; index < count; index++) {
    const uint8_t *slot = tt_plan + 32 + index * TT_SLOT_BYTES;
    uint32_t id = plan_u32(slot, 0);
    uint32_t layer = plan_u32(slot, 4);
    const char *name = role_name(id);
    char where[96];
    if (!name) {
      snprintf(where, sizeof(where), "role id %u", id);
      if (named_size && !named[0]) snprintf(named, named_size, "%s", where);
      differences++;
      continue;
    }
    if (layer == AIUEOS_QWEN35_LAYER_COUNT)
      snprintf(where, sizeof(where), "%s", name);
    else
      snprintf(where, sizeof(where), "blk.%u.%s", layer, name);
    const struct aiueos_qwen35_tensor *tensor = 0;
    if (layer == AIUEOS_QWEN35_LAYER_COUNT) {
      size_t at = field_offset(model_fields,
                               sizeof(model_fields) / sizeof(model_fields[0]),
                               name);
      if (at != (size_t)-1) tensor = tensor_at(model, at);
    } else if (layer < AIUEOS_QWEN35_LAYER_COUNT) {
      const struct aiueos_qwen35_layer *l = &model->layers[layer];
      size_t at = field_offset(every_layer_fields,
                               sizeof(every_layer_fields) /
                                 sizeof(every_layer_fields[0]), name);
      if (at == (size_t)-1 && l->linear_attention)
        at = field_offset(linear_fields,
                          sizeof(linear_fields) / sizeof(linear_fields[0]),
                          name);
      if (at == (size_t)-1 && !l->linear_attention)
        at = field_offset(full_fields,
                          sizeof(full_fields) / sizeof(full_fields[0]), name);
      if (at != (size_t)-1) tensor = tensor_at(l, at);
    }
    if (!tensor) {
      if (named_size && !named[0])
        snprintf(named, named_size, "no field for %s", where);
      differences++;
      continue;
    }
    seen++;
    uint32_t d1 = plan_u32(slot, 16);
    uint64_t file_offset = (uint64_t)plan_u32(slot, 20) |
                           ((uint64_t)plan_u32(slot, 24) << 32);
    if (tensor->dimensions[0] != plan_u32(slot, 12) ||
        tensor->dimensions[1] != d1 ||
        tensor->dimension_count != (d1 ? 2U : 1U) ||
        tensor->type != plan_u32(slot, 8) ||
        tensor->offset != file_offset - data_offset ||
        tensor->storage_bytes != plan_u32(slot, 28) ||
        tensor->data != 0) {
      if (named_size && !named[0]) snprintf(named, named_size, "%s", where);
      differences++;
    }
  }
  if (visited) *visited = seen;
  return differences;
}

/* Every tensor the struct carries, found by its dimension count rather than
   by any table here: the translation writes `dimension_count` last for each
   record it accepts and zeroes the struct first, so this is the independent
   count of how many fields it filled. The extent walk rides along, because
   the tiling identity is about the same set. */
static uint32_t count_and_measure(const struct aiueos_qwen35_model *model,
                                  uint64_t *last_end) {
  const struct aiueos_qwen35_tensor *all[3 + AIUEOS_QWEN35_LAYER_COUNT * 24];
  uint32_t n = 0;
  uint64_t end = 0;
  all[n++] = &model->token_embedding;
  all[n++] = &model->output_norm;
  all[n++] = &model->output;
  for (uint32_t layer = 0; layer < AIUEOS_QWEN35_LAYER_COUNT; layer++) {
    const struct aiueos_qwen35_layer *l = &model->layers[layer];
    const struct aiueos_qwen35_tensor *fields[] = {
      &l->attention_norm, &l->post_attention_norm, &l->ffn_down, &l->ffn_gate,
      &l->ffn_up, &l->mixer.linear.gate, &l->mixer.linear.qkv,
      &l->mixer.linear.a, &l->mixer.linear.alpha, &l->mixer.linear.beta,
      &l->mixer.linear.conv1d, &l->mixer.linear.dt_bias, &l->mixer.linear.norm,
      &l->mixer.linear.output, &l->nextn.eh_projection,
      &l->nextn.embedding_norm, &l->nextn.hidden_norm,
      &l->nextn.shared_head_norm
    };
    /* The mixer is a union: under a full-attention layer the six full fields
       occupy the same bytes the nine linear ones would, so counting both arms
       would count those bytes twice. The arm the layer is in is the arm that
       exists. */
    const struct aiueos_qwen35_tensor *full_fields_in[] = {
      &l->mixer.full.key, &l->mixer.full.key_norm, &l->mixer.full.output,
      &l->mixer.full.query_gate, &l->mixer.full.query_norm, &l->mixer.full.value
    };
    for (uint32_t i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
      if (i >= 5 && i <= 13 && !l->linear_attention) continue;
      all[n++] = fields[i];
    }
    if (!l->linear_attention)
      for (uint32_t i = 0; i < 6; i++) all[n++] = full_fields_in[i];
  }
  uint32_t filled = 0;
  for (uint32_t i = 0; i < n; i++) {
    if (!all[i]->dimension_count) continue;
    filled++;
    uint64_t tensor_end = all[i]->offset + all[i]->storage_bytes;
    if (tensor_end > end) end = tensor_end;
  }
  if (last_end) *last_end = end;
  return filled;
}

static struct aiueos_qwen35_model translated;
static struct aiueos_qwen35_model refused;
static uint8_t kv_copy[KV_PLAN_BYTES];
static uint8_t tt_copy[TT_PLAN_BYTES];
static uint8_t stand_in_artifact[1];

/* One refusal control: a workspace with one thing changed, the translation
   required to refuse AND to report the reason literal the source names. */
static void refusal(const uint8_t *kv, const uint8_t *tt, uint64_t artifact,
                    int64_t reason, const char *what) {
  aiueos_qwen35_admission_verdict = 0;
  aiueos_qwen35_admission_stage = 0;
  int admitted = aiueos_qwen35_model_translate(
    stand_in_artifact, expect_scalar("data-offset"), artifact, kv, tt, &refused);
  char name[160];
  snprintf(name, sizeof(name), "%s is refused as %lld", what, (long long)reason);
  if (check(!admitted && aiueos_qwen35_admission_verdict == reason &&
            aiueos_qwen35_admission_stage == 4, name))
    printf("CONTROL %s REFUSED reason=%lld stage=%u\n", what,
           (long long)aiueos_qwen35_admission_verdict,
           aiueos_qwen35_admission_stage);
  else
    fprintf(stderr, "  admitted=%d reason=%lld stage=%u\n", admitted,
            (long long)aiueos_qwen35_admission_verdict,
            aiueos_qwen35_admission_stage);
}

int main(int argc, char **argv) {
  if (argc != 4) {
    fprintf(stderr,
            "usage: bonsai-runtime-translation EXPECTATIONS KV-PLAN TT-PLAN\n");
    return 2;
  }
  if (!load_expectations(argv[1])) {
    fprintf(stderr, "FAIL expectations unreadable: %s\n", argv[1]);
    return 2;
  }
  uint64_t kv_length = 0, tt_length = 0;
  uint8_t *kv_plan = read_file(argv[2], &kv_length);
  uint8_t *tt_plan = read_file(argv[3], &tt_length);
  if (!kv_plan || !tt_plan) {
    fprintf(stderr, "FAIL a workspace is unreadable\n");
    return 2;
  }
  check(kv_length == KV_PLAN_BYTES, "the kv workspace is the Bonsai length");
  check(tt_length == TT_PLAN_BYTES, "the tensor-table workspace is 28,160 bytes");
  check(role_count > 0 && scalar_count > 0, "the expectations are not empty");
  if (failures) return 1;

  uint64_t artifact_bytes = expect_scalar("artifact-bytes");
  uint64_t data_offset = expect_scalar("data-offset");
  uint64_t tensor_count = expect_scalar("tensor-count");

  /* The workspaces are the objects' -- the profile bit and the record count
     below are read back from them, so that a gate fed the WRONG pair of
     files says so instead of grading the Qwen3.8 profile a second time. */
  check((plan_u32(kv_plan, 124) >> 31) == 1U,
        "the kv workspace is the Bonsai profile");
  check(plan_u32(tt_plan, 0) == tensor_count,
        "the tensor-table workspace holds the contract's record count");

  aiueos_qwen35_admission_verdict = 0;
  aiueos_qwen35_admission_stage = 0;
  check(aiueos_qwen35_model_translate(stand_in_artifact, data_offset,
                                      artifact_bytes, kv_plan, tt_plan,
                                      &translated),
        "the Bonsai workspaces translate");
  if (failures) return 1;

  check(translated.tensor_count == tensor_count, "tensor count");
  check(translated.metadata_count == expect_scalar("metadata-count"),
        "metadata count");
  check(translated.metadata_end == expect_scalar("metadata-end"),
        "metadata end");
  check(translated.tensor_info_end == expect_scalar("tensor-info-end"),
        "tensor info end");
  check(translated.data_offset == data_offset, "data offset");
  check(translated.artifact_bytes == artifact_bytes, "artifact bytes");
  check(translated.block_count == expect_scalar("block-count"), "block count");
  check(translated.trunk_layer_count == expect_scalar("trunk-layers"),
        "trunk layers");
  check(translated.linear_layer_count == expect_scalar("linear-layers"),
        "linear-attention layers");
  check(translated.full_layer_count == expect_scalar("full-layers"),
        "full-attention layers");
  check(translated.nextn_layer_count == expect_scalar("nextn-layers"),
        "nextn layers");
  check(translated.full_attention_interval ==
          expect_scalar("full-attention-interval"), "full attention interval");
  check(translated.context_length == expect_scalar("context"), "context length");
  check(translated.embedding_length == expect_scalar("embedding"),
        "embedding length");
  check(translated.feed_forward_length == expect_scalar("feed-forward"),
        "feed forward length");
  check(translated.vocab_size == expect_scalar("vocabulary"), "vocabulary");
  check(translated.attention_head_count == expect_scalar("attention-query-heads"),
        "attention head count");
  check(translated.attention_kv_head_count ==
          expect_scalar("attention-kv-heads"), "attention kv head count");
  check(translated.attention_key_length ==
          expect_scalar("attention-head-dimension"), "attention key length");
  check(translated.attention_value_length ==
          expect_scalar("attention-head-dimension"), "attention value length");
  check(translated.linear_key_head_count == expect_scalar("linear-key-heads"),
        "linear key heads");
  check(translated.linear_value_head_count ==
          expect_scalar("linear-value-heads"), "linear value heads");
  check(translated.linear_state_size == expect_scalar("linear-state-size"),
        "linear state size");
  check(translated.linear_inner_size == expect_scalar("linear-inner-size"),
        "linear inner size");
  check(translated.linear_conv_kernel ==
          expect_scalar("linear-convolution-kernel"), "linear conv kernel");
  check(translated.rope_dimension_count == expect_scalar("rope-dimensions"),
        "rope dimension count");
  check(translated.rope_sections[0] == expect_scalar("rope-section-0") &&
        translated.rope_sections[1] == expect_scalar("rope-section-1") &&
        translated.rope_sections[2] == expect_scalar("rope-section-2") &&
        translated.rope_sections[3] == expect_scalar("rope-section-3"),
        "rope sections");

  /* The histogram, in the slots the counter table has: PTQ1_0 is ggml type
     143 and counts in slot 31. Every other slot must be zero -- an artifact
     of three types that also left a count in Q4_K's slot would be a record
     translated into the wrong type and this is where that shows. */
  {
    uint64_t f32 = expect_scalar("type-count-f32");
    uint64_t bf16 = expect_scalar("type-count-bf16");
    uint64_t ptq = expect_scalar("type-count-ptq1-0");
    uint32_t bf16_type = (uint32_t)expect_scalar("bf16-ggml-type");
    check(translated.ggml_type_counts[AIUEOS_GGML_F32] == f32, "F32 count");
    check(translated.ggml_type_counts[bf16_type] == bf16, "BF16 count");
    check(translated.ggml_type_counts[AIUEOS_QWEN35_PTQ1_0_TYPE_SLOT] == ptq,
          "PTQ1_0 count in slot 31");
    uint64_t total = 0;
    int other = 0;
    for (uint32_t slot = 0; slot < AIUEOS_QWEN35_TYPE_SLOT_COUNT; slot++) {
      total += translated.ggml_type_counts[slot];
      if (slot != AIUEOS_GGML_F32 && slot != bf16_type &&
          slot != AIUEOS_QWEN35_PTQ1_0_TYPE_SLOT &&
          translated.ggml_type_counts[slot])
        other = 1;
    }
    check(!other, "no count in any other type slot");
    check(total == tensor_count, "the histogram sums to the record count");
    check(translated.token_embedding.type ==
            (uint32_t)expect_scalar("ptq1-0-ggml-type"),
          "token_embd keeps the artifact's own ggml type, not the slot");
  }

  /* The MTP head Bonsai does not have. Layer 64 must be exactly as the clear
     left it: this artifact has 64 blocks and the struct has 65. */
  {
    static const struct aiueos_qwen35_layer zero;
    check(memcmp(&translated.layers[AIUEOS_QWEN35_TRUNK_LAYER_COUNT], &zero,
                 sizeof(zero)) == 0,
          "the absent MTP layer is untouched");
  }

  {
    int visited = 0;
    char named[160];
    int differences = walk_roles(&translated, &visited, named, sizeof(named));
    printf("SCANNED %d role placements in %u roles, DIFFER %d\n", visited,
           role_count, differences);
    if (differences) fprintf(stderr, "FAIL first differing tensor: %s\n", named);
    check(differences == 0, "every role landed in its field with its shape");
    check((uint64_t)visited == tensor_count,
          "the role walk visited one field per record");
  }

  {
    int visited = 0;
    char named[160];
    int differences = walk_slots(&translated, tt_plan, tensor_count,
                                 data_offset, &visited, named, sizeof(named));
    printf("SCANNED %d workspace records against their fields, DIFFER %d\n",
           visited, differences);
    if (differences) fprintf(stderr, "FAIL first differing record: %s\n", named);
    check(differences == 0,
          "every record landed in the field its role id names");
    check((uint64_t)visited == tensor_count,
          "the identity walk reached one field per record");
    check(role_id_count == 27U, "the object's 27 role ids were decoded");
  }

  {
    uint64_t last_end = 0;
    uint32_t filled = count_and_measure(&translated, &last_end);
    printf("SCANNED %u filled tensor fields, last extent ends at %llu\n",
           filled, (unsigned long long)last_end);
    check(filled == tensor_count, "the struct carries one tensor per record");
    check(last_end == artifact_bytes - data_offset,
          "the extents still tile the artifact after the offset subtraction");
    check(translated.layers[63].post_attention_norm.offset ==
            expect_scalar("last-tensor-offset") &&
          translated.layers[63].post_attention_norm.offset +
            translated.layers[63].post_attention_norm.storage_bytes ==
            expect_scalar("last-tensor-end"),
          "the contract's last tensor is where the contract says");
  }

  /* ------------------------------------------------------------- controls */

  /* One record's second dimension, changed in a copy of the workspace: the
     walk must go red and must name the tensor. */
  {
    memcpy(tt_copy, tt_plan, TT_PLAN_BYTES);
    uint64_t slot_at = 0;
    for (uint64_t index = 0; index < tensor_count; index++) {
      uint64_t at = 32 + index * TT_SLOT_BYTES;
      if (plan_u32(tt_copy, at) == 7 && plan_u32(tt_copy, at + 4) == 0) {
        slot_at = at;
        break;
      }
    }
    check(slot_at != 0, "the workspace holds role 7 in layer 0");
    if (slot_at) {
      uint32_t before = plan_u32(tt_copy, slot_at + 16);
      plan_put_u32(tt_copy, slot_at + 16, before + 1);
      static struct aiueos_qwen35_model corrupted;
      check(aiueos_qwen35_model_translate(stand_in_artifact, data_offset,
                                          artifact_bytes, kv_plan, tt_copy,
                                          &corrupted),
            "the corrupted workspace still translates");
      char named[160];
      int visited = 0;
      int differences = walk_roles(&corrupted, &visited, named, sizeof(named));
      printf("CONTROL corrupt=blk.0.attn_qkv.weight.d1 %u->%u DIFFER %d NAMED %s\n",
             before, before + 1, differences, named);
      check(differences == 1, "exactly one placement differs");
      check(strcmp(named, "blk.0.attn_qkv.weight") == 0,
            "the walk names the corrupted tensor");
      /* And the identity walk must NOT see it: the struct still agrees with
         the workspace it was built from, which is what makes the two walks
         two measurements rather than one made twice. */
      int corrupt_visited = 0;
      char identity_named[160];
      int identity = walk_slots(&corrupted, tt_copy, tensor_count, data_offset,
                                &corrupt_visited, identity_named,
                                sizeof(identity_named));
      check(identity == 0,
            "the identity walk agrees with the corrupted workspace");
    }
  }

  /* The eight refusals. Each is one change to one copy, and the reason
     literal is asserted, not merely "it said no". */
  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  memcpy(tt_copy, tt_plan, TT_PLAN_BYTES);
  plan_put_u32(kv_copy, 124, plan_u32(kv_copy, 124) & 0x7fffffffU);
  refusal(kv_copy, tt_plan, artifact_bytes, -106,
          "the Bonsai table under the Qwen3.8 profile bit");

  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  memcpy(tt_copy, tt_plan, TT_PLAN_BYTES);
  plan_put_u32(tt_copy, 0, (uint32_t)tensor_count - 1U);
  refusal(kv_plan, tt_copy, artifact_bytes, -106,
          "a record count that is not the profile's");

  refusal(kv_plan, tt_plan, artifact_bytes - 1, -107,
          "an artifact length that is not the profile's");

  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  plan_put_u32(kv_copy, 0, plan_u32(kv_copy, 0) + 32U);
  refusal(kv_copy, tt_plan, artifact_bytes, -108,
          "a metadata end that is not the profile's");

  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  plan_put_u32(kv_copy, 4, plan_u32(kv_copy, 4) + 1U);
  refusal(kv_copy, tt_plan, artifact_bytes, -109,
          "a block count that leaves more than 64 trunk layers");

  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  plan_put_u32(kv_copy, 56, 0U);
  refusal(kv_copy, tt_plan, artifact_bytes, -110,
          "a zero full-attention interval");

  memcpy(kv_copy, kv_plan, KV_PLAN_BYTES);
  plan_put_u32(kv_copy, 56, 2U);
  refusal(kv_copy, tt_plan, artifact_bytes, -111,
          "an interval whose schedule is not the one the object counted");

  memcpy(tt_copy, tt_plan, TT_PLAN_BYTES);
  plan_put_u32(tt_copy, 32 + 8, AIUEOS_QWEN35_MAX_GGML_TYPE + 1U);
  refusal(kv_plan, tt_copy, artifact_bytes, -105,
          "a ggml type with no counter slot");

  memcpy(tt_copy, tt_plan, TT_PLAN_BYTES);
  plan_put_u32(tt_copy, 32 + TT_SLOT_BYTES, plan_u32(tt_copy, 32));
  plan_put_u32(tt_copy, 32 + TT_SLOT_BYTES + 4, plan_u32(tt_copy, 36));
  refusal(kv_plan, tt_copy, artifact_bytes, -103,
          "two records claiming one field");

  /* Nothing in the expectations may go unread. */
  for (uint32_t i = 0; i < scalar_count; i++)
    if (!scalars[i].used) {
      fprintf(stderr, "FAIL the expectation %s was never asserted\n",
              scalars[i].name);
      failures++;
    }

  free(kv_plan);
  free(tt_plan);
  if (failures) {
    fprintf(stderr, "FAILURES %d\n", failures);
    return 1;
  }
  printf("AIUEOS_BONSAI_TRANSLATION_OK tensors=%llu scalars=%u roles=%u "
         "ids=%u refusals=9 workspace=kotoba-oracle "
         "expectation=graph-contract\n",
         (unsigned long long)tensor_count, scalar_count, role_count,
         role_id_count);
  return 0;
}
