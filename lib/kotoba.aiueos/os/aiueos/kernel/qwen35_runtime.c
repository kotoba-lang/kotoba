/* SPDX-License-Identifier: Apache-2.0 */
#include "qwen35_runtime.h"

/* The GGUF admission moved to three Kotoba objects (ADR-0145). This file now
   holds TWO implementations of `aiueos_qwen35_model_parse` and the build
   chooses one:

     AIUEOS_QWEN35_KOTOBA_ADMISSION defined   -- delegate to the objects.
                                                 build-uefi.sh defines it for
                                                 every profile that compiles
                                                 this file, so NO IMAGE
                                                 CONTAINS C GGUF PARSING.
     undefined                               -- the C parser below. It is the
                                                 host reference that
                                                 scripts/smoke-qwen35-runtime.sh
                                                 and tests/qwen35_runtime_model.c
                                                 exercise, because this
                                                 workstation is aarch64 and the
                                                 objects are x86-64 ET_REL.

   The `#else` branch is NOT a runtime fallback. Nothing selects it at run
   time and no shipped artifact contains it; it is the reference the oracle
   for those objects is checked against, kept compilable so the fixture and
   the four representative tensor offsets stay gated on a machine that cannot
   execute the objects.

   A third switch, AIUEOS_QWEN35_TRANSLATION_ONLY, compiles ONLY the
   workspace -> struct translation out of the delegating branch: no externs, no
   parse, no bind. It exists so the host gate can link that translation
   alongside the reference parser and compare the two structs; it is never set
   by a build that produces an image. */
#if defined(AIUEOS_QWEN35_TRANSLATION_ONLY) && \
    !defined(AIUEOS_QWEN35_KOTOBA_ADMISSION)
#error "AIUEOS_QWEN35_TRANSLATION_ONLY requires AIUEOS_QWEN35_KOTOBA_ADMISSION"
#endif
#ifndef AIUEOS_QWEN35_KOTOBA_ADMISSION
enum gguf_value_type {
  GGUF_UINT8 = 0,
  GGUF_INT8 = 1,
  GGUF_UINT16 = 2,
  GGUF_INT16 = 3,
  GGUF_UINT32 = 4,
  GGUF_INT32 = 5,
  GGUF_FLOAT32 = 6,
  GGUF_BOOL = 7,
  GGUF_STRING = 8,
  GGUF_ARRAY = 9,
  GGUF_UINT64 = 10,
  GGUF_INT64 = 11,
  GGUF_FLOAT64 = 12
};

struct reader {
  const uint8_t *bytes;
  uint64_t length;
  uint64_t position;
  int valid;
};

struct string_view {
  const uint8_t *bytes;
  uint64_t length;
};

