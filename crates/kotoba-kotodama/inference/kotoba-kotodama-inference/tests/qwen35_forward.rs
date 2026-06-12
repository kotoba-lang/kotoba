/// Integration test: Forward pass through Qwen3.5-4B DeltaNet + Attention blocks
///
/// Run: cargo test -p kotodama-inference --test qwen35_forward --release -- --nocapture

#[tokio::test]
async fn test_qwen35_single_deltanet_forward() {
    let model_dir = std::path::Path::new("/Volumes/251220/qwen3.5-4b");
    if !model_dir.exists() {
        eprintln!("SKIP: Qwen3.5-4B not found");
        return;
    }

    let config = kotodama_inference::loader::load_config(model_dir)
        .expect("failed to load config");

    println!("Initializing inference engine...");
    let engine = kotodama_inference::engine::InferenceEngine::new()
        .await
        .expect("failed to init engine");
    println!("Backend: {}", engine.backend_name());

    // Load only the first DeltaNet block to test forward pass
    println!("Loading first DeltaNet block...");
    let model = kotodama_inference::loader::load_hybrid_model(model_dir)
        .expect("failed to load model");

    let block = match &model.blocks[0] {
        kotodama_inference::model::HybridBlock::DeltaNet(dn) => dn,
        _ => panic!("block 0 should be DeltaNet"),
    };

    // Create dummy input: [1, 4, dim] (batch=1, seq_len=4, dim=2560)
    let dim = config.hidden_size as usize;
    let seq_len = 4;
    let input: Vec<f32> = (0..seq_len * dim)
        .map(|i| ((i % 100) as f32 - 50.0) * 0.01)
        .collect();

    println!("Running DeltaNet forward (seq_len={}, dim={})...", seq_len, dim);
    let start = std::time::Instant::now();

    let result = kotodama_inference::transformer::forward_deltanet_block(
        &engine, block, &config, &input,
    )
    .await
    .expect("DeltaNet forward failed");

    let elapsed = start.elapsed();
    println!("DeltaNet forward: {:.1}ms", elapsed.as_millis());
    println!("Output shape: {} (expected {})", result.hidden_states.len(), seq_len * dim);
    println!("Output[0..5]: {:?}", &result.hidden_states[..5.min(result.hidden_states.len())]);

    assert_eq!(result.hidden_states.len(), seq_len * dim,
        "output size mismatch");
    // Should not be all zeros
    let nonzero = result.hidden_states.iter().any(|&v| v.abs() > 1e-10);
    assert!(nonzero, "output should not be all zeros");

    println!("DeltaNet forward pass OK!");
}

#[tokio::test]
async fn test_qwen35_single_attention_forward() {
    let model_dir = std::path::Path::new("/Volumes/251220/qwen3.5-4b");
    if !model_dir.exists() {
        eprintln!("SKIP: Qwen3.5-4B not found");
        return;
    }

    let config = kotodama_inference::loader::load_config(model_dir)
        .expect("failed to load config");

    let engine = kotodama_inference::engine::InferenceEngine::new()
        .await
        .expect("failed to init engine");

    let model = kotodama_inference::loader::load_hybrid_model(model_dir)
        .expect("failed to load model");

    // Block 3 is first attention layer
    let block = match &model.blocks[3] {
        kotodama_inference::model::HybridBlock::Attention(attn) => attn,
        _ => panic!("block 3 should be Attention"),
    };

    let dim = config.hidden_size as usize;
    let seq_len = 4;
    let input: Vec<f32> = (0..seq_len * dim)
        .map(|i| ((i % 100) as f32 - 50.0) * 0.01)
        .collect();

    println!("Running Attention forward (seq_len={}, dim={})...", seq_len, dim);
    let start = std::time::Instant::now();

    let result = kotodama_inference::transformer::forward_block(
        &engine, block, &config, &input,
    )
    .await
    .expect("Attention forward failed");

    let elapsed = start.elapsed();
    println!("Attention forward: {:.1}ms", elapsed.as_millis());
    println!("Output shape: {} (expected {})", result.hidden_states.len(), seq_len * dim);

    assert_eq!(result.hidden_states.len(), seq_len * dim);
    let nonzero = result.hidden_states.iter().any(|&v| v.abs() > 1e-10);
    assert!(nonzero, "output should not be all zeros");

    println!("Attention forward pass OK!");
}

#[tokio::test]
async fn test_qwen35_hybrid_4_blocks() {
    let model_dir = std::path::Path::new("/Volumes/251220/qwen3.5-4b");
    if !model_dir.exists() {
        eprintln!("SKIP: Qwen3.5-4B not found");
        return;
    }

    let config = kotodama_inference::loader::load_config(model_dir)
        .expect("failed to load config");
    let engine = kotodama_inference::engine::InferenceEngine::new()
        .await
        .expect("failed to init engine");
    let model = kotodama_inference::loader::load_hybrid_model(model_dir)
        .expect("failed to load model");

    // Run first 4 blocks (3 DeltaNet + 1 Attention)
    let blocks: Vec<&kotodama_inference::model::HybridBlock> = model.blocks[..4].iter().collect();

    let dim = config.hidden_size as usize;
    let seq_len = 4;
    let input: Vec<f32> = (0..seq_len * dim)
        .map(|i| ((i % 100) as f32 - 50.0) * 0.01)
        .collect();

    println!("Running hybrid shard (4 blocks: 3×DeltaNet + 1×Attention)...");
    let start = std::time::Instant::now();

    let result = kotodama_inference::transformer::forward_hybrid_shard(
        &engine, &blocks, &config, &input,
    )
    .await
    .expect("hybrid forward failed");

    let elapsed = start.elapsed();
    println!("Hybrid 4-block forward: {:.1}ms", elapsed.as_millis());
    println!("Output shape: {}", result.hidden_states.len());

    assert_eq!(result.hidden_states.len(), seq_len * dim);
    println!("Hybrid forward pass OK!");
}
