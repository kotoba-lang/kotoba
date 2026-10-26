#!/usr/bin/env python3
"""Build the exact Qwen3.8 GGUF metadata/tensor-table shape without weights."""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path


TENSOR_COUNT = 866
METADATA_COUNT = 50
METADATA_END = 10_945_379
TENSOR_INFO_END = 10_996_621
DATA_OFFSET = 10_996_640
ARTIFACT_BYTES = 10_934_860_704

U32 = 4
I32 = 5
F32 = 6
STRING = 8
ARRAY = 9


def string(value: str | bytes) -> bytes:
    encoded = value.encode() if isinstance(value, str) else value
    return struct.pack("<Q", len(encoded)) + encoded


def metadata(key: str, value_type: int, value: bytes) -> bytes:
    return string(key) + struct.pack("<I", value_type) + value


def scalar_u32(key: str, value: int) -> bytes:
    return metadata(key, U32, struct.pack("<I", value))


def scalar_i32(key: str, value: int) -> bytes:
    return metadata(key, I32, struct.pack("<i", value))


def scalar_f32(key: str, value: float) -> bytes:
    return metadata(key, F32, struct.pack("<f", value))


def scalar_string(key: str, value: str) -> bytes:
    return metadata(key, STRING, string(value))


def array_header(key: str, element_type: int, count: int) -> bytes:
    return string(key) + struct.pack("<IIQ", ARRAY, element_type, count)


def build_metadata() -> bytes:
    entries = [
        scalar_string("general.architecture", "qwen35"),
        scalar_string("general.type", "model"),
        scalar_i32("general.sampling.top_k", 20),
        scalar_f32("general.sampling.top_p", 0.95),
        scalar_f32("general.sampling.temp", 1.0),
        scalar_string("general.name", "Qwen3.8-27B"),
        scalar_string("general.basename", "Qwen3.8-27B"),
        scalar_string(
            "general.description",
            "Renewal of the beloved Qwen model, delivering unmatched intelligence density.",
        ),
        scalar_string("general.quantized_by", "Unsloth"),
        scalar_string("general.size_label", "27B"),
        scalar_string("general.license", "apache-2.0"),
        scalar_string("general.repo_url", "https://huggingface.co/unsloth"),
        scalar_u32("general.base_model.count", 1),
        scalar_string("general.base_model.0.name", "Qwen3.8 27B"),
        scalar_string("general.base_model.0.organization", "Qwen"),
        scalar_string(
            "general.base_model.0.repo_url", "https://huggingface.co/Qwen/Qwen3.8-27B"
        ),
        array_header("general.tags", STRING, 1) + string("unsloth"),
        scalar_u32("qwen35.block_count", 65),
        scalar_u32("qwen35.context_length", 262_144),
        scalar_u32("qwen35.embedding_length", 5_120),
        scalar_u32("qwen35.feed_forward_length", 17_408),
        scalar_u32("qwen35.attention.head_count", 24),
        scalar_u32("qwen35.attention.head_count_kv", 4),
        array_header("qwen35.rope.dimension_sections", I32, 4)
        + struct.pack("<IIII", 11, 11, 10, 0),
        scalar_f32("qwen35.rope.freq_base", 10_000_000.0),
        scalar_f32("qwen35.attention.layer_norm_rms_epsilon", 1e-6),
        scalar_u32("qwen35.attention.key_length", 256),
        scalar_u32("qwen35.attention.value_length", 256),
        scalar_u32("qwen35.nextn_predict_layers", 1),
        scalar_u32("qwen35.ssm.conv_kernel", 4),
        scalar_u32("qwen35.ssm.state_size", 128),
        scalar_u32("qwen35.ssm.group_count", 16),
        scalar_u32("qwen35.ssm.time_step_rank", 48),
        scalar_u32("qwen35.ssm.inner_size", 6_144),
        scalar_u32("qwen35.full_attention_interval", 4),
        scalar_u32("qwen35.rope.dimension_count", 64),
        scalar_string("tokenizer.ggml.model", "gpt2"),
        scalar_string("tokenizer.ggml.pre", "qwen35"),
        array_header("tokenizer.ggml.tokens", STRING, 248_320) + b"\0" * (8 * 248_320),
        array_header("tokenizer.ggml.token_type", I32, 248_320) + b"\0" * (4 * 248_320),
        array_header("tokenizer.ggml.merges", STRING, 247_587) + b"\0" * (8 * 247_587),
        scalar_u32("tokenizer.ggml.eos_token_id", 248_046),
        scalar_u32("tokenizer.ggml.padding_token_id", 248_055),
        scalar_u32("tokenizer.ggml.bos_token_id", 248_044),
        scalar_u32("general.quantization_version", 2),
        scalar_u32("general.file_type", 23),
        scalar_string("quantize.imatrix.file", "Qwen3.8-27B-GGUF/imatrix_unsloth.gguf"),
        scalar_u32("quantize.imatrix.entries_count", 496),
        scalar_u32("quantize.imatrix.chunks_count", 1_251),
    ]
    assert len(entries) == METADATA_COUNT - 1
    current = 24 + sum(map(len, entries))
    final_key_overhead = len(string("tokenizer.chat_template")) + 4 + 8
    padding = METADATA_END - current - final_key_overhead
    assert padding >= 0
    entries.append(scalar_string("tokenizer.chat_template", "x" * padding))
    result = b"".join(entries)
    assert 24 + len(result) == METADATA_END
    return result