static uint32_t read_u32(struct reader *reader) {
  if (!reader->valid || reader->position > reader->length ||
      reader->length - reader->position < 4) {
    reader->valid = 0;
    return 0;
  }
  const uint8_t *p = reader->bytes + reader->position;
  reader->position += 4;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint64_t read_u64(struct reader *reader) {
  uint64_t low = read_u32(reader);
  uint64_t high = read_u32(reader);
  return low | (high << 32);
}

static float read_f32(struct reader *reader) {
  union { uint32_t bits; float value; } decoded;
  decoded.bits = read_u32(reader);
  return decoded.value;
}

static int skip_bytes(struct reader *reader, uint64_t amount) {
  if (!reader->valid || reader->position > reader->length ||
      amount > reader->length - reader->position) {
    reader->valid = 0;
    return 0;
  }
  reader->position += amount;
  return 1;
}

static struct string_view read_string(struct reader *reader) {
  struct string_view result = {0};
  uint64_t length = read_u64(reader);
  if (!reader->valid || !skip_bytes(reader, length)) return result;
  result.bytes = reader->bytes + reader->position - length;
  result.length = length;
  return result;
}

static int string_is(struct string_view value, const char *expected) {
  uint64_t length = 0;
  while (expected[length]) length++;
  if (value.length != length) return 0;
  for (uint64_t i = 0; i < length; i++)
    if (value.bytes[i] != (uint8_t)expected[i]) return 0;
  return 1;
}

static int string_starts(struct string_view value, const char *prefix,
                         uint64_t *prefix_length) {
  uint64_t length = 0;
  while (prefix[length]) length++;
  if (value.length < length) return 0;
  for (uint64_t i = 0; i < length; i++)
    if (value.bytes[i] != (uint8_t)prefix[i]) return 0;
  if (prefix_length) *prefix_length = length;
  return 1;
}

static uint64_t scalar_size(uint32_t type) {
  switch (type) {
    case GGUF_UINT8:
    case GGUF_INT8:
    case GGUF_BOOL: return 1;
    case GGUF_UINT16:
    case GGUF_INT16: return 2;
    case GGUF_UINT32:
    case GGUF_INT32:
    case GGUF_FLOAT32: return 4;
    case GGUF_UINT64:
    case GGUF_INT64:
    case GGUF_FLOAT64: return 8;
    default: return 0;
  }
}

static int skip_value(struct reader *reader, uint32_t type, uint32_t depth) {
  uint64_t size = scalar_size(type);
  if (size) return skip_bytes(reader, size);
  if (type == GGUF_STRING) {
    (void)read_string(reader);
    return reader->valid;
  }
  if (type != GGUF_ARRAY || depth >= 2) return 0;
  uint32_t element_type = read_u32(reader);
  uint64_t count = read_u64(reader);
  if (!reader->valid || count > 1000000ULL) return 0;
  size = scalar_size(element_type);
  if (size) {
    if (count && size > UINT64_MAX / count) return 0;
    return skip_bytes(reader, size * count);
  }
  for (uint64_t i = 0; i < count; i++)
    if (!skip_value(reader, element_type, depth + 1)) return 0;
  return 1;
}

static int read_expected_u32(struct reader *reader, uint32_t type,
                             uint32_t *destination) {
  if (type != GGUF_UINT32) return 0;
  *destination = read_u32(reader);
  return reader->valid;
}

static int read_expected_string(struct reader *reader, uint32_t type,
                                const char *expected) {
  return type == GGUF_STRING && string_is(read_string(reader), expected) &&
         reader->valid;
}

static int read_expected_array_length(struct reader *reader, uint32_t type,
                                      uint32_t expected_element_type,
                                      uint64_t expected_count) {
  if (type != GGUF_ARRAY) return 0;
  uint32_t element_type = read_u32(reader);
  uint64_t count = read_u64(reader);
  if (!reader->valid || element_type != expected_element_type ||
      count != expected_count) return 0;
  uint64_t size = scalar_size(element_type);
  if (size) return skip_bytes(reader, size * count);
  for (uint64_t i = 0; i < count; i++)
    if (!skip_value(reader, element_type, 1)) return 0;
  return 1;
}

static int parse_metadata(struct reader *reader,
                          struct aiueos_qwen35_model *model) {
  uint64_t required = 0;
  for (uint64_t i = 0; i < model->metadata_count; i++) {
    struct string_view key = read_string(reader);
    uint32_t type = read_u32(reader);
    if (!reader->valid) return 0;
    if (string_is(key, "general.architecture")) {
      if (!read_expected_string(reader, type, "qwen35")) return 0;
      required |= 1ULL << 0;
    } else if (string_is(key, "general.name")) {
      if (!read_expected_string(reader, type, "Qwen3.8-27B")) return 0;
      required |= 1ULL << 1;
    } else if (string_is(key, "qwen35.block_count")) {
      if (!read_expected_u32(reader, type, &model->block_count)) return 0;
      required |= 1ULL << 2;
    } else if (string_is(key, "qwen35.context_length")) {
      if (!read_expected_u32(reader, type, &model->context_length)) return 0;
      required |= 1ULL << 3;
    } else if (string_is(key, "qwen35.embedding_length")) {
      if (!read_expected_u32(reader, type, &model->embedding_length)) return 0;
      required |= 1ULL << 4;
    } else if (string_is(key, "qwen35.feed_forward_length")) {
      if (!read_expected_u32(reader, type, &model->feed_forward_length)) return 0;
      required |= 1ULL << 5;
    } else if (string_is(key, "qwen35.attention.head_count")) {
      if (!read_expected_u32(reader, type, &model->attention_head_count)) return 0;
      required |= 1ULL << 6;
    } else if (string_is(key, "qwen35.attention.head_count_kv")) {
      if (!read_expected_u32(reader, type, &model->attention_kv_head_count)) return 0;
      required |= 1ULL << 7;
    } else if (string_is(key, "qwen35.rope.dimension_sections")) {
      if (type != GGUF_ARRAY || read_u32(reader) != GGUF_INT32 ||
          read_u64(reader) != 4) return 0;
      for (uint32_t section = 0; section < 4; section++)
        model->rope_sections[section] = read_u32(reader);
      required |= 1ULL << 8;
    } else if (string_is(key, "qwen35.rope.freq_base")) {
      if (type != GGUF_FLOAT32 || read_f32(reader) != 10000000.0f) return 0;
      required |= 1ULL << 9;
    } else if (string_is(key, "qwen35.attention.layer_norm_rms_epsilon")) {
      if (type != GGUF_FLOAT32) return 0;
      float epsilon = read_f32(reader);
      if (epsilon < 0.0000009f || epsilon > 0.0000011f) return 0;
      required |= 1ULL << 10;
    } else if (string_is(key, "qwen35.attention.key_length")) {
      if (!read_expected_u32(reader, type, &model->attention_key_length)) return 0;
      required |= 1ULL << 11;
    } else if (string_is(key, "qwen35.attention.value_length")) {
      if (!read_expected_u32(reader, type, &model->attention_value_length)) return 0;
      required |= 1ULL << 12;
    } else if (string_is(key, "qwen35.nextn_predict_layers")) {
      if (!read_expected_u32(reader, type, &model->nextn_layer_count)) return 0;
      required |= 1ULL << 13;
    } else if (string_is(key, "qwen35.ssm.conv_kernel")) {
      if (!read_expected_u32(reader, type, &model->linear_conv_kernel)) return 0;
      required |= 1ULL << 14;
    } else if (string_is(key, "qwen35.ssm.state_size")) {
      if (!read_expected_u32(reader, type, &model->linear_state_size)) return 0;
      required |= 1ULL << 15;
    } else if (string_is(key, "qwen35.ssm.group_count")) {
      if (!read_expected_u32(reader, type, &model->linear_key_head_count)) return 0;
      required |= 1ULL << 16;
    } else if (string_is(key, "qwen35.ssm.time_step_rank")) {
      if (!read_expected_u32(reader, type, &model->linear_value_head_count)) return 0;
      required |= 1ULL << 17;
    } else if (string_is(key, "qwen35.ssm.inner_size")) {
      if (!read_expected_u32(reader, type, &model->linear_inner_size)) return 0;
      required |= 1ULL << 18;
    } else if (string_is(key, "qwen35.full_attention_interval")) {
      if (!read_expected_u32(reader, type, &model->full_attention_interval)) return 0;
      required |= 1ULL << 19;
    } else if (string_is(key, "qwen35.rope.dimension_count")) {
      if (!read_expected_u32(reader, type, &model->rope_dimension_count)) return 0;
      required |= 1ULL << 20;
    } else if (string_is(key, "tokenizer.ggml.model")) {
      if (!read_expected_string(reader, type, "gpt2")) return 0;
      required |= 1ULL << 21;
    } else if (string_is(key, "tokenizer.ggml.pre")) {
      if (!read_expected_string(reader, type, "qwen35")) return 0;
      required |= 1ULL << 22;
    } else if (string_is(key, "tokenizer.ggml.tokens")) {
      if (!read_expected_array_length(reader, type, GGUF_STRING,
                                      AIUEOS_QWEN35_VOCAB_SIZE)) return 0;
      model->vocab_size = AIUEOS_QWEN35_VOCAB_SIZE;
      required |= 1ULL << 23;
    } else if (string_is(key, "tokenizer.ggml.token_type")) {
      if (!read_expected_array_length(reader, type, GGUF_INT32,
                                      AIUEOS_QWEN35_VOCAB_SIZE)) return 0;
      required |= 1ULL << 24;
    } else if (string_is(key, "tokenizer.ggml.merges")) {
      if (!read_expected_array_length(reader, type, GGUF_STRING, 247587)) return 0;
      required |= 1ULL << 25;
    } else if (string_is(key, "tokenizer.ggml.eos_token_id")) {
      uint32_t value;
      if (!read_expected_u32(reader, type, &value) || value != 248046U) return 0;
      required |= 1ULL << 26;
    } else if (string_is(key, "tokenizer.ggml.padding_token_id")) {
      uint32_t value;
      if (!read_expected_u32(reader, type, &value) || value != 248055U) return 0;
      required |= 1ULL << 27;
    } else if (string_is(key, "tokenizer.ggml.bos_token_id")) {
      uint32_t value;
      if (!read_expected_u32(reader, type, &value) || value != 248044U) return 0;
      required |= 1ULL << 28;
    } else if (string_is(key, "general.quantization_version")) {
      uint32_t value;
      if (!read_expected_u32(reader, type, &value) || value != 2U) return 0;
      required |= 1ULL << 29;
    } else if (string_is(key, "general.file_type")) {
      uint32_t value;
      if (!read_expected_u32(reader, type, &value) || value != 23U) return 0;
      required |= 1ULL << 30;
    } else if (!skip_value(reader, type, 0)) {
      return 0;
    }
  }
  return reader->valid && required == ((1ULL << 31) - 1ULL);
}

static int type_layout(uint32_t type, uint64_t *block, uint64_t *bytes) {
  *block = 256;
  switch (type) {
    case AIUEOS_GGML_F32: *block = 1; *bytes = 4; return 1;
    case AIUEOS_GGML_Q8_0: *block = 32; *bytes = 34; return 1;
    case AIUEOS_GGML_Q2_K: *bytes = 84; return 1;
    case AIUEOS_GGML_Q3_K: *bytes = 110; return 1;
    case AIUEOS_GGML_Q4_K: *bytes = 144; return 1;
    case AIUEOS_GGML_Q5_K: *bytes = 176; return 1;
    case AIUEOS_GGML_Q6_K: *bytes = 210; return 1;
    case AIUEOS_GGML_IQ2_XXS: *bytes = 66; return 1;
    case AIUEOS_GGML_IQ2_XS: *bytes = 74; return 1;
    case AIUEOS_GGML_IQ3_XXS: *bytes = 98; return 1;
    case AIUEOS_GGML_IQ1_S: *bytes = 50; return 1;
    case AIUEOS_GGML_IQ3_S: *bytes = 110; return 1;
    case AIUEOS_GGML_IQ2_S: *bytes = 82; return 1;
    case AIUEOS_GGML_IQ4_XS: *bytes = 136; return 1;
    case AIUEOS_GGML_IQ1_M: *bytes = 56; return 1;
    default: return 0;
  }
}

static int tensor_storage(struct aiueos_qwen35_tensor *tensor) {
  if (!tensor->dimension_count || tensor->dimension_count > 4) return 0;
  uint64_t elements = 1;
  for (uint32_t i = 0; i < tensor->dimension_count; i++) {
    uint64_t dimension = tensor->dimensions[i];
    if (!dimension || elements > UINT64_MAX / dimension) return 0;
    elements *= dimension;
  }
  uint64_t block, bytes;
  if (!type_layout(tensor->type, &block, &bytes) || elements % block) return 0;
  elements /= block;
  if (elements > UINT64_MAX / bytes) return 0;
  tensor->storage_bytes = elements * bytes;
  return tensor->storage_bytes != 0;
}

static int tensor_set(struct aiueos_qwen35_tensor *destination,
                      const struct aiueos_qwen35_tensor *source) {
  if (destination->dimension_count) return 0;
  *destination = *source;
  return 1;
}

static int parse_layer_name(struct string_view name, uint32_t *layer,
                            struct string_view *role) {
  uint64_t position;
  if (!string_starts(name, "blk.", &position) || position >= name.length) return 0;
  uint32_t value = 0, digits = 0;
  while (position < name.length && name.bytes[position] >= '0' &&
         name.bytes[position] <= '9') {
    if (value > 100U) return 0;
    value = value * 10U + (uint32_t)(name.bytes[position] - '0');
    position++;
    digits++;
  }
  if (!digits || value >= AIUEOS_QWEN35_LAYER_COUNT ||
      position >= name.length || name.bytes[position++] != '.') return 0;
  *layer = value;
  role->bytes = name.bytes + position;
  role->length = name.length - position;
  return role->length != 0;
}

static int assign_layer_tensor(struct aiueos_qwen35_layer *layer,
                               struct string_view role,
                               const struct aiueos_qwen35_tensor *tensor) {
  if (string_is(role, "attn_norm.weight"))
    return tensor_set(&layer->attention_norm, tensor);
  if (string_is(role, "post_attention_norm.weight"))
    return tensor_set(&layer->post_attention_norm, tensor);
  if (string_is(role, "ffn_down.weight"))
    return tensor_set(&layer->ffn_down, tensor);
  if (string_is(role, "ffn_gate.weight"))
    return tensor_set(&layer->ffn_gate, tensor);
  if (string_is(role, "ffn_up.weight"))
    return tensor_set(&layer->ffn_up, tensor);
  if (string_is(role, "attn_gate.weight"))
    return tensor_set(&layer->mixer.linear.gate, tensor);
  if (string_is(role, "attn_qkv.weight"))
    return tensor_set(&layer->mixer.linear.qkv, tensor);
  if (string_is(role, "ssm_a"))
    return tensor_set(&layer->mixer.linear.a, tensor);
  if (string_is(role, "ssm_alpha.weight"))
    return tensor_set(&layer->mixer.linear.alpha, tensor);
  if (string_is(role, "ssm_beta.weight"))
    return tensor_set(&layer->mixer.linear.beta, tensor);
  if (string_is(role, "ssm_conv1d.weight"))
    return tensor_set(&layer->mixer.linear.conv1d, tensor);
  if (string_is(role, "ssm_dt.bias"))
    return tensor_set(&layer->mixer.linear.dt_bias, tensor);
  if (string_is(role, "ssm_norm.weight"))
    return tensor_set(&layer->mixer.linear.norm, tensor);
  if (string_is(role, "ssm_out.weight"))
    return tensor_set(&layer->mixer.linear.output, tensor);
  if (string_is(role, "attn_k.weight"))
    return tensor_set(&layer->mixer.full.key, tensor);
  if (string_is(role, "attn_k_norm.weight"))
    return tensor_set(&layer->mixer.full.key_norm, tensor);
  if (string_is(role, "attn_output.weight"))
    return tensor_set(&layer->mixer.full.output, tensor);
  if (string_is(role, "attn_q.weight"))
    return tensor_set(&layer->mixer.full.query_gate, tensor);
  if (string_is(role, "attn_q_norm.weight"))
    return tensor_set(&layer->mixer.full.query_norm, tensor);
  if (string_is(role, "attn_v.weight"))
    return tensor_set(&layer->mixer.full.value, tensor);
  if (string_is(role, "nextn.eh_proj.weight"))
    return tensor_set(&layer->nextn.eh_projection, tensor);
  if (string_is(role, "nextn.enorm.weight"))
    return tensor_set(&layer->nextn.embedding_norm, tensor);
  if (string_is(role, "nextn.hnorm.weight"))
    return tensor_set(&layer->nextn.hidden_norm, tensor);
  if (string_is(role, "nextn.shared_head_norm.weight"))
    return tensor_set(&layer->nextn.shared_head_norm, tensor);
  return 0;
}

static int assign_tensor(struct aiueos_qwen35_model *model,
                         struct string_view name,
                         const struct aiueos_qwen35_tensor *tensor) {
  if (string_is(name, "token_embd.weight"))
    return tensor_set(&model->token_embedding, tensor);
  if (string_is(name, "output_norm.weight"))
    return tensor_set(&model->output_norm, tensor);
  if (string_is(name, "output.weight"))
    return tensor_set(&model->output, tensor);
  uint32_t layer;
  struct string_view role;
  if (!parse_layer_name(name, &layer, &role)) return 0;
  return assign_layer_tensor(&model->layers[layer], role, tensor);
}

static int dimensions_are(const struct aiueos_qwen35_tensor *tensor,
                          uint32_t count, uint64_t d0, uint64_t d1) {
  return tensor->dimension_count == count && tensor->dimensions[0] == d0 &&
         (count == 1 || tensor->dimensions[1] == d1);
}

static int common_layer_valid(const struct aiueos_qwen35_layer *layer) {
  return dimensions_are(&layer->attention_norm, 1, 5120, 0) &&
         dimensions_are(&layer->post_attention_norm, 1, 5120, 0) &&
         dimensions_are(&layer->ffn_down, 2, 17408, 5120) &&
         dimensions_are(&layer->ffn_gate, 2, 5120, 17408) &&
         dimensions_are(&layer->ffn_up, 2, 5120, 17408);
}

static int linear_layer_valid(const struct aiueos_qwen35_layer *layer) {
  const struct aiueos_qwen35_linear_tensors *linear = &layer->mixer.linear;
  return common_layer_valid(layer) &&
         dimensions_are(&linear->gate, 2, 5120, 6144) &&
         dimensions_are(&linear->qkv, 2, 5120, 10240) &&
         dimensions_are(&linear->a, 1, 48, 0) &&
         dimensions_are(&linear->alpha, 2, 5120, 48) &&
         dimensions_are(&linear->beta, 2, 5120, 48) &&
         dimensions_are(&linear->conv1d, 2, 4, 10240) &&
         dimensions_are(&linear->dt_bias, 1, 48, 0) &&
         dimensions_are(&linear->norm, 1, 128, 0) &&
         dimensions_are(&linear->output, 2, 6144, 5120);
}

static int full_layer_valid(const struct aiueos_qwen35_layer *layer) {
  const struct aiueos_qwen35_attention_tensors *full = &layer->mixer.full;
  return common_layer_valid(layer) &&
         dimensions_are(&full->key, 2, 5120, 1024) &&
         dimensions_are(&full->key_norm, 1, 256, 0) &&
         dimensions_are(&full->output, 2, 6144, 5120) &&
         dimensions_are(&full->query_gate, 2, 5120, 12288) &&
         dimensions_are(&full->query_norm, 1, 256, 0) &&
         dimensions_are(&full->value, 2, 5120, 1024);
}

static int nextn_layer_valid(const struct aiueos_qwen35_layer *layer) {
  return full_layer_valid(layer) &&
         dimensions_are(&layer->nextn.eh_projection, 2, 10240, 5120) &&
         dimensions_are(&layer->nextn.embedding_norm, 1, 5120, 0) &&
         dimensions_are(&layer->nextn.hidden_norm, 1, 5120, 0) &&
         dimensions_are(&layer->nextn.shared_head_norm, 1, 5120, 0);
}

static int expected_type_counts(const struct aiueos_qwen35_model *model) {
  static const struct { uint32_t type, count; } expected[] = {
    {AIUEOS_GGML_F32, 360}, {AIUEOS_GGML_Q8_0, 98},
    {AIUEOS_GGML_Q2_K, 10}, {AIUEOS_GGML_Q3_K, 6},
    {AIUEOS_GGML_Q4_K, 26}, {AIUEOS_GGML_Q5_K, 7},
    {AIUEOS_GGML_Q6_K, 6}, {AIUEOS_GGML_IQ2_XXS, 24},
    {AIUEOS_GGML_IQ2_XS, 12}, {AIUEOS_GGML_IQ3_XXS, 120},
    {AIUEOS_GGML_IQ1_S, 8}, {AIUEOS_GGML_IQ3_S, 106},
    {AIUEOS_GGML_IQ2_S, 35}, {AIUEOS_GGML_IQ4_XS, 45},
    {AIUEOS_GGML_IQ1_M, 3}
  };
  uint32_t total = 0;
  for (uint32_t i = 0; i < sizeof(expected) / sizeof(expected[0]); i++) {
    if (model->ggml_type_counts[expected[i].type] != expected[i].count) return 0;
    total += expected[i].count;
  }
  return total == AIUEOS_QWEN35_TENSOR_COUNT;
}

static int exact_contract_valid(struct aiueos_qwen35_model *model) {
  if (model->tensor_count != AIUEOS_QWEN35_TENSOR_COUNT ||
      model->metadata_count != AIUEOS_QWEN35_METADATA_COUNT ||
      model->metadata_end != 10945379ULL ||
      model->tensor_info_end != 10996621ULL ||
      model->data_offset != AIUEOS_QWEN35_DATA_OFFSET ||
      model->artifact_bytes != AIUEOS_QWEN35_ARTIFACT_BYTES ||
      model->block_count != AIUEOS_QWEN35_LAYER_COUNT ||
      model->context_length != AIUEOS_QWEN35_CONTEXT_LENGTH ||
      model->embedding_length != AIUEOS_QWEN35_EMBEDDING_LENGTH ||
      model->feed_forward_length != AIUEOS_QWEN35_FEED_FORWARD_LENGTH ||
      model->vocab_size != AIUEOS_QWEN35_VOCAB_SIZE ||
      model->attention_head_count != 24 ||
      model->attention_kv_head_count != 4 ||
      model->attention_key_length != 256 ||
      model->attention_value_length != 256 ||
      model->linear_key_head_count != 16 ||
      model->linear_value_head_count != 48 ||
      model->linear_state_size != 128 ||
      model->linear_inner_size != 6144 ||
      model->linear_conv_kernel != 4 ||
      model->full_attention_interval != 4 ||
      model->rope_dimension_count != 64 ||
      model->rope_sections[0] != 11 || model->rope_sections[1] != 11 ||
      model->rope_sections[2] != 10 || model->rope_sections[3] != 0 ||
      model->nextn_layer_count != AIUEOS_QWEN35_NEXTN_LAYER_COUNT ||
      !dimensions_are(&model->token_embedding, 2, 5120, 248320) ||
      model->token_embedding.type != AIUEOS_GGML_Q2_K ||
      !dimensions_are(&model->output_norm, 1, 5120, 0) ||
      model->output_norm.type != AIUEOS_GGML_F32 ||
      !dimensions_are(&model->output, 2, 5120, 248320) ||
      model->output.type != AIUEOS_GGML_Q4_K ||
      !expected_type_counts(model)) return 0;

  model->linear_layer_count = 0;
  model->full_layer_count = 0;
  for (uint32_t layer = 0; layer < AIUEOS_QWEN35_TRUNK_LAYER_COUNT; layer++) {
    int linear = ((layer + 1U) % 4U) != 0;
    model->layers[layer].linear_attention = (uint32_t)linear;
    if (linear) {
      if (!linear_layer_valid(&model->layers[layer])) return 0;
      model->linear_layer_count++;
    } else {
      if (!full_layer_valid(&model->layers[layer])) return 0;
      model->full_layer_count++;
    }
  }
  model->layers[64].linear_attention = 0;
  if (!nextn_layer_valid(&model->layers[64])) return 0;
  model->trunk_layer_count = AIUEOS_QWEN35_TRUNK_LAYER_COUNT;
  return model->linear_layer_count == AIUEOS_QWEN35_LINEAR_LAYER_COUNT &&
         model->full_layer_count == AIUEOS_QWEN35_FULL_LAYER_COUNT;
}

int aiueos_qwen35_model_parse(const uint8_t *bytes,
                              uint64_t accessible_bytes,
                              uint64_t artifact_bytes,
                              struct aiueos_qwen35_model *model) {
  if (!bytes || !model || accessible_bytes < 24 ||
      artifact_bytes != AIUEOS_QWEN35_ARTIFACT_BYTES ||
      accessible_bytes > artifact_bytes) return 0;
  volatile uint8_t *clear = (volatile uint8_t *)model;
  for (uint64_t i = 0; i < sizeof(*model); i++) clear[i] = 0;
  model->bytes = bytes;
  model->accessible_bytes = accessible_bytes;
  model->artifact_bytes = artifact_bytes;

  struct reader reader = {bytes, accessible_bytes, 0, 1};
  if (read_u32(&reader) != 0x46554747U || read_u32(&reader) != 3U) return 0;
  model->tensor_count = read_u64(&reader);
  model->metadata_count = read_u64(&reader);
  if (model->tensor_count != AIUEOS_QWEN35_TENSOR_COUNT ||
      model->metadata_count != AIUEOS_QWEN35_METADATA_COUNT ||
      !parse_metadata(&reader, model)) return 0;
  model->metadata_end = reader.position;

  uint64_t next_offset = 0;
  for (uint64_t index = 0; index < model->tensor_count; index++) {
    struct string_view name = read_string(&reader);
    struct aiueos_qwen35_tensor tensor = {0};
    tensor.dimension_count = read_u32(&reader);
    if (!reader.valid || tensor.dimension_count == 0 ||
        tensor.dimension_count > 4) return 0;
    for (uint32_t dimension = 0; dimension < tensor.dimension_count; dimension++)
      tensor.dimensions[dimension] = read_u64(&reader);
    tensor.type = read_u32(&reader);
    tensor.offset = read_u64(&reader);
    if (!reader.valid || tensor.type >= AIUEOS_QWEN35_MAX_GGML_TYPE ||
        !tensor_storage(&tensor) || tensor.offset != next_offset ||
        tensor.offset > artifact_bytes ||
        tensor.storage_bytes > artifact_bytes - tensor.offset ||
        !assign_tensor(model, name, &tensor)) return 0;
    model->ggml_type_counts[tensor.type]++;
    uint64_t end = tensor.offset + tensor.storage_bytes;
    if (end > UINT64_MAX - 31ULL) return 0;
    next_offset = (end + 31ULL) & ~31ULL;
  }
  model->tensor_info_end = reader.position;
  if (reader.position > UINT64_MAX - 31ULL) return 0;
  model->data_offset = (reader.position + 31ULL) & ~31ULL;
  if (model->data_offset > artifact_bytes ||
      next_offset != artifact_bytes - model->data_offset ||
      !exact_contract_valid(model)) return 0;
  if (accessible_bytes == artifact_bytes)
    return aiueos_qwen35_model_bind(model, bytes, accessible_bytes);
  return 1;
}

#else /* AIUEOS_QWEN35_KOTOBA_ADMISSION */

/* The admission is three Kotoba objects (ADR-0145). What remains here is
   buffer plumbing: two workspaces, a little-endian load, and the translation
   from the objects' workspace into `struct aiueos_qwen35_model`, which is the
   shape `qwen35_infer.c` reads.

   The objects decide; this decides nothing. Every refusal below is either a
   non-zero verdict handed back by an object, or the one thing the objects
   cannot check because it is about THIS struct rather than about the file: two
   records claiming the same field.

   ZERO IS THE SUCCESS VALUE for all three. `if (verdict)` would invert the
   decision and admit exactly the files they rejected, so every call site here
   spells `!= 0`.

   The translation is a NAMED function rather than the tail of
   `aiueos_qwen35_model_parse`, and with AIUEOS_QWEN35_TRANSLATION_ONLY it is
   the only thing this file compiles to. That is what lets
   `tests/qwen35_runtime_model.c` link the translation and the reference parser
   into one binary on a machine that cannot execute an x86-64 ET_REL object,
   and compare the two structs field by field. Before that seam existed the
   translation had been read but never run (ADR-0145 left it that way). */

/* The kv workspace is the profile's length and the object refuses any other:
   128 bytes for Qwen3.8, 144 for Bonsai, whose last four words carry the
   Hadamard sign array's file offset and count and `general.file_type`. The
   buffer is the larger of the two; which length is PASSED is decided below by
   asking the object, not by parsing the header here. */
#define AIUEOS_QWEN35_KV_PLAN_BYTES 128U
#define AIUEOS_BONSAI2_KV_PLAN_BYTES 144U
#define AIUEOS_QWEN35_TT_PLAN_BYTES 28160U
#define AIUEOS_QWEN35_TT_SLOT_BYTES 32U

/* The two artifacts this file translates (ADR-0222). The profile is not
   chosen here: `qwen35-gguf-header-valid.kotoba` ties the artifact length to
   the header's two counts, `qwen35-gguf-kv-scan.kotoba` publishes which
   profile it admitted in bit 31 of workspace slot 124, and
   `qwen35-tensor-table-bind.kotoba` decides the same profile from
   `metadata-end`. This table is how the C checks that those three and the
   caller's artifact length are talking about ONE file: a Bonsai tensor table
   walked under the Qwen3.8 record count is fifteen records of another model's
   arithmetic, and it would not look wrong on the way past. */
struct qwen35_profile {
  uint64_t artifact_bytes;
  uint64_t metadata_end;
  uint32_t tensor_count;
  uint32_t metadata_count;
};

#define AIUEOS_QWEN35_PROFILE_COUNT 2U

static const struct qwen35_profile
    qwen35_profiles[AIUEOS_QWEN35_PROFILE_COUNT] = {
  /* 0 -- Qwen3.8-27B, contracts/qwen38-qwen35-runtime-v1.edn */
  { AIUEOS_QWEN35_ARTIFACT_BYTES, 10945379ULL,
    AIUEOS_QWEN35_TENSOR_COUNT, AIUEOS_QWEN35_METADATA_COUNT },
  /* 1 -- Ternary Bonsai 2 27B PTQ1_0, contracts/bonsai2-qwen35-runtime-v1.edn.
     The metadata count is here and not in the workspace because no workspace
     slot carries it: the header object is what checked it (-8), against this
     same artifact length. */
  { 5946648928ULL, 11070652ULL, 851U, 49U }
};

/* The last verdict an object handed back, and which object handed it back.
   Diagnostics only: nothing reads these to decide anything. They exist because
   `aiueos_qwen35_model_parse` returns 0/1 and a boot that refuses a model
   otherwise cannot say WHICH clause of WHICH object refused it, and the reason
   literal is the only evidence on the console that the decision came from a
   Kotoba object at all -- the C parser has no such number to print. */
int64_t aiueos_qwen35_admission_verdict;
uint32_t aiueos_qwen35_admission_stage;

static uint32_t plan_u32(const uint8_t *plan, uint64_t offset) {
  const uint8_t *p = plan + offset;
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint64_t plan_u64(const uint8_t *plan, uint64_t offset) {
  return (uint64_t)plan_u32(plan, offset) |
         ((uint64_t)plan_u32(plan, offset + 4) << 32);
}

/* Role id (1..27) and layer (0..64, or 65 for the three whole-model tensors)
   to the field that holds it. The union is safe because the object's per-layer
   role masks admit only linear roles in a linear layer and only full-attention
   roles in a full one; a layer carrying both is refused there with -25 before
   this function is ever reached. */
static struct aiueos_qwen35_tensor *qwen35_slot(
    struct aiueos_qwen35_model *model, uint32_t role, uint32_t layer) {
  if (layer == AIUEOS_QWEN35_LAYER_COUNT) {
    if (role == 25) return &model->token_embedding;
    if (role == 26) return &model->output_norm;
    if (role == 27) return &model->output;
    return 0;
  }
  if (layer >= AIUEOS_QWEN35_LAYER_COUNT) return 0;
  struct aiueos_qwen35_layer *l = &model->layers[layer];
  switch (role) {
    case 1:  return &l->attention_norm;
    case 2:  return &l->post_attention_norm;
    case 3:  return &l->ffn_down;
    case 4:  return &l->ffn_gate;
    case 5:  return &l->ffn_up;
    case 6:  return &l->mixer.linear.gate;
    case 7:  return &l->mixer.linear.qkv;
    case 8:  return &l->mixer.linear.a;
    case 9:  return &l->mixer.linear.alpha;
    case 10: return &l->mixer.linear.beta;
    case 11: return &l->mixer.linear.conv1d;
    case 12: return &l->mixer.linear.dt_bias;
    case 13: return &l->mixer.linear.norm;
    case 14: return &l->mixer.linear.output;
    case 15: return &l->mixer.full.key;
    case 16: return &l->mixer.full.key_norm;
    case 17: return &l->mixer.full.output;
    case 18: return &l->mixer.full.query_gate;
    case 19: return &l->mixer.full.query_norm;
    case 20: return &l->mixer.full.value;
    case 21: return &l->nextn.eh_projection;
    case 22: return &l->nextn.embedding_norm;
    case 23: return &l->nextn.hidden_norm;
    case 24: return &l->nextn.shared_head_norm;
    default: return 0;
  }
}

int aiueos_qwen35_model_translate(const uint8_t *bytes,
                                  uint64_t accessible_bytes,
                                  uint64_t artifact_bytes,
                                  const uint8_t *qwen35_kv_plan,
                                  const uint8_t *qwen35_tt_plan,
                                  struct aiueos_qwen35_model *model) {
  if (!bytes || !model || !qwen35_kv_plan || !qwen35_tt_plan) return 0;
  volatile uint8_t *clear = (volatile uint8_t *)model;
  for (uint64_t i = 0; i < sizeof(*model); i++) clear[i] = 0;
  uint64_t metadata_end = plan_u32(qwen35_kv_plan, 0);

  /* Bit 31 of the required-key mask is the profile the kv-scan object
     admitted: it sets that bit before the walk under profile 1 and never
     under profile 0, so the bit is the object's answer and not a guess made
     from the numbers below it. */
  uint32_t profile = plan_u32(qwen35_kv_plan, 124) >> 31;
  const struct qwen35_profile *expected = &qwen35_profiles[profile];
  uint32_t tensor_count = plan_u32(qwen35_tt_plan, 0);

  /* The three refusals that say the two workspaces and the caller are not
     describing one artifact. Each is a disagreement between the objects and
     this struct, which is what this function refuses on; none of them can be
     repaired by continuing with one of the two answers. */
  if (tensor_count != expected->tensor_count) {
    aiueos_qwen35_admission_verdict = -106;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }
  if (artifact_bytes != expected->artifact_bytes) {
    aiueos_qwen35_admission_verdict = -107;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }
  if (metadata_end != expected->metadata_end) {
    aiueos_qwen35_admission_verdict = -108;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }

  model->bytes = bytes;
  model->accessible_bytes = accessible_bytes;
  model->artifact_bytes = artifact_bytes;
  model->tensor_count = tensor_count;
  model->metadata_count = expected->metadata_count;
  model->metadata_end = metadata_end;
  model->tensor_info_end = plan_u64(qwen35_tt_plan, 16);
  model->data_offset = plan_u64(qwen35_tt_plan, 4);
  model->block_count = plan_u32(qwen35_kv_plan, 4);
  model->context_length = plan_u32(qwen35_kv_plan, 8);
  model->embedding_length = plan_u32(qwen35_kv_plan, 12);
  model->feed_forward_length = plan_u32(qwen35_kv_plan, 16);
  model->attention_head_count = plan_u32(qwen35_kv_plan, 20);
  model->attention_kv_head_count = plan_u32(qwen35_kv_plan, 24);
  model->attention_key_length = plan_u32(qwen35_kv_plan, 28);
  model->attention_value_length = plan_u32(qwen35_kv_plan, 32);
  model->linear_key_head_count = plan_u32(qwen35_kv_plan, 36);
  model->linear_value_head_count = plan_u32(qwen35_kv_plan, 40);
  model->linear_state_size = plan_u32(qwen35_kv_plan, 44);
  model->linear_inner_size = plan_u32(qwen35_kv_plan, 48);
  model->linear_conv_kernel = plan_u32(qwen35_kv_plan, 52);
  model->full_attention_interval = plan_u32(qwen35_kv_plan, 56);
  model->rope_dimension_count = plan_u32(qwen35_kv_plan, 60);
  for (uint32_t section = 0; section < 4; section++)
    model->rope_sections[section] = plan_u32(qwen35_kv_plan, 64 + 4 * section);
  model->nextn_layer_count = plan_u32(qwen35_kv_plan, 80);
  model->vocab_size = plan_u32(qwen35_kv_plan, 84);
  /* The trunk is every block that is not the MTP head: 65 - 1 under Qwen3.8,
     64 - 0 under Bonsai, both of them 64. It is DERIVED from the two words
     the kv-scan object published rather than written as 64, so a third
     artifact with another block count is refused here instead of silently
     losing its last layers -- `layers[]` holds 64 trunk layers and one head
     and cannot be told to hold more. */
  if (model->block_count < model->nextn_layer_count ||
      model->block_count - model->nextn_layer_count !=
        AIUEOS_QWEN35_TRUNK_LAYER_COUNT) {
    aiueos_qwen35_admission_verdict = -109;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }
  model->trunk_layer_count = AIUEOS_QWEN35_TRUNK_LAYER_COUNT;
  model->linear_layer_count = plan_u32(qwen35_tt_plan, 24);
  model->full_layer_count = plan_u32(qwen35_tt_plan, 28);
  /* Every `full_attention_interval`-th layer is full attention and the rest
     are gated DeltaNet. The interval is the metadata value the kv-scan object
     read (4 in both artifacts), not a 4 written here: writing 4 would make
     the schedule of one file a property of the translation. */
  if (model->full_attention_interval == 0) {
    aiueos_qwen35_admission_verdict = -110;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }
  uint32_t linear_derived = 0;
  for (uint32_t layer = 0; layer < AIUEOS_QWEN35_TRUNK_LAYER_COUNT; layer++) {
    uint32_t linear =
      ((layer + 1U) % model->full_attention_interval) != 0 ? 1U : 0U;
    model->layers[layer].linear_attention = linear;
    linear_derived += linear;
  }
  model->layers[AIUEOS_QWEN35_TRUNK_LAYER_COUNT].linear_attention = 0;
  /* The object counted the same schedule a different way -- from the role
     mask each layer actually carried -- so the two counts disagreeing means
     the roles landed in layers this schedule calls something else, and the
     union in `struct aiueos_qwen35_layer` would then be read as the wrong
     arm. That is the one disagreement whose damage is silent. */
  if (linear_derived != model->linear_layer_count ||
      model->linear_layer_count + model->full_layer_count !=
        AIUEOS_QWEN35_TRUNK_LAYER_COUNT) {
    aiueos_qwen35_admission_verdict = -111;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }

  for (uint64_t index = 0; index < model->tensor_count; index++) {
    const uint8_t *slot = qwen35_tt_plan + 32 +
                          index * AIUEOS_QWEN35_TT_SLOT_BYTES;
    uint32_t role = plan_u32(slot, 0);
    uint32_t layer = plan_u32(slot, 4);
    uint64_t file_offset = plan_u64(slot, 20);
    struct aiueos_qwen35_tensor *tensor = qwen35_slot(model, role, layer);
    /* An unknown (role, layer) or a second claim on one field. The objects
       refuse both -- -18 and -19 -- so reaching either here means the
       workspace and this translation disagree, which is a refusal and not a
       recovery. */
    if (!tensor) {
      aiueos_qwen35_admission_verdict = -102;
      aiueos_qwen35_admission_stage = 4;
      return 0;
    }
    if (tensor->dimension_count) {
      aiueos_qwen35_admission_verdict = -103;
      aiueos_qwen35_admission_stage = 4;
      return 0;
    }
    if (file_offset < model->data_offset) {
      aiueos_qwen35_admission_verdict = -104;
      aiueos_qwen35_admission_stage = 4;
      return 0;
    }
    /* Refuse rather than mask. The object already refuses a type it has no
       block layout for (-13), so this cannot fire; but `% MAX` would WRAP
       type 31 onto the F32 counter and make a corrupt table look like a valid
       one, which is the shape a bounds guard must not have.

       PTQ1_0 is the exception the Bonsai profile brings: ggml type 143, which
       is a real type and not a corrupt word, and which counts in slot 31 --
       the slot no Qwen3.8 type uses -- because a table indexed by 143 would
       be 143 words of counters for two. `type-slot` in
       qwen35-tensor-table-bind.kotoba does the same thing with the same two
       numbers; the histogram the object checked against the contract and the
       one below have to be the same histogram. */
    uint32_t type = plan_u32(slot, 8);
    if (type != AIUEOS_GGML_PTQ1_0 && type >= AIUEOS_QWEN35_MAX_GGML_TYPE) {
      aiueos_qwen35_admission_verdict = -105;
      aiueos_qwen35_admission_stage = 4;
      return 0;
    }
    uint32_t type_slot = type == AIUEOS_GGML_PTQ1_0
      ? AIUEOS_QWEN35_PTQ1_0_TYPE_SLOT : type;
    tensor->dimensions[0] = plan_u32(slot, 12);
    tensor->dimensions[1] = plan_u32(slot, 16);
    tensor->dimension_count = tensor->dimensions[1] ? 2U : 1U;
    /* The type stays the artifact's own 143 here. The counter slot is a
       counting detail; a dequantiser handed this tensor must see the type
       the file gave it. */
    tensor->type = type;
    tensor->offset = file_offset - model->data_offset;
    tensor->storage_bytes = plan_u32(slot, 28);
    tensor->data = 0;
    model->ggml_type_counts[type_slot]++;
  }
  return 1;
}

#ifndef AIUEOS_QWEN35_TRANSLATION_ONLY

extern int64_t kotoba_aiueos_qwen35_gguf_header_valid(uint64_t base,
                                                      uint64_t accessible,
                                                      uint64_t artifact);
extern int64_t kotoba_aiueos_qwen35_gguf_kv_scan(uint64_t base,
                                                 uint64_t accessible,
                                                 uint64_t plan,
                                                 uint64_t plan_length);
extern int64_t kotoba_aiueos_qwen35_tensor_table_bind(uint64_t table,
                                                      uint64_t limit,
                                                      uint64_t metadata_end,
                                                      uint64_t plan,
                                                      uint64_t plan_length);

static uint8_t qwen35_kv_plan[AIUEOS_BONSAI2_KV_PLAN_BYTES];
/* `.high_bss` since ADR-0221 (low-region budget; main.c zeroes the section at entry). */
static uint8_t __attribute__((section(".high_bss"), aligned(64))) qwen35_tt_plan[AIUEOS_QWEN35_TT_PLAN_BYTES];

int aiueos_qwen35_model_parse(const uint8_t *bytes,
                              uint64_t accessible_bytes,
                              uint64_t artifact_bytes,
                              struct aiueos_qwen35_model *model) {
  aiueos_qwen35_admission_verdict = 0;
  aiueos_qwen35_admission_stage = 0;
  if (!bytes || !model) return 0;
  for (uint64_t i = 0; i < AIUEOS_BONSAI2_KV_PLAN_BYTES; i++)
    qwen35_kv_plan[i] = 0;
  for (uint64_t i = 0; i < AIUEOS_QWEN35_TT_PLAN_BYTES; i++)
    qwen35_tt_plan[i] = 0;

  uint64_t base = (uint64_t)(uintptr_t)bytes;
  int64_t verdict = kotoba_aiueos_qwen35_gguf_header_valid(
    base, accessible_bytes, artifact_bytes);
  if (verdict != 0) {
    aiueos_qwen35_admission_verdict = verdict;
    aiueos_qwen35_admission_stage = 1;
    return 0;
  }
  /* Which workspace length this artifact wants is the object's answer and not
     a header field read here. Hand it the Qwen3.8 length first; -3 is "the
     workspace is not this profile's length", and when the length passed IS
     one of the two the object admits, -3 can only mean the OTHER profile. The
     length is checked before anything is written, so the retry starts on a
     workspace nothing has touched. A file that is neither refuses twice and
     the second verdict is the one reported. */
  verdict = kotoba_aiueos_qwen35_gguf_kv_scan(
    base, accessible_bytes, (uint64_t)(uintptr_t)qwen35_kv_plan,
    AIUEOS_QWEN35_KV_PLAN_BYTES);
  if (verdict == -3)
    verdict = kotoba_aiueos_qwen35_gguf_kv_scan(
      base, accessible_bytes, (uint64_t)(uintptr_t)qwen35_kv_plan,
      AIUEOS_BONSAI2_KV_PLAN_BYTES);
  if (verdict != 0) {
    aiueos_qwen35_admission_verdict = verdict;
    aiueos_qwen35_admission_stage = 2;
    return 0;
  }

  uint64_t metadata_end = plan_u32(qwen35_kv_plan, 0);
  if (metadata_end > accessible_bytes) {
    aiueos_qwen35_admission_verdict = -101;
    aiueos_qwen35_admission_stage = 4;
    return 0;
  }
  verdict = kotoba_aiueos_qwen35_tensor_table_bind(
    base + metadata_end, accessible_bytes - metadata_end, metadata_end,
    (uint64_t)(uintptr_t)qwen35_tt_plan, AIUEOS_QWEN35_TT_PLAN_BYTES);
  if (verdict != 0) {
    aiueos_qwen35_admission_verdict = verdict;
    aiueos_qwen35_admission_stage = 3;
    return 0;
  }

  if (!aiueos_qwen35_model_translate(bytes, accessible_bytes, artifact_bytes,
                                     qwen35_kv_plan, qwen35_tt_plan, model))
    return 0;
  if (accessible_bytes == artifact_bytes)
    return aiueos_qwen35_model_bind(model, bytes, accessible_bytes);
  return 1;
}

#endif /* AIUEOS_QWEN35_TRANSLATION_ONLY */

#endif /* AIUEOS_QWEN35_KOTOBA_ADMISSION */

#ifndef AIUEOS_QWEN35_TRANSLATION_ONLY

static int bind_tensor(struct aiueos_qwen35_model *model,
                       struct aiueos_qwen35_tensor *tensor) {
  if (!tensor->dimension_count || tensor->offset > model->artifact_bytes ||
      model->data_offset > model->artifact_bytes - tensor->offset) return 0;
  uint64_t absolute = model->data_offset + tensor->offset;
  if (absolute > model->accessible_bytes ||
      tensor->storage_bytes > model->accessible_bytes - absolute) return 0;
  tensor->data = model->bytes + absolute;
  return 1;
}

static int bind_common(struct aiueos_qwen35_model *model,
                       struct aiueos_qwen35_layer *layer) {
  return bind_tensor(model, &layer->attention_norm) &&
         bind_tensor(model, &layer->post_attention_norm) &&
         bind_tensor(model, &layer->ffn_down) &&
         bind_tensor(model, &layer->ffn_gate) &&
         bind_tensor(model, &layer->ffn_up);
}

/* STILL QWEN3.8-ONLY, and it fails closed (ADR-0222). Two clauses below are
   about that artifact and not about binding: the data offset is compared with
   Qwen3.8's 10,996,640, so Bonsai's 11,120,992 is refused here, and the tail
   binds the four MTP tensors, which a 64-block artifact does not have and
   whose zero `dimension_count` `bind_tensor` refuses. A Bonsai artifact
   therefore translates and then does not bind -- it returns 0, it does not
   fabricate a pointer. Making it bind is the floor after this one; it needs
   the mapped 5.9 GB artifact to be graded, which the translation did not. */
int aiueos_qwen35_model_bind(struct aiueos_qwen35_model *model,
                             const uint8_t *bytes,
                             uint64_t accessible_bytes) {
  if (!model || !bytes || accessible_bytes != model->artifact_bytes ||
      model->data_offset != AIUEOS_QWEN35_DATA_OFFSET) return 0;
  model->bytes = bytes;
  model->accessible_bytes = accessible_bytes;
  if (!bind_tensor(model, &model->token_embedding) ||
      !bind_tensor(model, &model->output_norm) ||
      !bind_tensor(model, &model->output)) return 0;
  for (uint32_t index = 0; index < AIUEOS_QWEN35_LAYER_COUNT; index++) {
    struct aiueos_qwen35_layer *layer = &model->layers[index];
    if (!bind_common(model, layer)) return 0;
    if (index < AIUEOS_QWEN35_TRUNK_LAYER_COUNT && layer->linear_attention) {
      struct aiueos_qwen35_linear_tensors *linear = &layer->mixer.linear;
      if (!bind_tensor(model, &linear->gate) || !bind_tensor(model, &linear->qkv) ||
          !bind_tensor(model, &linear->a) || !bind_tensor(model, &linear->alpha) ||
          !bind_tensor(model, &linear->beta) || !bind_tensor(model, &linear->conv1d) ||
          !bind_tensor(model, &linear->dt_bias) || !bind_tensor(model, &linear->norm) ||
          !bind_tensor(model, &linear->output)) return 0;
    } else {
      struct aiueos_qwen35_attention_tensors *full = &layer->mixer.full;
      if (!bind_tensor(model, &full->key) || !bind_tensor(model, &full->key_norm) ||
          !bind_tensor(model, &full->output) || !bind_tensor(model, &full->query_gate) ||
          !bind_tensor(model, &full->query_norm) || !bind_tensor(model, &full->value)) return 0;
    }
  }
  struct aiueos_qwen35_nextn_tensors *nextn = &model->layers[64].nextn;
  return bind_tensor(model, &nextn->eh_projection) &&
         bind_tensor(model, &nextn->embedding_norm) &&
         bind_tensor(model, &nextn->hidden_norm) &&
         bind_tensor(model, &nextn->shared_head_norm);
}

#endif /* AIUEOS_QWEN35_TRANSLATION_ONLY */
