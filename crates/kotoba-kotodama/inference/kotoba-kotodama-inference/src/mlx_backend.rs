//! MLX backend — Apple Silicon native Metal inference via mlx-c (runtime dlopen).
//! Compiled only on macOS arm64.
//!
//! Uses runtime dynamic loading (dlopen/dlsym) so the binary links without libmlx_c.
//! Falls back to wgpu if mlx-c is not installed.

use crate::wgpu_backend::EngineError;
use std::ffi::c_void;

type MlxStream = *mut c_void;
type MlxArray = *mut c_void;

const MLX_FLOAT32: i32 = 0;

macro_rules! mlx_fn {
    ($lib:expr, $name:ident, ($($arg:ty),*) -> $ret:ty) => {
        {
            let sym = unsafe {
                libc::dlsym($lib, concat!(stringify!($name), "\0").as_ptr() as *const _)
            };
            if sym.is_null() {
                return Err(EngineError::DeviceError(format!("mlx symbol not found: {}", stringify!($name))));
            }
            unsafe { std::mem::transmute::<_, unsafe extern "C" fn($($arg),*) -> $ret>(sym) }
        }
    };
}

/// Runtime-loaded MLX C function pointers (mlx-c v0.6.0+ symbol names)
struct MlxFns {
    default_gpu_stream: unsafe extern "C" fn() -> MlxStream,
    array_new_data: unsafe extern "C" fn(*const c_void, *const i32, i32, i32) -> MlxArray,
    array_eval: unsafe extern "C" fn(MlxArray),
    array_data_float32: unsafe extern "C" fn(MlxArray) -> *const f32,
    array_size: unsafe extern "C" fn(MlxArray) -> usize,
    array_free: unsafe extern "C" fn(MlxArray),
    matmul: unsafe extern "C" fn(MlxArray, MlxArray, MlxStream) -> MlxArray,
    multiply: unsafe extern "C" fn(MlxArray, MlxArray, MlxStream) -> MlxArray,
    add: unsafe extern "C" fn(MlxArray, MlxArray, MlxStream) -> MlxArray,
    softmax: unsafe extern "C" fn(MlxArray, i32, MlxStream) -> MlxArray,
    rsqrt: unsafe extern "C" fn(MlxArray, MlxStream) -> MlxArray,
    mean_axis: unsafe extern "C" fn(MlxArray, i32, bool, MlxStream) -> MlxArray,
    square: unsafe extern "C" fn(MlxArray, MlxStream) -> MlxArray,
}

fn find_mlx_lib() -> Option<String> {
    let paths = [
        "/opt/homebrew/lib/libmlxc.dylib",
        "/opt/homebrew/Cellar/mlx-c/0.6.0/lib/libmlxc.dylib",
        "/usr/local/lib/libmlxc.dylib",
        // Legacy naming
        "/opt/homebrew/lib/libmlx_c.dylib",
        "/usr/local/lib/libmlx_c.dylib",
    ];
    paths.iter().find(|p| std::path::Path::new(p).exists()).map(|s| s.to_string())
}

pub fn mlx_available() -> bool {
    find_mlx_lib().is_some()
}

fn load_mlx_fns() -> Result<(*mut c_void, MlxFns), EngineError> {
    let lib_path = find_mlx_lib()
        .ok_or_else(|| EngineError::DeviceError("libmlx_c.dylib not found".into()))?;

    let c_path = std::ffi::CString::new(lib_path.clone())
        .map_err(|_| EngineError::DeviceError("invalid path".into()))?;
    let handle = unsafe { libc::dlopen(c_path.as_ptr(), libc::RTLD_NOW) };
    if handle.is_null() {
        let err = unsafe { std::ffi::CStr::from_ptr(libc::dlerror()) };
        return Err(EngineError::DeviceError(format!("dlopen failed: {}", err.to_string_lossy())));
    }

    let fns = MlxFns {
        default_gpu_stream: mlx_fn!(handle, mlx_default_gpu_stream_new, () -> MlxStream),
        array_new_data: mlx_fn!(handle, mlx_array_new_data, (*const c_void, *const i32, i32, i32) -> MlxArray),
        array_eval: mlx_fn!(handle, mlx_array_eval, (MlxArray) -> ()),
        array_data_float32: mlx_fn!(handle, mlx_array_data_float32, (MlxArray) -> *const f32),
        array_size: mlx_fn!(handle, mlx_array_size, (MlxArray) -> usize),
        array_free: mlx_fn!(handle, mlx_array_free, (MlxArray) -> ()),
        matmul: mlx_fn!(handle, mlx_matmul, (MlxArray, MlxArray, MlxStream) -> MlxArray),
        multiply: mlx_fn!(handle, mlx_multiply, (MlxArray, MlxArray, MlxStream) -> MlxArray),
        add: mlx_fn!(handle, mlx_add, (MlxArray, MlxArray, MlxStream) -> MlxArray),
        softmax: mlx_fn!(handle, mlx_softmax, (MlxArray, i32, MlxStream) -> MlxArray),
        rsqrt: mlx_fn!(handle, mlx_rsqrt, (MlxArray, MlxStream) -> MlxArray),
        mean_axis: mlx_fn!(handle, mlx_mean_axis, (MlxArray, i32, bool, MlxStream) -> MlxArray),
        square: mlx_fn!(handle, mlx_square, (MlxArray, MlxStream) -> MlxArray),
    };

    Ok((handle, fns))
}

