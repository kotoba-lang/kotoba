//! wgpu compute pipeline — matmul, attention, FFN, RMSNorm
//! Same code runs on browser (web-sys WebGPU) and native (Metal/Vulkan).

use bytemuck::{Pod, Zeroable};

/// GPU matmul threshold: use GPU when M*K*N > this value
const GPU_MATMUL_THRESHOLD: u64 = 1_000_000;

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct MatmulMeta {
    m: u32,
    n: u32,
    k: u32,
    has_bias: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct RmsnormMeta {
    n: u32,
    dim: u32,
    eps: f32,
    _pad: f32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SoftmaxMeta {
    rows: u32,
    cols: u32,
    _p0: u32,
    _p1: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct GatedSiluMeta {
    n: u32,
    ffn_dim: u32,
    _p0: u32,
    _p1: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct ResidualMeta {
    total: u32,
    _p0: u32,
    _p1: u32,
    _p2: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SiluMeta {
    total: u32,
    _p0: u32,
    _p1: u32,
    _p2: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SoftplusMeta {
    total: u32,
    _p0: u32,
    _p1: u32,
    _p2: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct SsmOutputMeta {
    seq_len: u32,
    inner: u32,
    state_dim: u32,
    _pad: u32,
}

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct ElementwiseMulMeta {
    total: u32,
    _p0: u32,
    _p1: u32,
    _p2: u32,
}

pub struct Pipelines {
    pub matmul: wgpu::ComputePipeline,
    pub rmsnorm: wgpu::ComputePipeline,
    pub softmax: wgpu::ComputePipeline,
    pub gated_silu: wgpu::ComputePipeline,
    pub residual_add: wgpu::ComputePipeline,
    pub silu: wgpu::ComputePipeline,
    pub softplus: wgpu::ComputePipeline,
    pub ssm_output: wgpu::ComputePipeline,
    pub elementwise_mul: wgpu::ComputePipeline,
}

pub struct InferenceEngine {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipelines: Pipelines,
}

#[derive(Debug, Clone)]
pub struct ShardResult {
    pub shard_id: String,
    pub gpu_time_ms: u64,
    pub hidden_states: Vec<f32>,
    pub checksum: u32,
}

#[derive(Debug)]
pub enum EngineError {
    NoGpu,
    DeviceError(String),
    BufferMapFailed,
}

impl std::fmt::Display for EngineError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoGpu => write!(f, "no GPU adapter available"),
            Self::DeviceError(e) => write!(f, "GPU device error: {e}"),
            Self::BufferMapFailed => write!(f, "GPU buffer map failed"),
        }
    }
}

impl InferenceEngine {
    pub async fn new() -> Result<Self, EngineError> {
        // Browser: force WebGPU backend. Native: auto-detect (Metal/Vulkan).
        #[cfg(target_arch = "wasm32")]
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::BROWSER_WEBGPU,
            ..Default::default()
        });
        #[cfg(not(target_arch = "wasm32"))]
        let instance = wgpu::Instance::default();
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                ..Default::default()
            })
            .await
            .ok_or(EngineError::NoGpu)?;

        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor::default(), None)
            .await
            .map_err(|e| EngineError::DeviceError(e.to_string()))?;

        let pipelines = Pipelines {
            matmul: create_pipeline(&device, include_str!("../shaders/matmul.wgsl")),
            rmsnorm: create_pipeline(&device, include_str!("../shaders/rmsnorm.wgsl")),
            softmax: create_pipeline(&device, include_str!("../shaders/softmax.wgsl")),
            gated_silu: create_pipeline(&device, include_str!("../shaders/gated_silu.wgsl")),
            residual_add: create_pipeline(&device, include_str!("../shaders/residual_add.wgsl")),
            silu: create_pipeline(&device, include_str!("../shaders/silu.wgsl")),
            softplus: create_pipeline(&device, include_str!("../shaders/softplus.wgsl")),
            ssm_output: create_pipeline(&device, include_str!("../shaders/ssm_output.wgsl")),
            elementwise_mul: create_pipeline(&device, include_str!("../shaders/elementwise_mul.wgsl")),
        };

        Ok(Self {
            device,
            queue,
            pipelines,
        })
    }

    /// GPU-accelerated matrix multiply: C[M,N] = A[M,K] * B[K,N] + optional bias[N]
    pub async fn matmul(
        &self,
        a: &[f32],
        b: &[f32],
        m: u32,
        k: u32,
        n: u32,
        bias: Option<&[f32]>,
    ) -> Result<Vec<f32>, EngineError> {
        let ops = m as u64 * k as u64 * n as u64;
        if ops < GPU_MATMUL_THRESHOLD {
            return Ok(cpu_matmul(a, b, m, k, n, bias));
        }

        let meta = MatmulMeta {
            m,
            n,
            k,
            has_bias: if bias.is_some() { 1 } else { 0 },
        };

        let meta_buf = self.create_uniform(&meta);
        let a_buf = self.create_storage_read(bytemuck::cast_slice(a));
        let b_buf = self.create_storage_read(bytemuck::cast_slice(b));
        let c_buf = self.create_storage_rw((m * n) as usize * 4);
        let bias_data: Vec<f32> = bias.map(|b| b.to_vec()).unwrap_or_else(|| vec![0.0]);
        let bias_buf = self.create_storage_read(bytemuck::cast_slice(&bias_data));

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.matmul.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: a_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: b_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: c_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 4, resource: bias_buf.as_entire_binding() },
            ],
        });

        let wg_x = (n + 15) / 16;
        let wg_y = (m + 15) / 16;
        self.dispatch(&self.pipelines.matmul, &bind_group, wg_x, wg_y, 1);

        self.read_buffer(&c_buf, (m * n) as usize).await
    }

    /// GPU-accelerated RMSNorm in-place
    pub async fn rmsnorm(
        &self,
        x: &mut [f32],
        weight: &[f32],
        seq_len: u32,
        dim: u32,
        eps: f32,
    ) -> Result<(), EngineError> {
        let meta = RmsnormMeta { n: seq_len, dim, eps, _pad: 0.0 };
        let meta_buf = self.create_uniform(&meta);
        let x_buf = self.create_storage_rw_init(bytemuck::cast_slice(x));
        let w_buf = self.create_storage_read(bytemuck::cast_slice(weight));

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.rmsnorm.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: x_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: w_buf.as_entire_binding() },
            ],
        });

        let wg_x = (seq_len + 255) / 256;
        self.dispatch(&self.pipelines.rmsnorm, &bind_group, wg_x, 1, 1);

        let result = self.read_buffer(&x_buf, (seq_len * dim) as usize).await?;
        x[..(seq_len * dim) as usize].copy_from_slice(&result);
        Ok(())
    }

    /// GPU-accelerated softmax (row-wise, in-place)
    pub async fn softmax(
        &self,
        data: &mut [f32],
        rows: u32,
        cols: u32,
    ) -> Result<(), EngineError> {
        let meta = SoftmaxMeta { rows, cols, _p0: 0, _p1: 0 };
        let meta_buf = self.create_uniform(&meta);
        let data_buf = self.create_storage_rw_init(bytemuck::cast_slice(data));

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.softmax.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: data_buf.as_entire_binding() },
            ],
        });

        let wg_x = (rows + 255) / 256;
        self.dispatch(&self.pipelines.softmax, &bind_group, wg_x, 1, 1);

        let result = self.read_buffer(&data_buf, (rows * cols) as usize).await?;
        data[..(rows * cols) as usize].copy_from_slice(&result);
        Ok(())
    }

    /// GPU-accelerated gated SiLU FFN
    pub async fn gated_silu(
        &self,
        input: &[f32],
        n: u32,
        ffn_dim: u32,
    ) -> Result<Vec<f32>, EngineError> {
        let meta = GatedSiluMeta { n, ffn_dim, _p0: 0, _p1: 0 };
        let meta_buf = self.create_uniform(&meta);
        let in_buf = self.create_storage_read(bytemuck::cast_slice(input));
        let out_buf = self.create_storage_rw((n * ffn_dim) as usize * 4);

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.gated_silu.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: in_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: out_buf.as_entire_binding() },
            ],
        });

        let total = n * ffn_dim;
        let wg_x = (total + 255) / 256;
        self.dispatch(&self.pipelines.gated_silu, &bind_group, wg_x, 1, 1);

        self.read_buffer(&out_buf, (n * ffn_dim) as usize).await
    }

    /// GPU-accelerated residual add: x = x + residual
    pub async fn residual_add(
        &self,
        x: &mut [f32],
        residual: &[f32],
    ) -> Result<(), EngineError> {
        let total = x.len() as u32;
        let meta = ResidualMeta { total, _p0: 0, _p1: 0, _p2: 0 };
        let meta_buf = self.create_uniform(&meta);
        let x_buf = self.create_storage_rw_init(bytemuck::cast_slice(x));
        let r_buf = self.create_storage_read(bytemuck::cast_slice(residual));

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.residual_add.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: x_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: r_buf.as_entire_binding() },
            ],
        });

        let wg_x = (total + 255) / 256;
        self.dispatch(&self.pipelines.residual_add, &bind_group, wg_x, 1, 1);

        let result = self.read_buffer(&x_buf, total as usize).await?;
        x[..total as usize].copy_from_slice(&result);
        Ok(())
    }

    /// GPU-accelerated element-wise SiLU: y[i] = x[i] * sigmoid(x[i])
    pub async fn silu(&self, input: &[f32]) -> Result<Vec<f32>, EngineError> {
        let total = input.len() as u32;
        let meta = SiluMeta { total, _p0: 0, _p1: 0, _p2: 0 };
        let meta_buf = self.create_uniform(&meta);
        let in_buf = self.create_storage_read(bytemuck::cast_slice(input));
        let out_buf = self.create_storage_rw(input.len() * 4);

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.silu.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: in_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: out_buf.as_entire_binding() },
            ],
        });

        let wg_x = (total + 255) / 256;
        self.dispatch(&self.pipelines.silu, &bind_group, wg_x, 1, 1);
        self.read_buffer(&out_buf, total as usize).await
    }

    /// GPU-accelerated element-wise softplus: y[i] = ln(1 + exp(x[i]))
    pub async fn softplus(&self, input: &[f32]) -> Result<Vec<f32>, EngineError> {
        let total = input.len() as u32;
        let meta = SoftplusMeta { total, _p0: 0, _p1: 0, _p2: 0 };
        let meta_buf = self.create_uniform(&meta);
        let in_buf = self.create_storage_read(bytemuck::cast_slice(input));
        let out_buf = self.create_storage_rw(input.len() * 4);

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.softplus.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: in_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: out_buf.as_entire_binding() },
            ],
        });

        let wg_x = (total + 255) / 256;
        self.dispatch(&self.pipelines.softplus, &bind_group, wg_x, 1, 1);
        self.read_buffer(&out_buf, total as usize).await
    }

    /// Mamba2 SSM output: y[t,i] = sum_s(C[t,i,s]*dt[t,i]*B[t,i,s]) + D[i]*x[t,i]
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
        let meta = SsmOutputMeta { seq_len, inner, state_dim, _pad: 0 };
        let meta_buf = self.create_uniform(&meta);
        let x_buf = self.create_storage_read(bytemuck::cast_slice(x_in));
        let dt_buf = self.create_storage_read(bytemuck::cast_slice(dt));
        let b_buf = self.create_storage_read(bytemuck::cast_slice(b_val));
        let c_buf = self.create_storage_read(bytemuck::cast_slice(c_val));
        let d_buf = self.create_storage_read(bytemuck::cast_slice(d_val));
        let total = (seq_len * inner) as usize;
        let out_buf = self.create_storage_rw(total * 4);

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.ssm_output.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: x_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: dt_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: b_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 4, resource: c_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 5, resource: d_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 6, resource: out_buf.as_entire_binding() },
            ],
        });

        let wg_x = (total as u32 + 255) / 256;
        self.dispatch(&self.pipelines.ssm_output, &bind_group, wg_x, 1, 1);
        self.read_buffer(&out_buf, total).await
    }

    /// GPU-accelerated element-wise multiply: output[i] = a[i] * b[i]
    pub async fn elementwise_mul(
        &self,
        a: &[f32],
        b: &[f32],
    ) -> Result<Vec<f32>, EngineError> {
        let total = a.len() as u32;
        let meta = ElementwiseMulMeta { total, _p0: 0, _p1: 0, _p2: 0 };
        let meta_buf = self.create_uniform(&meta);
        let a_buf = self.create_storage_read(bytemuck::cast_slice(a));
        let b_buf = self.create_storage_read(bytemuck::cast_slice(b));
        let out_buf = self.create_storage_rw(a.len() * 4);

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipelines.elementwise_mul.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: meta_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: a_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: b_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: out_buf.as_entire_binding() },
            ],
        });

        let wg_x = (total + 255) / 256;
        self.dispatch(&self.pipelines.elementwise_mul, &bind_group, wg_x, 1, 1);
        self.read_buffer(&out_buf, total as usize).await
    }

    // --- internal helpers ---

    fn create_uniform<T: Pod>(&self, data: &T) -> wgpu::Buffer {
        wgpu::util::DeviceExt::create_buffer_init(
            &self.device,
            &wgpu::util::BufferInitDescriptor {
                label: None,
                contents: bytemuck::bytes_of(data),
                usage: wgpu::BufferUsages::UNIFORM,
            },
        )
    }

    fn create_storage_read(&self, data: &[u8]) -> wgpu::Buffer {
        wgpu::util::DeviceExt::create_buffer_init(
            &self.device,
            &wgpu::util::BufferInitDescriptor {
                label: None,
                contents: data,
                usage: wgpu::BufferUsages::STORAGE,
            },
        )
    }

    fn create_storage_rw(&self, size: usize) -> wgpu::Buffer {
        self.device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size: size as u64,
            usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
            mapped_at_creation: false,
        })
    }

    fn create_storage_rw_init(&self, data: &[u8]) -> wgpu::Buffer {
        wgpu::util::DeviceExt::create_buffer_init(
            &self.device,
            &wgpu::util::BufferInitDescriptor {
                label: None,
                contents: data,
                usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
            },
        )
    }

    fn dispatch(
        &self,
        pipeline: &wgpu::ComputePipeline,
        bind_group: &wgpu::BindGroup,
        x: u32,
        y: u32,
        z: u32,
    ) {
        let mut encoder = self.device.create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_compute_pass(&Default::default());
            pass.set_pipeline(pipeline);
            pass.set_bind_group(0, bind_group, &[]);
            pass.dispatch_workgroups(x, y, z);
        }
        self.queue.submit(std::iter::once(encoder.finish()));
    }

    async fn read_buffer(&self, buf: &wgpu::Buffer, count: usize) -> Result<Vec<f32>, EngineError> {
        let size = (count * 4) as u64;
        let staging = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size,
            usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let mut encoder = self.device.create_command_encoder(&Default::default());
        encoder.copy_buffer_to_buffer(buf, 0, &staging, 0, size);
        self.queue.submit(std::iter::once(encoder.finish()));

        let slice = staging.slice(..);
        let (tx, rx) = futures_channel::oneshot::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = tx.send(result);
        });

        // On native, poll(Wait) blocks until done. On browser (wasm32),
        // we must use poll(Poll) + yield to JS event loop to avoid deadlock.
        #[cfg(target_arch = "wasm32")]
        {
            self.device.poll(wgpu::Maintain::Poll);
        }
        #[cfg(not(target_arch = "wasm32"))]
        {
            self.device.poll(wgpu::Maintain::Wait);
        }

        rx.await
            .map_err(|_| EngineError::BufferMapFailed)?
            .map_err(|_| EngineError::BufferMapFailed)?;

        let data = slice.get_mapped_range();
        let result: Vec<f32> = bytemuck::cast_slice(&data).to_vec();
        drop(data);
        staging.unmap();
        Ok(result)
    }
}

