/* SPDX-License-Identifier: Apache-2.0 */
/* Two gates in one binary.
 *
 * The first is the original one: the C reference parser
 * (`kernel/qwen35_runtime.c` with no defines) admits the exact-contract
 * fixture and refuses four mutations of it.
 *
 * The second is new. `kernel/qwen35_runtime.c` compiled with
 * -DAIUEOS_QWEN35_KOTOBA_ADMISSION -DAIUEOS_QWEN35_TRANSLATION_ONLY is ONLY
 * the workspace -> struct translation of the Kotoba admission, so it links
 * here beside the reference parser on a machine that cannot execute an
 * x86-64 ET_REL object. Fed the two workspaces a real run of the objects
 * produced -- committed under tests/fixtures/ and pinned in both directions by
 * aiueos.qwen35-{gguf-kv-scan,tensor-table}-parity-test -- it must build a
 * `struct aiueos_qwen35_model` IDENTICAL to the reference parser's, field by
 * field and byte for byte.
 *
 * ADR-0145 landed that translation without ever running it: the delegation
 * linked, the objects passed their oracle, and the assignment between them was
 * checked by reading. Reading does not catch a field copied from the wrong
 * workspace offset, because both are plausible little-endian words.
 *
 * The last case is the control. It corrupts ONE field of ONE record in a copy
 * of the tensor-table workspace and requires the comparison to report a
 * mismatch AND to name the field; a comparison that cannot go red is not
 * evidence that it went green for a reason.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../kernel/qwen35_runtime.h"

#define KV_PLAN_BYTES 128U
#define TT_PLAN_BYTES 28160U
#define TT_SLOT_BYTES 32U

static int check(int condition, const char *name) {
  if (condition) return 1;
  fprintf(stderr, "FAIL %s\n", name);
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

static uint8_t *find_bytes(uint8_t *bytes, uint64_t length,
                           const char *needle) {
  uint64_t needle_length = 0;
  while (needle[needle_length]) needle_length++;
  for (uint64_t i = 0; i + needle_length <= length; i++) {
    uint64_t j = 0;
    while (j < needle_length && bytes[i + j] == (uint8_t)needle[j]) j++;
    if (j == needle_length) return bytes + i;
  }
  return 0;
}

/* ------------------------------------------------------------ the comparison
 *
 * The 34 top-level members of `struct aiueos_qwen35_model`, named. A memcmp of
 * the whole struct is the stronger assertion and is made too, but memcmp says
 * only "different"; a translation defect is a field, and the field is what the
 * report has to say. Both structs are zeroed over sizeof before use, so the
 * padding between members is zero in both and the whole-struct compare is
 * exact rather than approximately exact. */
struct field_desc {
  const char *name;
  size_t offset;
  size_t size;
};

#define FIELD(m) \
  { #m, offsetof(struct aiueos_qwen35_model, m), \
    sizeof(((struct aiueos_qwen35_model *)0)->m) }

static const struct field_desc model_fields[] = {
  FIELD(bytes), FIELD(accessible_bytes), FIELD(artifact_bytes),
  FIELD(metadata_end), FIELD(tensor_info_end), FIELD(data_offset),
  FIELD(tensor_count), FIELD(metadata_count), FIELD(block_count),
  FIELD(trunk_layer_count), FIELD(context_length), FIELD(embedding_length),
  FIELD(feed_forward_length), FIELD(vocab_size), FIELD(attention_head_count),
  FIELD(attention_kv_head_count), FIELD(attention_key_length),
  FIELD(attention_value_length), FIELD(linear_key_head_count),
  FIELD(linear_value_head_count), FIELD(linear_state_size),
  FIELD(linear_inner_size), FIELD(linear_conv_kernel),
  FIELD(full_attention_interval), FIELD(rope_dimension_count),
  FIELD(rope_sections), FIELD(nextn_layer_count), FIELD(linear_layer_count),
  FIELD(full_layer_count), FIELD(ggml_type_counts), FIELD(token_embedding),
  FIELD(output_norm), FIELD(output), FIELD(layers)
};

#define MODEL_FIELD_COUNT (sizeof(model_fields) / sizeof(model_fields[0]))