def layer_rows(index: int) -> list[tuple[str, tuple[int, ...]]]:
    prefix = f"blk.{index}."
    if index == 64:
        return [
            (prefix + "attn_k.weight", (5120, 1024)),
            (prefix + "attn_k_norm.weight", (256,)),
            (prefix + "attn_norm.weight", (5120,)),
            (prefix + "attn_output.weight", (6144, 5120)),
            (prefix + "attn_q.weight", (5120, 12288)),
            (prefix + "attn_q_norm.weight", (256,)),
            (prefix + "attn_v.weight", (5120, 1024)),
            (prefix + "ffn_down.weight", (17408, 5120)),
            (prefix + "ffn_gate.weight", (5120, 17408)),
            (prefix + "ffn_up.weight", (5120, 17408)),
            (prefix + "nextn.eh_proj.weight", (10240, 5120)),
            (prefix + "nextn.enorm.weight", (5120,)),
            (prefix + "nextn.hnorm.weight", (5120,)),
            (prefix + "nextn.shared_head_norm.weight", (5120,)),
            (prefix + "post_attention_norm.weight", (5120,)),
        ]
    if (index + 1) % 4 == 0:
        return [
            (prefix + "attn_k.weight", (5120, 1024)),
            (prefix + "attn_k_norm.weight", (256,)),
            (prefix + "attn_norm.weight", (5120,)),
            (prefix + "attn_output.weight", (6144, 5120)),
            (prefix + "attn_q.weight", (5120, 12288)),
            (prefix + "attn_q_norm.weight", (256,)),
            (prefix + "attn_v.weight", (5120, 1024)),
            (prefix + "ffn_down.weight", (17408, 5120)),
            (prefix + "ffn_gate.weight", (5120, 17408)),
            (prefix + "ffn_up.weight", (5120, 17408)),
            (prefix + "post_attention_norm.weight", (5120,)),
        ]
    return [
        (prefix + "attn_gate.weight", (5120, 6144)),
        (prefix + "attn_norm.weight", (5120,)),
        (prefix + "attn_qkv.weight", (5120, 10240)),
        (prefix + "ffn_down.weight", (17408, 5120)),
        (prefix + "ffn_gate.weight", (5120, 17408)),
        (prefix + "ffn_up.weight", (5120, 17408)),
        (prefix + "post_attention_norm.weight", (5120,)),
        (prefix + "ssm_a", (48,)),
        (prefix + "ssm_alpha.weight", (5120, 48)),
        (prefix + "ssm_beta.weight", (5120, 48)),
        (prefix + "ssm_conv1d.weight", (4, 10240)),
        (prefix + "ssm_dt.bias", (48,)),
        (prefix + "ssm_norm.weight", (128,)),
        (prefix + "ssm_out.weight", (6144, 5120)),
    ]