fn create_pipeline(device: &wgpu::Device, wgsl: &str) -> wgpu::ComputePipeline {
    let module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: None,
        source: wgpu::ShaderSource::Wgsl(wgsl.into()),
    });
    device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
        label: None,
        layout: None,
        module: &module,
        entry_point: Some("main"),
        compilation_options: Default::default(),
        cache: None,
    })
}

/// CPU fallback matmul for small matrices (avoids GPU dispatch overhead)
fn cpu_matmul(a: &[f32], b: &[f32], m: u32, k: u32, n: u32, bias: Option<&[f32]>) -> Vec<f32> {
    let (m, k, n) = (m as usize, k as usize, n as usize);
    let mut c = vec![0.0f32; m * n];
    for i in 0..m {
        for j in 0..n {
            let mut acc = 0.0f32;
            for p in 0..k {
                acc += a[i * k + p] * b[p * n + j];
            }
            if let Some(bias) = bias {
                acc += bias[j];
            }
            c[i * n + j] = acc;
        }
    }
    c
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cpu_matmul() {
        let a = vec![1.0, 2.0, 3.0, 4.0]; // 2x2
        let b = vec![5.0, 6.0, 7.0, 8.0]; // 2x2
        let c = cpu_matmul(&a, &b, 2, 2, 2, None);
        assert_eq!(c, vec![19.0, 22.0, 43.0, 50.0]);
    }

    #[test]
    fn test_cpu_matmul_with_bias() {
        let a = vec![1.0, 0.0, 0.0, 1.0]; // 2x2 identity
        let b = vec![3.0, 4.0, 5.0, 6.0]; // 2x2
        let bias = vec![10.0, 20.0];
        let c = cpu_matmul(&a, &b, 2, 2, 2, Some(&bias));
        assert_eq!(c, vec![13.0, 24.0, 15.0, 26.0]);
    }
}
