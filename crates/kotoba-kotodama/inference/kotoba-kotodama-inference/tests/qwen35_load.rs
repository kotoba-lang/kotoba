/// Integration test: Load Qwen3.5-4B hybrid model and verify structure
///
/// Requires Qwen3.5-4B weights at /Volumes/251220/qwen3.5-4b/
/// Run: cargo test -p kotodama-inference --test qwen35_load -- --nocapture

use std::path::Path;

#[test]
fn test_qwen35_config_parse() {
    let model_dir = Path::new("/Volumes/251220/qwen3.5-4b");
    if !model_dir.exists() {
        eprintln!("SKIP: Qwen3.5-4B not found at {}", model_dir.display());
        return;
    }

    let config = kotodama_inference::loader::load_config(model_dir)
        .expect("failed to load config");

    println!("Model type: {}", config.model_type);
    println!("Hidden size: {}", config.hidden_size);
    println!("Num layers: {}", config.num_hidden_layers);
    println!("Num attention heads: {}", config.num_attention_heads);
    println!("Num KV heads: {}", config.kv_heads());
    println!("Head dim: {}", config.head_dim());
    println!("FFN dim: {}", config.ffn_dim());
    println!("Vocab: {}", config.vocab_size);
    println!("Context: {}", config.max_position_embeddings);
    println!("Is hybrid: {}", config.is_hybrid());
    println!("Layer types: {} entries", config.layer_types.len());

    if config.is_hybrid() {
        let dn_count = config.layer_types.iter().filter(|t| *t == "linear_attention").count();
        let attn_count = config.layer_types.iter().filter(|t| *t == "full_attention").count();
        println!("  DeltaNet layers: {}", dn_count);
        println!("  Attention layers: {}", attn_count);
        println!("  DeltaNet QK dim: {}", config.deltanet_qk_dim());
        println!("  DeltaNet V dim: {}", config.deltanet_v_dim());

        assert_eq!(dn_count, 24, "expected 24 DeltaNet layers");
        assert_eq!(attn_count, 8, "expected 8 attention layers");
    }

    assert_eq!(config.hidden_size, 2560);
    assert_eq!(config.num_hidden_layers, 32);
}

#[test]
fn test_qwen35_hybrid_load() {
    let model_dir = Path::new("/Volumes/251220/qwen3.5-4b");
    if !model_dir.exists() {
        eprintln!("SKIP: Qwen3.5-4B not found at {}", model_dir.display());
        return;
    }

    println!("Loading Qwen3.5-4B hybrid model...");
    let start = std::time::Instant::now();

    let model = kotodama_inference::loader::load_hybrid_model(model_dir)
        .expect("failed to load hybrid model");

    let elapsed = start.elapsed();
    println!("Loaded in {:.1}s", elapsed.as_secs_f64());

    // Verify block structure
    let dn_blocks = model.blocks.iter()
        .filter(|b| matches!(b, kotodama_inference::model::HybridBlock::DeltaNet(_)))
        .count();
    let attn_blocks = model.blocks.iter()
        .filter(|b| matches!(b, kotodama_inference::model::HybridBlock::Attention(_)))
        .count();

    println!("Blocks: {} total ({} DeltaNet + {} Attention)", model.blocks.len(), dn_blocks, attn_blocks);
    println!("Embed tokens: {}", model.embed_tokens.is_some());
    println!("Final norm: {}", model.final_norm.is_some());
    println!("LM head: {}", model.lm_head.is_some());

    assert_eq!(model.blocks.len(), 32);
    assert_eq!(dn_blocks, 24);
    assert_eq!(attn_blocks, 8);
    assert!(model.embed_tokens.is_some(), "embed_tokens should be loaded");

    // Verify DeltaNet block shapes
    if let kotodama_inference::model::HybridBlock::DeltaNet(dn) = &model.blocks[0] {
        println!("\nDeltaNet block 0:");
        println!("  in_proj_qkv: {:?}", dn.in_proj_qkv.shape);
        println!("  in_proj_a: {:?}", dn.in_proj_a.shape);
        println!("  in_proj_b: {:?}", dn.in_proj_b.shape);
        println!("  in_proj_z: {:?}", dn.in_proj_z.shape);
        println!("  a_log: {:?}", dn.a_log.shape);
        println!("  conv1d: {:?}", dn.conv1d_weight.shape);
        println!("  norm: {:?}", dn.norm.shape);
        println!("  out_proj: {:?}", dn.out_proj.shape);
        println!("  gate_weight: {:?}", dn.gate_weight.shape);
        println!("  down_weight: {:?}", dn.down_weight.shape);
        assert!(!dn.in_proj_qkv.data.is_empty(), "QKV proj should have data");
        assert!(!dn.out_proj.data.is_empty(), "out_proj should have data");
    }

    // Verify Attention block shapes
    if let kotodama_inference::model::HybridBlock::Attention(attn) = &model.blocks[3] {
        println!("\nAttention block 3:");
        println!("  q_weight: {:?}", attn.q_weight.shape);
        println!("  k_weight: {:?}", attn.k_weight.shape);
        println!("  v_weight: {:?}", attn.v_weight.shape);
        println!("  o_weight: {:?}", attn.o_weight.shape);
        println!("  gate_weight: {:?}", attn.gate_weight.shape);
        println!("  down_weight: {:?}", attn.down_weight.shape);
        assert!(!attn.q_weight.data.is_empty(), "Q proj should have data");
    }

    println!("\nQwen3.5-4B hybrid model loaded successfully!");
}