/* Tensor slots inside one layer, so a mismatch inside `layers` can be named
   `layers[12].mixer.linear.qkv` rather than `layers`. `mixer.linear` and
   `mixer.full` are a union, so only the arm the layer actually uses is
   compared -- naming the other arm would name a field the file never had. */
struct tensor_desc {
  const char *name;
  size_t offset;
};

#define LAYER_TENSOR(m) { #m, offsetof(struct aiueos_qwen35_layer, m) }

static const struct tensor_desc common_tensors[] = {
  LAYER_TENSOR(attention_norm), LAYER_TENSOR(post_attention_norm),
  LAYER_TENSOR(ffn_down), LAYER_TENSOR(ffn_gate), LAYER_TENSOR(ffn_up)
};
static const struct tensor_desc linear_tensors[] = {
  LAYER_TENSOR(mixer.linear.gate), LAYER_TENSOR(mixer.linear.qkv),
  LAYER_TENSOR(mixer.linear.a), LAYER_TENSOR(mixer.linear.alpha),
  LAYER_TENSOR(mixer.linear.beta), LAYER_TENSOR(mixer.linear.conv1d),
  LAYER_TENSOR(mixer.linear.dt_bias), LAYER_TENSOR(mixer.linear.norm),
  LAYER_TENSOR(mixer.linear.output)
};
static const struct tensor_desc full_tensors[] = {
  LAYER_TENSOR(mixer.full.key), LAYER_TENSOR(mixer.full.key_norm),
  LAYER_TENSOR(mixer.full.output), LAYER_TENSOR(mixer.full.query_gate),
  LAYER_TENSOR(mixer.full.query_norm), LAYER_TENSOR(mixer.full.value)
};
static const struct tensor_desc nextn_tensors[] = {
  LAYER_TENSOR(nextn.eh_projection), LAYER_TENSOR(nextn.embedding_norm),
  LAYER_TENSOR(nextn.hidden_norm), LAYER_TENSOR(nextn.shared_head_norm)
};

static int compare_layer_group(const struct aiueos_qwen35_layer *a,
                               const struct aiueos_qwen35_layer *b,
                               const struct tensor_desc *group, size_t count,
                               uint32_t index, char *first_name,
                               size_t first_name_size) {
  int differences = 0;
  for (size_t i = 0; i < count; i++) {
    if (memcmp((const uint8_t *)a + group[i].offset,
               (const uint8_t *)b + group[i].offset,
               sizeof(struct aiueos_qwen35_tensor)) != 0) {
      if (!differences && first_name)
        snprintf(first_name, first_name_size, "layers[%u].%s", index,
                 group[i].name);
      differences++;
    }
  }
  return differences;
}

/* Name the first differing tensor inside `layers`, and count how many differ.
   Returns the number of differing tensor slots. */
static int compare_layers(const struct aiueos_qwen35_model *a,
                          const struct aiueos_qwen35_model *b,
                          char *first_name, size_t first_name_size) {
  int differences = 0;
  for (uint32_t index = 0; index < AIUEOS_QWEN35_LAYER_COUNT; index++) {
    const struct aiueos_qwen35_layer *la = &a->layers[index];
    const struct aiueos_qwen35_layer *lb = &b->layers[index];
    char *name = differences ? 0 : first_name;
    if (la->linear_attention != lb->linear_attention) {
      if (name) {
        snprintf(name, first_name_size, "layers[%u].linear_attention", index);
        name = 0;
      }
      differences++;
    }
    int group = compare_layer_group(
      la, lb, common_tensors,
      sizeof(common_tensors) / sizeof(common_tensors[0]), index, name,
      first_name_size);
    if (group) name = 0;
    differences += group;
    if (la->linear_attention)
      group = compare_layer_group(
        la, lb, linear_tensors,
        sizeof(linear_tensors) / sizeof(linear_tensors[0]), index, name,
        first_name_size);
    else
      group = compare_layer_group(
        la, lb, full_tensors,
        sizeof(full_tensors) / sizeof(full_tensors[0]), index, name,
        first_name_size);
    if (group) name = 0;
    differences += group;
    if (index == AIUEOS_QWEN35_TRUNK_LAYER_COUNT)
      differences += compare_layer_group(
        la, lb, nextn_tensors,
        sizeof(nextn_tensors) / sizeof(nextn_tensors[0]), index, name,
        first_name_size);
  }
  return differences;
}

