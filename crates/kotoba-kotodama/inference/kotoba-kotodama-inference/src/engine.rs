//! Inference engine — auto-selects optimal backend per platform.
//!
//! macOS arm64: MLX (native Metal, AMX/ANE) → wgpu (fallback)
//! Linux/other: wgpu (Vulkan/Metal)
//! Browser:     wgpu (WebGPU via web-sys)

pub use crate::wgpu_backend::EngineError;
pub use crate::wgpu_backend::ShardResult;

/// Backend selection — MLX native on macOS arm64, wgpu everywhere else
enum Backend {
    Wgpu(crate::wgpu_backend::InferenceEngine),
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    Mlx(crate::mlx_backend::MlxEngine),
}

pub struct InferenceEngine {
    backend: Backend,
}

impl InferenceEngine {
    pub async fn new() -> Result<Self, EngineError> {
        #[cfg(not(target_arch = "wasm32"))]
        let forced_backend = std::env::var("KOTODAMA_INFERENCE_BACKEND")
            .or_else(|_| std::env::var("etzhayyim_KOTODAMA_BACKEND"))
            .ok()
            .map(|v| v.to_ascii_lowercase());

        // On macOS arm64, try MLX first (native Metal performance).
        // wgpu Metal hangs without a CFRunLoop (daemon/headless context),
        // so MLX is the only viable GPU backend on macOS arm64 daemons.
        #[cfg(all(target_os = "macos", target_arch = "aarch64", not(target_arch = "wasm32")))]
        {
            let wants_wgpu = matches!(forced_backend.as_deref(), Some("wgpu" | "webgpu"));
            if !wants_wgpu {
                if crate::mlx_backend::mlx_available() {
                    match crate::mlx_backend::MlxEngine::new() {
                        Ok(mlx) => {
                            log::info!("using MLX backend (Apple Silicon native Metal)");
                            return Ok(Self {
                                backend: Backend::Mlx(mlx),
                            });
                        }
                        Err(e) => {
                            log::error!("MLX init failed: {e}");
                            return Err(EngineError::DeviceError(format!(
                                "MLX init failed on macOS arm64: {e}. Install mlx-c: brew install mlx-c"
                            )));
                        }
                    }
                } else {
                    // MLX library not found — cannot fall back to wgpu on macOS arm64
                    // because wgpu Metal requires a CFRunLoop which daemons don't have.
                    return Err(EngineError::DeviceError(
                        "MLX library (libmlxc.dylib) not found. wgpu Metal is not available \
                         in daemon/headless context (requires CFRunLoop). \
                         Install: brew install mlx-c"
                            .into(),
                    ));
                }
            }
        }

        // Non-macOS-arm64 or explicitly forced wgpu: use wgpu backend
        let wgpu = crate::wgpu_backend::InferenceEngine::new().await?;
        log::info!("using wgpu backend");
        Ok(Self {
            backend: Backend::Wgpu(wgpu),
        })
    }

    pub fn backend_name(&self) -> &'static str {
        match &self.backend {
            Backend::Wgpu(_) => "wgpu",
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(_) => "mlx",
        }
    }

    pub async fn matmul(
        &self,
        a: &[f32],
        b: &[f32],
        m: u32,
        k: u32,
        n: u32,
        bias: Option<&[f32]>,
    ) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.matmul(a, b, m, k, n, bias).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(e) => e.matmul(a, b, m, k, n, bias),
        }
    }

    pub async fn rmsnorm(
        &self,
        x: &mut [f32],
        weight: &[f32],
        seq_len: u32,
        dim: u32,
        eps: f32,
    ) -> Result<(), EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.rmsnorm(x, weight, seq_len, dim, eps).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(e) => e.rmsnorm(x, weight, seq_len, dim, eps),
        }
    }

    pub async fn softmax(
        &self,
        data: &mut [f32],
        rows: u32,
        cols: u32,
    ) -> Result<(), EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.softmax(data, rows, cols).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(e) => e.softmax(data, rows, cols),
        }
    }

    pub async fn gated_silu(
        &self,
        input: &[f32],
        n: u32,
        ffn_dim: u32,
    ) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.gated_silu(input, n, ffn_dim).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(e) => e.gated_silu(input, n, ffn_dim),
        }
    }

    pub async fn residual_add(
        &self,
        x: &mut [f32],
        residual: &[f32],
    ) -> Result<(), EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.residual_add(x, residual).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(e) => e.residual_add(x, residual),
        }
    }

    pub async fn silu(&self, input: &[f32]) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.silu(input).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(_) => Ok(cpu_silu(input)),
        }
    }

    pub async fn softplus(&self, input: &[f32]) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.softplus(input).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(_) => Ok(cpu_softplus(input)),
        }
    }

    pub async fn ssm_output(
        &self,
        x_in: &[f32],
        dt: &[f32],
        b_val: &[f32],
        c_val: &[f32],
        d_val: &[f32],
        seq_len: u32,
        inner: u32,
        state_dim: u32,
    ) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => {
                e.ssm_output(x_in, dt, b_val, c_val, d_val, seq_len, inner, state_dim)
                    .await
            }
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(_) => {
                Ok(cpu_ssm_output(x_in, dt, b_val, c_val, d_val, seq_len, inner, state_dim))
            }
        }
    }

    pub async fn elementwise_mul(
        &self,
        a: &[f32],
        b: &[f32],
    ) -> Result<Vec<f32>, EngineError> {
        match &self.backend {
            Backend::Wgpu(e) => e.elementwise_mul(a, b).await,
            #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
            Backend::Mlx(_) => Ok(a.iter().zip(b).map(|(x, y)| x * y).collect()),
        }
    }
}

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
fn cpu_silu(input: &[f32]) -> Vec<f32> {
    input.iter().map(|&x| x / (1.0 + (-x).exp())).collect()
}

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
fn cpu_softplus(input: &[f32]) -> Vec<f32> {
    input
        .iter()
        .map(|&x| if x > 20.0 { x } else { (1.0 + x.exp()).ln() })
        .collect()
}

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
fn cpu_ssm_output(
    x_in: &[f32],
    dt: &[f32],
    b_val: &[f32],
    c_val: &[f32],
    d_val: &[f32],
    seq_len: u32,
    inner: u32,
    state_dim: u32,
) -> Vec<f32> {
    let (seq_len, inner, state_dim) = (seq_len as usize, inner as usize, state_dim as usize);
    let mut output = vec![0.0f32; seq_len * inner];
    for t in 0..seq_len {
        for i in 0..inner {
            let idx = t * inner + i;
            let dt_val = dt[idx];
            let base = idx * state_dim;
            let mut acc = 0.0f32;
            for s in 0..state_dim {
                acc += c_val[base + s] * dt_val * b_val[base + s];
            }
            output[idx] = acc + d_val[i] * x_in[idx];
        }
    }
    output
}
