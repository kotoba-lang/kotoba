//! CoordinatorDO JSON protocol types — compatible with protocol.ts

use serde::{Deserialize, Serialize};

// Browser → Gateway message types
pub const MSG_REGISTER: &str = "register";
pub const MSG_HEARTBEAT: &str = "heartbeat";
pub const MSG_TASK_RESULT: &str = "task_result";
pub const MSG_TASK_FAILED: &str = "task_failed";
pub const MSG_CHECKPOINT: &str = "checkpoint";
pub const MSG_BYE: &str = "bye";
pub const MSG_TASK_TOKEN: &str = "task_token";

// Gateway → Browser message types
pub const MSG_REGISTERED: &str = "registered";
pub const MSG_TASK_PUSH: &str = "task_push";
pub const MSG_TASK_CANCEL: &str = "task_cancel";
pub const MSG_HEARTBEAT_ACK: &str = "heartbeat_ack";
pub const MSG_ERROR: &str = "error";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuCap {
    pub available: bool,
    pub adapter: String,
    pub features: Vec<String>,
    pub max_storage_buffer_binding_size: u64,
    pub max_compute_workgroup_storage_size: u64,
}

impl Default for GpuCap {
    fn default() -> Self {
        Self {
            available: false,
            adapter: "unknown".into(),
            features: vec![],
            max_storage_buffer_binding_size: 0,
            max_compute_workgroup_storage_size: 0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BrowserCapability {
    pub wasm_simd: bool,
    pub wasm_threads: bool,
    pub gpu: GpuCap,
    pub mem_class: String,
    pub net_class: String,
    pub power_class: String,
    pub gpu_tier: String,
    #[serde(default)]
    pub cores: u32,
    #[serde(default)]
    pub user_agent: String,
    #[serde(default)]
    pub runtime_class: String,
    #[serde(default)]
    pub accelerator_class: String,
    #[serde(default)]
    pub moq_available: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatteryState {
    pub charging: bool,
    pub level: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterMsg {
    pub capability: BrowserCapability,
    #[serde(default)]
    pub warm_shards: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisteredMsg {
    pub session_id: String,
    pub gpu_tier: String,
    pub heartbeat_interval_sec: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatMsg {
    pub session_id: String,
    pub visibility: String,
    pub battery: Option<BatteryState>,
    pub heap_pct: f32,
    pub shard_memory_mb: f32,
    #[serde(default)]
    pub warm_shards: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskPushMsg {
    pub lease_id: String,
    pub task_id: String,
    pub task_type: String,
    pub params: String,
    pub shader_hash: Option<String>,
    #[serde(default)]
    pub artifact_keys: Vec<String>,
    pub checkpoint_interval_sec: u32,
    pub timeout_sec: u32,
    pub verification_mode: Option<String>,
    pub runtime_class: Option<String>,
    pub accelerator_class: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResultMsg {
    pub lease_id: String,
    pub task_id: String,
    pub output: String,
    pub gpu_time_ms: u64,
    pub checksum: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskFailedMsg {
    pub lease_id: String,
    pub task_id: String,
    pub reason: String,
    pub error: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointMsg {
    pub lease_id: String,
    pub task_id: String,
    pub iteration: u32,
    pub state_b64: Option<String>,
    pub digest_sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskTokenMsg {
    pub task_id: String,
    pub token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskCancelMsg {
    pub lease_id: String,
    pub task_id: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorMsg {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatAckMsg {
    pub server_time: String,
}

/// Top-level WebSocket envelope — compatible with protocol.ts Envelope
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Envelope {
    #[serde(rename = "type")]
    pub msg_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub register: Option<RegisterMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub registered: Option<RegisteredMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub heartbeat: Option<HeartbeatMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub heartbeat_ack: Option<HeartbeatAckMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_push: Option<TaskPushMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_result: Option<TaskResultMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_failed: Option<TaskFailedMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_cancel: Option<TaskCancelMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checkpoint: Option<CheckpointMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorMsg>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_token: Option<TaskTokenMsg>,
}

impl Envelope {
    pub fn task_result(msg: TaskResultMsg) -> Self {
        Self {
            msg_type: MSG_TASK_RESULT.into(),
            task_result: Some(msg),
            register: None,
            registered: None,
            heartbeat: None,
            heartbeat_ack: None,
            task_push: None,
            task_failed: None,
            task_cancel: None,
            checkpoint: None,
            error: None,
            task_token: None,
        }
    }

    pub fn task_failed(msg: TaskFailedMsg) -> Self {
        Self {
            msg_type: MSG_TASK_FAILED.into(),
            task_failed: Some(msg),
            register: None,
            registered: None,
            heartbeat: None,
            heartbeat_ack: None,
            task_push: None,
            task_result: None,
            task_cancel: None,
            checkpoint: None,
            error: None,
            task_token: None,
        }
    }

    pub fn register(msg: RegisterMsg) -> Self {
        Self {
            msg_type: MSG_REGISTER.into(),
            register: Some(msg),
            registered: None,
            heartbeat: None,
            heartbeat_ack: None,
            task_push: None,
            task_result: None,
            task_failed: None,
            task_cancel: None,
            checkpoint: None,
            error: None,
            task_token: None,
        }
    }
}

pub fn tier_rank(tier: &str) -> u32 {
    match tier {
        "g4" => 4,
        "g3" => 3,
        "g2" => 2,
        "g1" => 1,
        _ => 0,
    }
}

pub fn classify_gpu_tier_from_gpu(gpu: &GpuCap, power_class: &str) -> String {
    if !gpu.available {
        return "g0".into();
    }
    let has_f16 = gpu.features.iter().any(|f| f == "shader-f16");
    let big_buf = gpu.max_storage_buffer_binding_size >= 256 * 1024 * 1024;
    let very_big_buf = gpu.max_storage_buffer_binding_size >= 1024 * 1024 * 1024;

    if has_f16 && very_big_buf && power_class == "desktop" {
        "g4".into()
    } else if has_f16 && big_buf {
        "g3".into()
    } else if has_f16 {
        "g2".into()
    } else {
        "g1".into()
    }
}

pub fn classify_gpu_tier(cap: &BrowserCapability) -> String {
    if !cap.gpu.available {
        return "g0".into();
    }
    let has_f16 = cap.gpu.features.iter().any(|f| f == "shader-f16");
    let big_buf = cap.gpu.max_storage_buffer_binding_size >= 256 * 1024 * 1024;
    let very_big_buf = cap.gpu.max_storage_buffer_binding_size >= 1024 * 1024 * 1024;

    if has_f16 && very_big_buf && cap.power_class == "desktop" {
        "g4".into()
    } else if has_f16 && big_buf {
        "g3".into()
    } else if has_f16 {
        "g2".into()
    } else {
        "g1".into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tier_rank() {
        assert_eq!(tier_rank("g4"), 4);
        assert_eq!(tier_rank("g0"), 0);
        assert_eq!(tier_rank("unknown"), 0);
    }

    #[test]
    fn test_envelope_roundtrip() {
        let env = Envelope::task_result(TaskResultMsg {
            lease_id: "lease-1".into(),
            task_id: "task-1".into(),
            output: "hello".into(),
            gpu_time_ms: 42,
            checksum: None,
        });
        let json = serde_json::to_string(&env).unwrap();
        let parsed: Envelope = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.msg_type, MSG_TASK_RESULT);
        assert_eq!(parsed.task_result.unwrap().gpu_time_ms, 42);
    }
}