/* Compare the two structs field by field. Returns the number of differing
   top-level fields and, when `first_name` is given, names the first one (for
   `layers`, the tensor slot inside it). `matched` receives the number that
   agreed, so a run that compared nothing cannot read as a pass. */
static int compare_models(const struct aiueos_qwen35_model *a,
                          const struct aiueos_qwen35_model *b, int *matched,
                          char *first_name, size_t first_name_size) {
  int differences = 0;
  int agreed = 0;
  if (first_name && first_name_size) first_name[0] = 0;
  for (size_t i = 0; i < MODEL_FIELD_COUNT; i++) {
    if (memcmp((const uint8_t *)a + model_fields[i].offset,
               (const uint8_t *)b + model_fields[i].offset,
               model_fields[i].size) == 0) {
      agreed++;
      continue;
    }
    if (!differences && first_name) {
      if (strcmp(model_fields[i].name, "layers") == 0)
        (void)compare_layers(a, b, first_name, first_name_size);
      else
        snprintf(first_name, first_name_size, "%s", model_fields[i].name);
    }
    differences++;
  }
  if (matched) *matched = agreed;
  return differences;
}

static struct aiueos_qwen35_model model;
static struct aiueos_qwen35_model reference;
static struct aiueos_qwen35_model translated;
static uint8_t corrupt_tt_plan[TT_PLAN_BYTES];

