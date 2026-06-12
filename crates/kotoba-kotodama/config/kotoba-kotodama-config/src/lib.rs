//! Container runtime configuration — single-tenant (1 Container = 1 component).
//! Source of truth is `kotodama.jsonld`. The Go CLI (`etzhayyim deploy`) generates
//! this TOML from JSON-LD for Container deploys. This crate parses the generated TOML.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KotodamaConfig {
    /// WASM component config. Optional — when absent, runs in graph-only mode
    /// (broker + REST API only, no WASM execution). Used by yata/pds containers.
    #[serde(default)]
    pub component: Option<ComponentConfig>,
    pub triggers: TriggerConfig,
    #[serde(default)]
    pub yata: YataConfig,
    #[serde(default)]
    pub pool: PoolConfig,
    /// Static site generation config — R2 FUSE mount output directory.
    #[serde(default, rename = "static")]
    pub static_site: Option<StaticSiteConfig>,
    /// W Protocol extensions — prebuild WASM components loaded at startup.
    #[serde(default, rename = "extensions")]
    pub extensions: Vec<ExtensionTomlConfig>,
    /// Cross-app interface declarations — provided and required WIT interfaces.
    #[serde(default)]
    pub interfaces: Option<InterfacesConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaticSiteConfig {
    /// S3 key prefix for pre-rendered pages in R2.
    /// Example: "keiba/static"
    pub prefix: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentConfig {
    pub path: PathBuf,
    #[serde(default)]
    pub env: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TriggerConfig {
    #[serde(default)]
    pub http: Option<HttpTriggerConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HttpTriggerConfig {
    #[serde(default = "default_listen")]
    pub listen: String,
    /// Routes dispatched to WASM (spin.toml format: "/api/...", "/health").
    /// Paths NOT matched here fall through to static_dir if configured.
    #[serde(default)]
    pub routes: Vec<String>,
    /// Directory to serve static files from (equivalent to spin-fileserver).
    /// Requests not matching `routes` are served from here.
    #[serde(default)]
    pub static_dir: Option<PathBuf>,
    /// If true, unmatched paths (not a real file) fall back to index.html.
    /// Use for SPA apps (Svelte, React, etc.) that use client-side routing.
    #[serde(default)]
    pub spa: bool,
}

fn default_listen() -> String {
    "0.0.0.0:8080".to_string()
}

impl Default for HttpTriggerConfig {
    fn default() -> Self {
        Self {
            listen: default_listen(),
            routes: vec![],
            static_dir: None,
            spa: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct YataConfig {
    #[serde(default = "default_data_dir")]
    pub data_dir: PathBuf,
    /// Graph data directory (CSR + MDAG CAS HEAD + vector index).
    #[serde(default = "default_graph_dir")]
    pub graph_data_dir: String,
    #[serde(default)]
    pub remote_endpoint: Option<String>,
    /// Base directory for graph data (CSR + MDAG CAS HEAD).
    #[serde(default)]
    pub graph_uri: Option<String>,
    /// Max vertices to load into memory per Sql query (default 50000, 0 = unlimited).
    #[serde(default)]
    pub graph_max_nodes: Option<usize>,
    /// Max edges to load into memory per Sql query (default 200000, 0 = unlimited).
    #[serde(default)]
    pub graph_max_edges: Option<usize>,
    /// S3-compatible cold storage (R2).
    /// TOML section: `[yata.s3]`.
    /// Ignored when `fuse = true`.
    #[serde(default)]
    pub s3: Option<S3TomlConfig>,
    /// R2 FUSE mount mode: data paths point to R2 FUSE mount.
    /// Filesystem writes go directly to R2 — no S3 API sync needed.
    #[serde(default)]
    pub fuse: bool,
}

/// S3-compatible cold storage config from `[yata.s3]` section in kotodama.toml.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct S3TomlConfig {
    pub endpoint: String,
    pub bucket: String,
    pub key_id: String,
    pub application_key: String,
    #[serde(default = "default_s3_region")]
    pub region: String,
    #[serde(default = "default_s3_prefix")]
    pub prefix: String,
    /// Eager sync: await remote upload (write-through).
    /// Use for CF Containers where disk is ephemeral.
    #[serde(default)]
    pub eager: bool,
}

fn default_s3_region() -> String {
    "us-west-004".to_string()
}
fn default_s3_prefix() -> String {
    "yata/".to_string()
}

fn default_data_dir() -> PathBuf {
    PathBuf::from("./kotodama-data")
}
fn default_graph_dir() -> String {
    "./kotodama-data/graph".to_string()
}

impl Default for YataConfig {
    fn default() -> Self {
        Self {
            data_dir: default_data_dir(),
            graph_data_dir: default_graph_dir(),
            remote_endpoint: None,
            graph_uri: None,
            graph_max_nodes: None,
            graph_max_edges: None,
            s3: None,
            fuse: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolConfig {
    #[serde(default = "default_pool_size")]
    pub size: usize,
}
fn default_pool_size() -> usize {
    1
}
impl Default for PoolConfig {
    fn default() -> Self {
        Self { size: 1 }
    }
}

/// Cross-app WIT interface declarations.
///
/// Each app declares provided interfaces (what it offers to other apps)
/// and required interfaces (what it needs from other apps).
/// Host registers these in Sql graph at Container startup.
///
/// ```toml
/// [interfaces]
/// package = "etzhayyim:handotai@0.1.0"
///
/// [[interfaces.provides]]
/// name = "news-feed"
/// description = "Semiconductor news aggregation"
/// functions = [{ name = "latest", params = "limit: u32", returns = "result<list<u8>, string>" }]
/// tags = ["semiconductor", "news"]
/// phase = "operational"
///
/// [[interfaces.requires]]
/// package = "etzhayyim:i18n@0.1.0"
/// interface = "translate"
/// functions = ["translate-text"]
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfacesConfig {
    /// WIT package namespace for this app's provided interfaces.
    pub package: String,
    /// Interfaces this app provides to other apps.
    #[serde(default)]
    pub provides: Vec<ProvidedInterface>,
    /// Interfaces this app requires from other apps.
    #[serde(default)]
    pub requires: Vec<RequiredInterface>,
}

/// A WIT interface this app provides to other apps.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProvidedInterface {
    /// Interface name (e.g. "news-feed").
    pub name: String,
    /// Human-readable description.
    #[serde(default)]
    pub description: String,
    /// Function signatures exposed by this interface.
    #[serde(default)]
    pub functions: Vec<InterfaceFunction>,
    /// Discovery tags (e.g. ["semiconductor", "news"]).
    #[serde(default)]
    pub tags: Vec<String>,
    /// Lifecycle phase: "operational", "developing", "planned", "retired".
    #[serde(default = "default_phase")]
    pub phase: String,
    /// Service tier for governance/linker selection (1 = platform, 2 = domain).
    #[serde(default = "default_service_tier")]
    pub tier: u8,
    /// Caller tiers allowed to invoke this interface (empty = any tier).
    #[serde(default)]
    pub allowed_caller_tiers: Vec<u8>,
    /// Restrict this interface to callers within the same org.
    #[serde(default)]
    pub same_org_only: bool,
    /// AI skill discovery hint — prompt for LLM agent routing.
    #[serde(default)]
    pub skill_prompt: String,
}

fn default_phase() -> String {
    "operational".to_string()
}
fn default_service_tier() -> u8 {
    2
}

/// A function signature within a provided interface.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfaceFunction {
    /// Function name (e.g. "latest").
    pub name: String,
    /// Parameter signature (human-readable, e.g. "limit: u32, lang: string").
    #[serde(default)]
    pub params: String,
    /// Return type (human-readable, e.g. "result<list<u8>, string>").
    #[serde(default)]
    pub returns: String,
}

/// A WIT interface this app requires from another app.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequiredInterface {
    /// Target package (e.g. "etzhayyim:i18n@0.1.0").
    pub package: String,
    /// Target interface name (e.g. "translate").
    pub interface: String,
    /// Required function names (subset validation at startup).
    #[serde(default)]
    pub functions: Vec<String>,
    /// Pin to a specific provider nanoid (optional).
    #[serde(default)]
    pub provider: String,
    /// Preferred provider tiers in resolution order (empty = runtime default).
    #[serde(default)]
    pub preferred_tiers: Vec<u8>,
    /// Allow linker to fall back outside preferred tiers.
    #[serde(default = "default_true")]
    pub allow_tier_fallback: bool,
}

fn default_true() -> bool {
    true
}

/// W Protocol extension declaration.
///
/// ```toml
/// [[extensions]]
/// name = "trade"
/// package = "etzhayyim:trade@0.1.0"
/// component = "extensions/trade-ext.wasm"
/// kinds = ["trade.order", "trade.cancel", "trade.*"]
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtensionTomlConfig {
    pub name: String,
    pub package: String,
    pub component: String,
    #[serde(default)]
    pub kinds: Vec<String>,
}

impl KotodamaConfig {
    pub fn from_file(path: impl AsRef<std::path::Path>) -> anyhow::Result<Self> {
        let content = std::fs::read_to_string(path)?;
        Ok(toml::from_str(&content)?)
    }

    pub fn from_str(s: &str) -> anyhow::Result<Self> {
        Ok(toml::from_str(s)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_minimal_config() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers.http]
listen = "0.0.0.0:8080"
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        assert_eq!(cfg.component.as_ref().unwrap().path.to_str().unwrap(), "component.wasm");
        assert!(cfg.triggers.http.is_some());
        let http = cfg.triggers.http.unwrap();
        assert_eq!(http.listen, "0.0.0.0:8080");
        assert!(http.routes.is_empty());
        assert!(!http.spa);
    }

    #[test]
    fn parse_graph_only_config() {
        let toml = r#"
[triggers]

[yata]
data_dir = "/data/yata"
graph_uri = "/data/yata/graph"
fuse = false
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        assert!(cfg.component.is_none());
        assert_eq!(cfg.yata.data_dir.to_str().unwrap(), "/data/yata");
    }

    #[test]
    fn parse_full_config() {
        let toml = r#"
[component]
path = "component.wasm"

[component.env]
SPIN_VARIABLE_FOO = "bar"

[triggers.http]
listen = "0.0.0.0:8080"
routes = ["/api/...", "/health"]
static_dir = "/app/static"
spa = true

[yata]
data_dir = "/data/yata"
graph_data_dir = "/data/graph"

[pool]
size = 2
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        assert_eq!(cfg.component.as_ref().unwrap().env.get("SPIN_VARIABLE_FOO").unwrap(), "bar");
        let http = cfg.triggers.http.unwrap();
        assert_eq!(http.routes.len(), 2);
        assert!(http.spa);
        assert_eq!(http.static_dir.unwrap().to_str().unwrap(), "/app/static");
        assert_eq!(cfg.yata.data_dir.to_str().unwrap(), "/data/yata");
        assert_eq!(cfg.pool.size, 2);
    }

    #[test]
    fn defaults_applied() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        assert_eq!(cfg.pool.size, 1);
        assert_eq!(cfg.yata.data_dir.to_str().unwrap(), "./kotodama-data");
        assert_eq!(cfg.yata.graph_data_dir, "./kotodama-data/graph");
        assert!(cfg.triggers.http.is_none());
        assert!(cfg.static_site.is_none());
        assert!(cfg.extensions.is_empty());
        assert!(cfg.interfaces.is_none());
        assert!(!cfg.yata.fuse);
    }

    #[test]
    fn parse_s3_config() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[yata.s3]
endpoint = "https://s3.example.com"
bucket = "mybucket"
key_id = "AKID"
application_key = "SECRET"
eager = true
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let s3 = cfg.yata.s3.unwrap();
        assert_eq!(s3.endpoint, "https://s3.example.com");
        assert_eq!(s3.bucket, "mybucket");
        assert_eq!(s3.region, "us-west-004");
        assert_eq!(s3.prefix, "yata/");
        assert!(s3.eager);
    }

    #[test]
    fn parse_extensions() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[[extensions]]
name = "trade"
package = "etzhayyim:trade@0.1.0"
component = "extensions/trade-ext.wasm"
kinds = ["trade.order", "trade.cancel"]

[[extensions]]
name = "notify"
package = "etzhayyim:notify@0.1.0"
component = "extensions/notify-ext.wasm"
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        assert_eq!(cfg.extensions.len(), 2);
        assert_eq!(cfg.extensions[0].name, "trade");
        assert_eq!(cfg.extensions[0].kinds, vec!["trade.order", "trade.cancel"]);
        assert_eq!(cfg.extensions[1].name, "notify");
        assert!(cfg.extensions[1].kinds.is_empty());
    }

    #[test]
    fn parse_static_site() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[static]
prefix = "keiba/static"
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let ss = cfg.static_site.unwrap();
        assert_eq!(ss.prefix, "keiba/static");
    }

    #[test]
    fn http_trigger_default() {
        let def = HttpTriggerConfig::default();
        assert_eq!(def.listen, "0.0.0.0:8080");
        assert!(def.routes.is_empty());
        assert!(!def.spa);
        assert!(def.static_dir.is_none());
    }

    #[test]
    fn pool_default() {
        let def = PoolConfig::default();
        assert_eq!(def.size, 1);
    }

    #[test]
    fn yata_default() {
        let def = YataConfig::default();
        assert_eq!(def.data_dir.to_str().unwrap(), "./kotodama-data");
        assert!(def.s3.is_none());
        assert!(!def.fuse);
    }

    #[test]
    fn parse_interfaces_config() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[interfaces]
package = "etzhayyim:handotai@0.1.0"

[[interfaces.provides]]
name = "news-feed"
description = "Semiconductor news aggregation"
functions = [
    { name = "latest", params = "limit: u32, lang: string", returns = "result<list<u8>, string>" },
    { name = "search", params = "query: string", returns = "result<list<u8>, string>" },
]
tags = ["semiconductor", "news", "intelligence"]
phase = "operational"
tier = 1
allowed_caller_tiers = [1, 2]
same_org_only = true
skill_prompt = "Use when asking about semiconductor news"

[[interfaces.provides]]
name = "translation"
description = "JP-EN semiconductor terminology"
functions = [
    { name = "translate", params = "text: string, from: string, to: string", returns = "result<string, string>" },
]
tags = ["nlp", "translation"]

[[interfaces.requires]]
package = "etzhayyim:i18n@0.1.0"
interface = "translate"
functions = ["translate-text", "detect-language"]
preferred_tiers = [1]

[[interfaces.requires]]
package = "etzhayyim:murakumo@0.1.0"
interface = "llm"
functions = ["chat"]
provider = "murakumo1"
allow_tier_fallback = false
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let ifaces = cfg.interfaces.unwrap();
        assert_eq!(ifaces.package, "etzhayyim:handotai@0.1.0");

        // Provided interfaces
        assert_eq!(ifaces.provides.len(), 2);
        assert_eq!(ifaces.provides[0].name, "news-feed");
        assert_eq!(ifaces.provides[0].functions.len(), 2);
        assert_eq!(ifaces.provides[0].functions[0].name, "latest");
        assert_eq!(
            ifaces.provides[0].tags,
            vec!["semiconductor", "news", "intelligence"]
        );
        assert_eq!(ifaces.provides[0].phase, "operational");
        assert_eq!(ifaces.provides[0].tier, 1);
        assert_eq!(ifaces.provides[0].allowed_caller_tiers, vec![1, 2]);
        assert!(ifaces.provides[0].same_org_only);
        assert_eq!(
            ifaces.provides[0].skill_prompt,
            "Use when asking about semiconductor news"
        );
        assert_eq!(ifaces.provides[1].name, "translation");
        assert_eq!(ifaces.provides[1].tags, vec!["nlp", "translation"]);
        // Default phase
        assert_eq!(ifaces.provides[1].phase, "operational");
        assert_eq!(ifaces.provides[1].tier, 2);

        // Required interfaces
        assert_eq!(ifaces.requires.len(), 2);
        assert_eq!(ifaces.requires[0].package, "etzhayyim:i18n@0.1.0");
        assert_eq!(ifaces.requires[0].interface, "translate");
        assert_eq!(
            ifaces.requires[0].functions,
            vec!["translate-text", "detect-language"]
        );
        assert!(ifaces.requires[0].provider.is_empty());
        assert_eq!(ifaces.requires[0].preferred_tiers, vec![1]);
        assert!(ifaces.requires[0].allow_tier_fallback);
        assert_eq!(ifaces.requires[1].provider, "murakumo1");
        assert!(!ifaces.requires[1].allow_tier_fallback);
    }

    #[test]
    fn parse_interfaces_provides_only() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[interfaces]
package = "etzhayyim:echo@0.1.0"

[[interfaces.provides]]
name = "echo"
functions = [{ name = "echo", params = "msg: string", returns = "string" }]
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let ifaces = cfg.interfaces.unwrap();
        assert_eq!(ifaces.provides.len(), 1);
        assert!(ifaces.requires.is_empty());
        assert_eq!(ifaces.provides[0].description, "");
        assert!(ifaces.provides[0].tags.is_empty());
        assert_eq!(ifaces.provides[0].tier, 2);
        assert_eq!(ifaces.provides[0].skill_prompt, "");
    }

    #[test]
    fn parse_interfaces_requires_only() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers]

[interfaces]
package = "etzhayyim:consumer@0.1.0"

[[interfaces.requires]]
package = "etzhayyim:i18n@0.1.0"
interface = "translate"
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let ifaces = cfg.interfaces.unwrap();
        assert!(ifaces.provides.is_empty());
        assert_eq!(ifaces.requires.len(), 1);
        assert!(ifaces.requires[0].functions.is_empty());
        assert!(ifaces.requires[0].preferred_tiers.is_empty());
        assert!(ifaces.requires[0].allow_tier_fallback);
    }

    #[test]
    fn roundtrip_serialization() {
        let toml = r#"
[component]
path = "component.wasm"

[triggers.http]
listen = "0.0.0.0:8080"
routes = ["/api/..."]

[pool]
size = 4
"#;
        let cfg = KotodamaConfig::from_str(toml).unwrap();
        let serialized = toml::to_string(&cfg).unwrap();
        let cfg2: KotodamaConfig = toml::from_str(&serialized).unwrap();
        assert_eq!(cfg2.pool.size, 4);
        assert_eq!(cfg2.triggers.http.unwrap().routes, vec!["/api/..."]);
    }
}
