//! GPU capability probing — compatible with capability-probe.ts

use crate::protocol::{BrowserCapability, GpuCap};

/// Probe GPU capabilities from a wgpu adapter
pub fn probe_from_adapter(adapter: &wgpu::Adapter) -> GpuCap {
    let info = adapter.get_info();
    let features = adapter.features();
    let limits = adapter.limits();

    let adapter_name = classify_adapter(&info.driver);

    let mut feature_list = Vec::new();
    if features.contains(wgpu::Features::SHADER_F16) {
        feature_list.push("shader-f16".to_string());
    }
    if features.contains(wgpu::Features::TIMESTAMP_QUERY) {
        feature_list.push("timestamp-query".to_string());
    }

    GpuCap {
        available: true,
        adapter: adapter_name,
        features: feature_list,
        max_storage_buffer_binding_size: limits.max_storage_buffer_binding_size as u64,
        max_compute_workgroup_storage_size: limits.max_compute_workgroup_storage_size as u64,
    }
}

fn classify_adapter(driver: &str) -> String {
    let v = driver.to_lowercase();
    if v.contains("apple") || v.contains("metal") {
        "apple".into()
    } else if v.contains("intel") {
        "intel".into()
    } else if v.contains("nvidia") {
        "nvidia".into()
    } else if v.contains("amd") || v.contains("ati") || v.contains("radeon") {
        "amd".into()
    } else if v.contains("qualcomm") || v.contains("adreno") {
        "qualcomm".into()
    } else {
        "unknown".into()
    }
}

/// Build a full BrowserCapability from a wgpu adapter (for native daemon use)
pub fn build_native_capability(adapter: &wgpu::Adapter) -> BrowserCapability {
    let gpu = probe_from_adapter(adapter);
    let gpu_tier = crate::protocol::classify_gpu_tier_from_gpu(&gpu, "desktop");

    BrowserCapability {
        wasm_simd: false,
        wasm_threads: false,
        gpu,
        mem_class: "high".into(),
        net_class: "good".into(),
        power_class: "desktop".into(),
        gpu_tier,
        cores: num_cpus(),
        user_agent: format!("kotodama-inference/{}", env!("CARGO_PKG_VERSION")),
        runtime_class: "native_wgpu".into(),
        accelerator_class: "wgpu".into(),
        moq_available: false,
    }
}

fn num_cpus() -> u32 {
    #[cfg(not(target_arch = "wasm32"))]
    {
        std::thread::available_parallelism()
            .map(|n| n.get() as u32)
            .unwrap_or(1)
    }
    #[cfg(target_arch = "wasm32")]
    {
        1
    }
}