static uint32_t plan_u32(const uint8_t *plan, uint64_t offset) {
  const uint8_t *p = plan + offset;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

int main(int argc, char **argv) {
  if (argc != 4) {
    fprintf(stderr,
            "usage: qwen35-runtime-model HEADER-FIXTURE KV-PLAN TT-PLAN\n");
    return 2;
  }
  uint64_t length = 0;
  uint8_t *bytes = read_file(argv[1], &length);
  if (!bytes) return 2;
  uint64_t kv_length = 0;
  uint8_t *kv_plan = read_file(argv[2], &kv_length);
  if (!kv_plan) {
    fprintf(stderr, "FAIL kv workspace unreadable: %s\n", argv[2]);
    return 2;
  }
  uint64_t tt_length = 0;
  uint8_t *tt_plan = read_file(argv[3], &tt_length);
  if (!tt_plan) {
    fprintf(stderr, "FAIL tensor-table workspace unreadable: %s\n", argv[3]);
    return 2;
  }
  int ok = 1;
  ok &= check(length == AIUEOS_QWEN35_DATA_OFFSET, "fixture prefix length");
  ok &= check(kv_length == KV_PLAN_BYTES, "kv workspace length");
  ok &= check(tt_length == TT_PLAN_BYTES, "tensor-table workspace length");
  ok &= check(aiueos_qwen35_model_parse(
                bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES, &model),
              "exact contract admitted");
  ok &= check(model.tensor_count == AIUEOS_QWEN35_TENSOR_COUNT &&
              model.block_count == AIUEOS_QWEN35_LAYER_COUNT &&
              model.trunk_layer_count == AIUEOS_QWEN35_TRUNK_LAYER_COUNT,
              "model counts");
  ok &= check(model.linear_layer_count == AIUEOS_QWEN35_LINEAR_LAYER_COUNT &&
              model.full_layer_count == AIUEOS_QWEN35_FULL_LAYER_COUNT &&
              model.nextn_layer_count == 1,
              "hybrid layer schedule");
  ok &= check(model.token_embedding.offset == 715182080ULL &&
              model.output.offset == 0 &&
              model.layers[0].mixer.linear.qkv.offset == 1149091840ULL &&
              model.layers[64].post_attention_norm.offset == 10923843584ULL,
              "representative tensor offsets");
  ok &= check(model.token_embedding.data == 0 && model.output.data == 0,
              "prefix parse does not fabricate data pointers");
  ok &= check(!aiueos_qwen35_model_bind(&model, bytes, length),
              "truncated mapping bind refused");
  ok &= check(!aiueos_qwen35_model_parse(
                bytes, length - 32, AIUEOS_QWEN35_ARTIFACT_BYTES, &model),
              "truncated tensor table refused");
  ok &= check(!aiueos_qwen35_model_parse(
                bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES - 1, &model),
              "wrong artifact length refused");

  uint8_t *architecture = find_bytes(bytes, length, "qwen35");
  ok &= check(architecture != 0, "architecture fixture located");
  if (architecture) {
    uint8_t saved = architecture[5];
    architecture[5] = '4';
    ok &= check(!aiueos_qwen35_model_parse(
                  bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES, &model),
                "wrong architecture refused");
    architecture[5] = saved;
  }

  /* ---------------------------------------------------------- translation */

  ok &= check(aiueos_qwen35_model_parse(
                bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES, &reference),
              "reference parse for the translation comparison");
  ok &= check(aiueos_qwen35_model_translate(
                bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES,
                kv_plan, tt_plan, &translated),
              "translation admitted the objects' workspaces");
  ok &= check(MODEL_FIELD_COUNT == 34, "the field table names 34 fields");
  ok &= check(model_fields[MODEL_FIELD_COUNT - 1].offset +
                model_fields[MODEL_FIELD_COUNT - 1].size ==
                sizeof(struct aiueos_qwen35_model),
              "the field table reaches the end of the struct");
  {
    int matched = 0;
    char named[128];
    int differences = compare_models(&reference, &translated, &matched,
                                     named, sizeof(named));
    printf("SCANNED %d fields MATCH %d DIFFER %d\n",
           (int)MODEL_FIELD_COUNT, matched, differences);
    if (differences) fprintf(stderr, "FAIL first differing field: %s\n", named);
    ok &= check(differences == 0, "translation agrees with the reference");
    ok &= check(matched == (int)MODEL_FIELD_COUNT,
                "every field was actually compared");
    ok &= check(memcmp(&reference, &translated, sizeof(reference)) == 0,
                "translation is byte-identical to the reference");
  }

  /* The control. One field of one record, changed in a copy of the workspace
     the objects produced: `blk.0.attn_qkv.weight` is role 7 in layer 0, and
     its second dimension moves 10240 -> 10241. Nothing else in the workspace
     moves, so exactly one tensor slot may differ and the comparison has to
     name it. A comparison that stayed green here would be measuring nothing. */
  {
    memcpy(corrupt_tt_plan, tt_plan, TT_PLAN_BYTES);
    uint64_t slot_at = 0;
    for (uint64_t index = 0; index < AIUEOS_QWEN35_TENSOR_COUNT; index++) {
      uint64_t at = 32 + index * TT_SLOT_BYTES;
      if (plan_u32(corrupt_tt_plan, at) == 7 &&
          plan_u32(corrupt_tt_plan, at + 4) == 0) {
        slot_at = at;
        break;
      }
    }
    ok &= check(slot_at != 0, "the workspace holds role 7 in layer 0");
    if (slot_at) {
      ok &= check(plan_u32(corrupt_tt_plan, slot_at + 16) == 10240,
                  "blk.0.attn_qkv.weight is 5120 x 10240 in the workspace");
      corrupt_tt_plan[slot_at + 16] = 0x01; /* 10240 -> 10241 */
      static struct aiueos_qwen35_model corrupted;
      ok &= check(aiueos_qwen35_model_translate(
                    bytes, length, AIUEOS_QWEN35_ARTIFACT_BYTES,
                    kv_plan, corrupt_tt_plan, &corrupted),
                  "the corrupted workspace still translates");
      int matched = 0;
      char named[128];
      int differences = compare_models(&reference, &corrupted, &matched,
                                       named, sizeof(named));
      printf("CONTROL corrupt=blk.0.attn_qkv.weight.d1 DIFFER %d NAMED %s\n",
             differences, named);
      ok &= check(differences == 1, "exactly one top-level field differs");
      ok &= check(strcmp(named, "layers[0].mixer.linear.qkv") == 0,
                  "the comparison names the corrupted tensor");
    }
  }

  free(bytes);
  free(kv_plan);
  free(tt_plan);
  if (!ok) return 1;
  puts("AIUEOS_QWEN35_RUNTIME_MODEL_OK gguf-v3 tensors=866 trunk=64 linear=48 full=16 mtp=1 bind=read-only");
  puts("AIUEOS_QWEN35_TRANSLATION_OK fields=34 workspace=kotoba-oracle struct=byte-identical control=named");
  return 0;
}