pub struct MlxEngine {
    _handle: *mut c_void,
    fns: MlxFns,
    stream: MlxStream,
}

// dlopen handle is safe to send across threads
unsafe impl Send for MlxEngine {}
unsafe impl Sync for MlxEngine {}

impl MlxEngine {
    pub fn new() -> Result<Self, EngineError> {
        let (handle, fns) = load_mlx_fns()?;
        let stream = unsafe { (fns.default_gpu_stream)() };
        if stream.is_null() {
            return Err(EngineError::NoGpu);
        }
        Ok(Self { _handle: handle, fns, stream })
    }

    fn make_array(&self, data: &[f32], shape: &[i32]) -> MlxArray {
        unsafe {
            (self.fns.array_new_data)(
                data.as_ptr() as *const _,
                shape.as_ptr(),
                shape.len() as i32,
                MLX_FLOAT32,
            )
        }
    }

    fn eval_to_vec(&self, arr: MlxArray) -> Vec<f32> {
        unsafe {
            (self.fns.array_eval)(arr);
            let size = (self.fns.array_size)(arr);
            let ptr = (self.fns.array_data_float32)(arr);
            std::slice::from_raw_parts(ptr, size).to_vec()
        }
    }

    fn free(&self, arr: MlxArray) {
        unsafe { (self.fns.array_free)(arr) }
    }

    pub fn matmul(
        &self,
        a: &[f32],
        b: &[f32],
        m: u32,
        k: u32,
        n: u32,
        bias: Option<&[f32]>,
    ) -> Result<Vec<f32>, EngineError> {
        let a_arr = self.make_array(a, &[m as i32, k as i32]);
        let b_arr = self.make_array(b, &[k as i32, n as i32]);

        let mut c_arr = unsafe { (self.fns.matmul)(a_arr, b_arr, self.stream) };

        if let Some(bias) = bias {
            let bias_arr = self.make_array(bias, &[1, n as i32]);
            let added = unsafe { (self.fns.add)(c_arr, bias_arr, self.stream) };
            self.free(c_arr);
            self.free(bias_arr);
            c_arr = added;
        }

        let result = self.eval_to_vec(c_arr);
        self.free(a_arr);
        self.free(b_arr);
        self.free(c_arr);
        Ok(result)
    }

    pub fn rmsnorm(
        &self,
        x: &mut [f32],
        weight: &[f32],
        seq_len: u32,
        dim: u32,
        eps: f32,
    ) -> Result<(), EngineError> {
        let x_arr = self.make_array(x, &[seq_len as i32, dim as i32]);
        let w_arr = self.make_array(weight, &[dim as i32]);
        let eps_arr = self.make_array(&[eps], &[1]);

        unsafe {
            let sq = (self.fns.square)(x_arr, self.stream);
            let mean_sq = (self.fns.mean_axis)(sq, -1, true, self.stream);
            let sum_eps = (self.fns.add)(mean_sq, eps_arr, self.stream);
            let rms = (self.fns.rsqrt)(sum_eps, self.stream);
            let normed = (self.fns.multiply)(x_arr, rms, self.stream);
            let result_arr = (self.fns.multiply)(normed, w_arr, self.stream);

            let result = self.eval_to_vec(result_arr);
            let size = (seq_len * dim) as usize;
            x[..size].copy_from_slice(&result[..size]);

            for arr in [x_arr, w_arr, eps_arr, sq, mean_sq, sum_eps, rms, normed, result_arr] {
                self.free(arr);
            }
        }
        Ok(())
    }

    pub fn softmax(
        &self,
        data: &mut [f32],
        rows: u32,
        cols: u32,
    ) -> Result<(), EngineError> {
        let arr = self.make_array(data, &[rows as i32, cols as i32]);
        let result_arr = unsafe { (self.fns.softmax)(arr, -1, self.stream) };
        let result = self.eval_to_vec(result_arr);
        let size = (rows * cols) as usize;
        data[..size].copy_from_slice(&result[..size]);
        self.free(arr);
        self.free(result_arr);
        Ok(())
    }

    pub fn gated_silu(
        &self,
        input: &[f32],
        n: u32,
        ffn_dim: u32,
    ) -> Result<Vec<f32>, EngineError> {
        // CPU fallback for gated SiLU (MLX doesn't have a single-call equivalent)
        let mut output = vec![0.0f32; (n * ffn_dim) as usize];
        for row in 0..n as usize {
            let in_offset = row * (ffn_dim as usize * 2);
            let out_offset = row * ffn_dim as usize;
            for col in 0..ffn_dim as usize {
                let gate = input[in_offset + col];
                let up = input[in_offset + ffn_dim as usize + col];
                let silu = gate / (1.0 + (-gate).exp());
                output[out_offset + col] = silu * up;
            }
        }
        Ok(output)
    }

    pub fn residual_add(
        &self,
        x: &mut [f32],
        residual: &[f32],
    ) -> Result<(), EngineError> {
        let len = x.len() as i32;
        let x_arr = self.make_array(x, &[len]);
        let r_arr = self.make_array(residual, &[len]);
        let result_arr = unsafe { (self.fns.add)(x_arr, r_arr, self.stream) };
        let result = self.eval_to_vec(result_arr);
        x.copy_from_slice(&result);
        self.free(x_arr);
        self.free(r_arr);
        self.free(result_arr);
        Ok(())
    }
}