MATRIX_TYPES_HEX = (
    "0c0a17171113130808000c12161210100808000c1212151616080800170c0c0a0c12161615161616160808001515"
    "121616120808001712121616110808001515120a0c0a161612101016160808000b16101111100808001516121111"
    "100808000b15120a0c1010101210101113080800121610131d1308080012100a1d10130808001215100a0c1d1310"
    "16151110100808001611121013100808000b0a0a161011080800120c15100c161110121515121508080015151212"
    "120b080800151212151215080800151515150d15121215120b121208080012151215150b08080017121512151508"
    "0800151717150d1512151515121212080800151515121216080800121512121112080800150c17120d1616121215"
    "121612080800151215161612080800151215151212080800150c17120d1516121212151212080800151212151212"
    "080800151216151215080800121517120c1512151212151215080800151212151515080800151212121215080800"
    "150c0c150c1212151212121212080800151615121212080800121215121612080800150c15120c12121216151212"
    "12080800150a15151215080800151212151212080800170c17150d15121512121512150808001712121512150808"
    "00171212171515080800150c17120c1712151515171517080800171512171717080800171515171717080800170c"
    "17120d1717171515171717080800171515171717080800151215151717080800170c17170d0c170c080e0e080e0e"
    "0e0e"
)


TYPE_LAYOUT = {
    0: (1, 4),
    8: (32, 34),
    10: (256, 84),
    11: (256, 110),
    12: (256, 144),
    13: (256, 176),
    14: (256, 210),
    16: (256, 66),
    17: (256, 74),
    18: (256, 98),
    19: (256, 50),
    21: (256, 110),
    22: (256, 82),
    23: (256, 136),
    29: (256, 56),
}


def build_tensor_table() -> tuple[bytes, int]:
    rows = [
        ("output.weight", (5120, 248320)),
        ("output_norm.weight", (5120,)),
        ("token_embd.weight", (5120, 248320)),
    ]
    for index in range(65):
        rows.extend(layer_rows(index))
    assert len(rows) == TENSOR_COUNT
    matrix_types = bytes.fromhex(MATRIX_TYPES_HEX)
    assert len(matrix_types) == 554
    matrix_index = 0
    offset = 0
    encoded = bytearray()
    for name, dimensions in rows:
        tensor_type = 0 if len(dimensions) == 1 else matrix_types[matrix_index]
        if len(dimensions) != 1:
            matrix_index += 1
        block, block_bytes = TYPE_LAYOUT[tensor_type]
        elements = math.prod(dimensions)
        assert elements % block == 0
        storage = elements // block * block_bytes
        encoded += string(name)
        encoded += struct.pack("<I", len(dimensions))
        encoded += struct.pack("<" + "Q" * len(dimensions), *dimensions)
        encoded += struct.pack("<IQ", tensor_type, offset)
        offset = (offset + storage + 31) & ~31
    assert matrix_index == len(matrix_types)
    return bytes(encoded), offset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    table, tensor_bytes = build_tensor_table()
    assert METADATA_END + len(table) == TENSOR_INFO_END
    assert DATA_OFFSET + tensor_bytes == ARTIFACT_BYTES
    header = (
        b"GGUF"
        + struct.pack("<IQQ", 3, TENSOR_COUNT, METADATA_COUNT)
        + build_metadata()
        + table
    )
    assert len(header) == TENSOR_INFO_END
    header += b"\0" * (DATA_OFFSET - len(header))
    args.output.write_bytes(header)
    print(
        "AIUEOS_QWEN35_HEADER_FIXTURE_OK "
        f"bytes={len(header)} tensors={TENSOR_COUNT} artifact={ARTIFACT_BYTES}"
    )


if __name__ == "__main__":
    main()
