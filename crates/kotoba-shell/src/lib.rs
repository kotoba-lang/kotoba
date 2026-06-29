//! kotoba-shell — Tauri-shaped app shell planning over kotoba capabilities.
//!
//! This crate is the first executable slice of `docs/ADR-kotoba-shell-aiueos-safety-clj.md`.
//! It gives the shell line something concrete and testable: parse an EDN app
//! manifest, admit safe-clj components through kotoba-clj's deny-by-default
//! profile, and generate native shell artifacts from the same capability plan.

use std::collections::{BTreeMap, BTreeSet};
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, bail, Context, Result};
use kotoba_edn::{EdnValue, Keyword};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShellManifest {
    pub id: String,
    pub name: String,
    pub ui: Option<UiSpec>,
    pub components: Vec<ComponentSpec>,
    pub capabilities: BTreeMap<String, CapabilitySpec>,
    pub storage: Option<StorageSpec>,
    pub targets: BTreeSet<Target>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UiSpec {
    pub kind: String,
    pub entry: String,
    pub build: Option<String>,
    pub dist: Option<PathBuf>,
    pub index: Option<String>,
    pub build_command: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentSpec {
    pub id: String,
    pub source: PathBuf,
    pub safe: bool,
    pub exports: Vec<String>,
    pub imports: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilitySpec {
    pub name: String,
    pub platforms: BTreeSet<Target>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorageSpec {
    pub kind: Option<String>,
    pub encrypted: bool,
    pub sync: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Target {
    Macos,
    Ios,
    Android,
    Windows,
}

impl Target {
    pub fn parse(s: &str) -> Result<Target> {
        match s {
            "macos" | "darwin" | "mac" => Ok(Target::Macos),
            "ios" => Ok(Target::Ios),
            "android" => Ok(Target::Android),
            "windows" | "win" | "win32" => Ok(Target::Windows),
            other => bail!("unknown shell target `{other}`"),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Target::Macos => "macos",
            Target::Ios => "ios",
            Target::Android => "android",
            Target::Windows => "windows",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShellPlan {
    pub manifest_path: PathBuf,
    pub manifest_dir: PathBuf,
    pub app_id: String,
    pub app_name: String,
    pub ui_entry: Option<String>,
    pub ui_dist: Option<PathBuf>,
    pub ui_index: Option<String>,
    pub ui_build_command: Vec<String>,
    pub targets: BTreeSet<Target>,
    pub components: Vec<ComponentPlan>,
    pub native_capabilities: Vec<String>,
    pub capability_platforms: BTreeMap<String, BTreeSet<Target>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DevSession {
    pub dir: PathBuf,
    pub index_html: PathBuf,
    pub swift_runner: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BuildArtifact {
    pub target: Target,
    pub project_dir: PathBuf,
    pub app_bundle: PathBuf,
    pub executable: PathBuf,
    pub release_manifest: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SignatureReport {
    pub app_bundle: PathBuf,
    pub signed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectVerifyReport {
    pub target: Target,
    pub project_dir: PathBuf,
    pub checks: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SdkCheckStatus {
    Passed,
    Skipped,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoverageAssessment {
    pub schema: String,
    pub status: SdkCheckStatus,
    pub baseline: String,
    pub maturity: String,
    pub functional_coverage_percent: u8,
    pub release_maturity_percent: u8,
    pub categories: Vec<CoverageCategory>,
    pub implemented: Vec<String>,
    pub partial: Vec<String>,
    pub missing: Vec<String>,
    pub next_steps: Vec<String>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoverageCategory {
    pub id: String,
    pub label: String,
    pub score_percent: u8,
    pub maturity_percent: u8,
    pub status: CoverageStatus,
    pub evidence: Vec<String>,
    pub gaps: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CoverageStatus {
    Implemented,
    Partial,
    Missing,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SdkCheckReport {
    pub target: Target,
    pub project_dir: PathBuf,
    pub status: SdkCheckStatus,
    pub command: Vec<String>,
    pub detail: String,
    pub stdout: String,
    pub stderr: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeDoctorReport {
    pub target: Target,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing: Vec<String>,
    pub remediation: Vec<String>,
    pub remediation_commands: Vec<Vec<String>>,
    pub detail: String,
    pub command: Vec<String>,
    pub stdout: String,
    pub stderr: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExportArtifact {
    pub target: Target,
    pub dir: PathBuf,
    pub release_manifest: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReleaseCheckReport {
    pub target: Target,
    pub dir: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing_credentials: Vec<String>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SigningCheckReport {
    pub target: Target,
    pub dir: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing_credentials: Vec<String>,
    pub command: Vec<String>,
    pub detail: String,
    pub stdout: String,
    pub stderr: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SubmissionCheckReport {
    pub target: Target,
    pub dir: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing_credentials: Vec<String>,
    pub command: Vec<String>,
    pub detail: String,
    pub stdout: String,
    pub stderr: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceCheckReport {
    pub dir: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub entries: Vec<EvidenceEntry>,
    pub missing: Vec<String>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceEntry {
    pub file: PathBuf,
    pub status: SdkCheckStatus,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdapterCheckReport {
    pub target: Target,
    pub manifest: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing: Vec<String>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UpdaterCheckReport {
    pub target: Target,
    pub manifest: PathBuf,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub missing: Vec<String>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UpdaterFinalizeReport {
    pub target: Target,
    pub manifest: PathBuf,
    pub artifact: PathBuf,
    pub sha256: String,
    pub url: String,
    pub signature: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BrokerCheckReport {
    pub target: Target,
    pub app_id: String,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub dry_run: Option<BrokerDryRun>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BrokerDryRun {
    pub command: String,
    pub allowed: bool,
    pub provider: Option<String>,
    pub capability: Option<String>,
    pub audit_event: serde_json::Value,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SupervisorCheckReport {
    pub target: Target,
    pub app_id: String,
    pub status: SdkCheckStatus,
    pub checks: Vec<String>,
    pub components: Vec<ComponentSupervisorReport>,
    pub dry_run: Option<ComponentDryRunReport>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentSupervisorReport {
    pub id: String,
    pub safe: bool,
    pub status: ComponentStatus,
    pub source: PathBuf,
    pub wasm_bytes: Option<usize>,
    pub exports: Vec<String>,
    pub imports: Vec<String>,
    pub capability_surface: Vec<String>,
    pub inferred_effects: BTreeMap<String, Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentDryRunRequest {
    pub component: Option<String>,
    pub function: Option<String>,
    pub args: Vec<i64>,
    pub fuel: u64,
    pub host_adapter_manifest: Option<PathBuf>,
    pub adapter_timeout_seconds: u64,
    pub auth_grants: Vec<String>,
    pub kqe_snapshot: Vec<ComponentKqeQuad>,
    pub llm_echo: bool,
    pub llm_responses: Vec<ComponentLlmResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentDryRunReport {
    pub component: String,
    pub function: String,
    pub args: Vec<i64>,
    pub status: SdkCheckStatus,
    pub result: Option<i64>,
    pub host_events: Vec<ComponentHostEvent>,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentHostEvent {
    pub provider: String,
    pub operation: String,
    pub graph: String,
    pub subject: String,
    pub predicate: String,
    pub object: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentKqeQuad {
    pub graph: String,
    pub subject: String,
    pub predicate: String,
    pub object: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentLlmResponse {
    pub model: String,
    pub response: String,
}

#[derive(Debug, Clone)]
struct SupervisorHostState {
    auth_grants: BTreeSet<(String, String)>,
    kqe_snapshot: Vec<ComponentKqeQuad>,
    llm_echo: bool,
    llm_responses: BTreeMap<String, String>,
    live_adapters: Option<SupervisorLiveAdapters>,
    host_events: Vec<ComponentHostEvent>,
}

#[derive(Debug, Clone)]
struct SupervisorLiveAdapters {
    urls: BTreeMap<String, String>,
    timeout: Duration,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentPlan {
    pub id: String,
    pub source: PathBuf,
    pub safe: bool,
    pub status: ComponentStatus,
    pub exports: Vec<String>,
    pub imports: Vec<String>,
    pub wasm_bytes: Option<usize>,
    pub policy_edn: Option<String>,
    pub capability_surface: Vec<String>,
    pub inferred_effects: BTreeMap<String, Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ComponentStatus {
    Admitted,
    DeclaredOnly,
}

pub fn load_manifest_file(path: impl AsRef<Path>) -> Result<ShellManifest> {
    let path = path.as_ref();
    let src = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    parse_manifest(&src).with_context(|| format!("parse {}", path.display()))
}

pub fn parse_manifest(src: &str) -> Result<ShellManifest> {
    let value = kotoba_edn::parse(src).map_err(|e| anyhow!("EDN parse error: {e}"))?;
    let map = value
        .as_map()
        .ok_or_else(|| anyhow!("kotoba-shell manifest must be an EDN map"))?;

    let id = required_string(map, &["kotoba.app/id", "app/id", "id"])?;
    let name = required_string(map, &["kotoba.app/name", "app/name", "name"])?;
    let ui = optional_ui(map_get(map, &["ui"])).context("parse :ui")?;
    let components = optional_components(map_get(map, &["components"]))?;
    let capabilities = optional_capabilities(map_get(map, &["capabilities"]))?;
    let storage = optional_storage(map_get(map, &["storage"]))?;
    let targets = optional_targets(map_get(map, &["targets"]))?;

    Ok(ShellManifest {
        id,
        name,
        ui,
        components,
        capabilities,
        storage,
        targets,
    })
}

pub fn plan_manifest_file(path: impl AsRef<Path>) -> Result<ShellPlan> {
    let path = path.as_ref();
    let manifest = load_manifest_file(path)?;
    let base = path.parent().unwrap_or_else(|| Path::new("."));
    plan_manifest(path.to_path_buf(), base, manifest)
}

pub fn plan_manifest(
    manifest_path: PathBuf,
    base_dir: &Path,
    manifest: ShellManifest,
) -> Result<ShellPlan> {
    let mut components = Vec::new();
    for component in &manifest.components {
        let source = base_dir.join(&component.source);
        let component_plan = if component.safe {
            admit_safe_component(component, &source)?
        } else {
            ComponentPlan {
                id: component.id.clone(),
                source,
                safe: false,
                status: ComponentStatus::DeclaredOnly,
                exports: component.exports.clone(),
                imports: component.imports.clone(),
                wasm_bytes: None,
                policy_edn: None,
                capability_surface: Vec::new(),
                inferred_effects: BTreeMap::new(),
            }
        };
        components.push(component_plan);
    }

    let native_capabilities = manifest.capabilities.keys().cloned().collect();
    let capability_platforms = manifest
        .capabilities
        .iter()
        .map(|(name, spec)| (name.clone(), spec.platforms.clone()))
        .collect();
    Ok(ShellPlan {
        manifest_path,
        manifest_dir: base_dir.to_path_buf(),
        app_id: manifest.id,
        app_name: manifest.name,
        ui_entry: manifest.ui.as_ref().map(|u| u.entry.clone()),
        ui_dist: manifest.ui.as_ref().and_then(|u| u.dist.clone()),
        ui_index: manifest.ui.as_ref().and_then(|u| u.index.clone()),
        ui_build_command: manifest
            .ui
            .as_ref()
            .map(|u| u.build_command.clone())
            .unwrap_or_default(),
        targets: manifest.targets,
        components,
        native_capabilities,
        capability_platforms,
    })
}

pub fn format_plan(plan: &ShellPlan) -> String {
    let mut out = String::new();
    out.push_str(&format!("shell app {} ({})\n", plan.app_name, plan.app_id));
    if let Some(entry) = &plan.ui_entry {
        out.push_str(&format!("ui: {entry}\n"));
    }
    if let Some(dist) = &plan.ui_dist {
        out.push_str(&format!("ui dist: {}\n", dist.display()));
    }
    if !plan.ui_build_command.is_empty() {
        out.push_str(&format!(
            "ui build command: {}\n",
            plan.ui_build_command.join(" ")
        ));
    }
    let targets = plan
        .targets
        .iter()
        .map(|t| t.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    out.push_str(&format!(
        "targets: {}\n",
        if targets.is_empty() { "-" } else { &targets }
    ));
    out.push_str(&format!(
        "native capabilities: {}\n",
        if plan.native_capabilities.is_empty() {
            "-".to_string()
        } else {
            plan.native_capabilities.join(", ")
        }
    ));
    out.push_str("components:\n");
    for c in &plan.components {
        let status = match c.status {
            ComponentStatus::Admitted => "admitted",
            ComponentStatus::DeclaredOnly => "declared-only",
        };
        out.push_str(&format!(
            "  - {} [{}] {}",
            c.id,
            if c.safe { "safe" } else { "host" },
            status
        ));
        if let Some(bytes) = c.wasm_bytes {
            out.push_str(&format!(" ({bytes} wasm bytes)"));
        }
        out.push('\n');
        if !c.capability_surface.is_empty() {
            out.push_str(&format!(
                "    capability surface: {}\n",
                c.capability_surface.join(", ")
            ));
        }
        if !c.exports.is_empty() {
            out.push_str(&format!("    exports: {}\n", c.exports.join(", ")));
        }
        if !c.imports.is_empty() {
            out.push_str(&format!("    imports: {}\n", c.imports.join(", ")));
        }
        if let Some(policy) = &c.policy_edn {
            out.push_str("    minimal policy:\n");
            for line in policy.lines() {
                out.push_str("      ");
                out.push_str(line);
                out.push('\n');
            }
        }
    }
    out
}

pub fn coverage_assessment() -> CoverageAssessment {
    let categories = vec![
        coverage_category(
            "manifest-policy",
            "Manifest, safe-clj admission, and least-privilege policy",
            88,
            70,
            CoverageStatus::Partial,
            &[
                "EDN app manifest parser",
                "safe-clj component admission",
                "least-privilege policy synthesis",
                "target-aware capability filtering",
            ],
            &["schema evolution and compatibility guarantees are not stabilized"],
        ),
        coverage_category(
            "native-shells",
            "Native WebView shells and JS bridge",
            72,
            46,
            CoverageStatus::Partial,
            &[
                "macOS WKWebView runner",
                "iOS WKWebView scaffold",
                "Android Java WebView scaffold",
                "request/reply bridge with readiness marker",
            ],
            &[
                "iOS/Android real device or emulator runtime pass evidence is still missing",
                "Windows scaffold is metadata/run-script level, not a WebView2 host",
            ],
        ),
        coverage_category(
            "providers",
            "Capability-gated native providers",
            64,
            42,
            CoverageStatus::Partial,
            &[
                "fs/app-data on macOS",
                "notification, clipboard, http, keychain, contacts, and calendar provider paths",
                "Android runtime permission retry flow for contacts/calendar",
            ],
            &[
                "provider API is narrow compared with Tauri plugins",
                "cross-platform behavioral parity is not proven on devices",
            ],
        ),
        coverage_category(
            "aiueos-supervisor",
            "aiueos broker, safe component supervisor, and host adapters",
            78,
            58,
            CoverageStatus::Partial,
            &[
                "broker admission and dry-dispatch gate",
                "safe component supervisor under wasmtime fuel",
                "auth/kqe/llm host-bound dry-runs",
                "adapter readiness/probe/smoke response-contract gates",
            ],
            &[
                "hosted public HTTPS adapter pass evidence is required for release confidence",
                "durable aiueos audit integration is pending",
            ],
        ),
        coverage_category(
            "packaging-release",
            "Packaging, signing, submission, updater, and evidence gates",
            61,
            34,
            CoverageStatus::Partial,
            &[
                "macOS .app generation and local codesign verification",
                "iOS/Android project verifier and SDK compiler gates",
                "release checklist, store metadata, signing helpers, submission helpers",
                "updater manifest integrity/finalization gates",
                "aggregated evidence profiles",
            ],
            &[
                "credential-backed production signing evidence is missing",
                "real Apple notarization/App Store Connect and Google Play upload evidence is missing",
                "published updater feed evidence is missing",
            ],
        ),
        coverage_category(
            "ci-runtime",
            "CI/runtime verification",
            58,
            35,
            CoverageStatus::Partial,
            &[
                "SDK/runtime JSON evidence output",
                "runtime prerequisite doctor with remediation commands and optional Android boot probe",
                "CI live adapter fixture and dry runtime evidence artifact",
            ],
            &[
                "CI runtime-check currently accepts dry-run evidence",
            "Android AVD boot pass and iOS simulator boot pass are environment-dependent",
            ],
        ),
    ];

    CoverageAssessment {
        schema: "kotoba-shell.coverage.v0".to_string(),
        status: SdkCheckStatus::Passed,
        baseline: "Tauri v2 application shell baseline".to_string(),
        maturity: "alpha: SDK/debug-package-gated native scaffold with evidence-driven release gates"
            .to_string(),
        functional_coverage_percent: weighted_average(&categories, |category| {
            category.score_percent
        }),
        release_maturity_percent: weighted_average(&categories, |category| {
            category.maturity_percent
        }),
        implemented: vec![
            "EDN manifest parser, safe-clj admission, and policy synthesis".to_string(),
            "macOS/iOS/Android WebView scaffold generation".to_string(),
            "capability-gated bridge/provider paths for core shell commands".to_string(),
            "aiueos broker and safe component supervisor gates".to_string(),
            "release metadata, signing/submission/updater helper generation".to_string(),
            "SDK/runtime/doctor/evidence-check JSON reports".to_string(),
        ],
        partial: vec![
            "provider catalog is useful but much narrower than Tauri's plugin ecosystem"
                .to_string(),
            "mobile projects build/check, but real connected runtime evidence is not established"
                .to_string(),
            "release gates exist, but production credentials and store submission evidence are absent"
                .to_string(),
            "adapter contracts are checked, but public hosted production adapter evidence is pending"
                .to_string(),
        ],
        missing: vec![
            "passing iOS/Android device or emulator runtime verification for generated projects"
                .to_string(),
            "real notarization / store upload evidence from Apple/Google services".to_string(),
            "credential-backed production signing execution evidence".to_string(),
            "published updater feed evidence".to_string(),
            "Tauri-scale plugin ecosystem, updater UX, window/menu/tray breadth, and long-term compatibility policy"
                .to_string(),
        ],
        next_steps: vec![
            "repair Android AVD system image and capture a Passed android-runtime-evidence.json"
                .to_string(),
            "capture a Passed ios-runtime-evidence.json from a booted simulator or device".to_string(),
            "run signing-check --execute with real credentials and store signing evidence".to_string(),
            "run submission-check --execute against Apple/Google service credentials".to_string(),
            "publish a real HTTPS auth/kqe/llm adapter endpoint and run adapter-check --hosted --probe --smoke"
                .to_string(),
        ],
        detail:
            "coverage assessment generated; unresolved gaps are recorded under missing and categories.gaps"
                .to_string(),
        categories,
    }
}

pub fn coverage_report() -> String {
    let assessment = coverage_assessment();
    let mut out = String::new();
    out.push_str("kotoba-shell coverage against Tauri v2 baseline\n\n");
    out.push_str(&format!("Maturity: {}\n", assessment.maturity));
    out.push_str(&format!(
        "Estimated functional coverage: {}%\n",
        assessment.functional_coverage_percent
    ));
    out.push_str(&format!(
        "Estimated release maturity: {}%\n\n",
        assessment.release_maturity_percent
    ));
    out.push_str("Categories:\n");
    for category in &assessment.categories {
        out.push_str(&format!(
            "  [{mark}] {}: functionality {}%, maturity {}%\n",
            category.label,
            category.score_percent,
            category.maturity_percent,
            mark = coverage_status_mark(&category.status)
        ));
        for evidence in &category.evidence {
            out.push_str(&format!("      ok: {evidence}\n"));
        }
        for gap in &category.gaps {
            out.push_str(&format!("      gap: {gap}\n"));
        }
    }
    out.push_str("\nImplemented:\n");
    for item in &assessment.implemented {
        out.push_str(&format!("  [x] {item}\n"));
    }
    out.push_str("\nPartial:\n");
    for item in &assessment.partial {
        out.push_str(&format!("  [~] {item}\n"));
    }
    out.push_str("\nMissing:\n");
    for item in &assessment.missing {
        out.push_str(&format!("  [ ] {item}\n"));
    }
    out.push_str("\nNext coverage steps:\n");
    for item in &assessment.next_steps {
        out.push_str(&format!("  - {item}\n"));
    }
    out
}

fn coverage_category(
    id: &str,
    label: &str,
    score_percent: u8,
    maturity_percent: u8,
    status: CoverageStatus,
    evidence: &[&str],
    gaps: &[&str],
) -> CoverageCategory {
    CoverageCategory {
        id: id.to_string(),
        label: label.to_string(),
        score_percent,
        maturity_percent,
        status,
        evidence: evidence.iter().map(|item| item.to_string()).collect(),
        gaps: gaps.iter().map(|item| item.to_string()).collect(),
    }
}

fn coverage_status_mark(status: &CoverageStatus) -> &'static str {
    match status {
        CoverageStatus::Implemented => "x",
        CoverageStatus::Partial => "~",
        CoverageStatus::Missing => " ",
    }
}

fn weighted_average(
    categories: &[CoverageCategory],
    value: impl Fn(&CoverageCategory) -> u8,
) -> u8 {
    if categories.is_empty() {
        return 0;
    }
    let sum = categories
        .iter()
        .map(|category| value(category) as u32)
        .sum::<u32>();
    (sum / categories.len() as u32) as u8
}

pub fn broker_check_plan(
    plan: &ShellPlan,
    target: Target,
    command: Option<&str>,
) -> Result<BrokerCheckReport> {
    let capabilities = target_capabilities(plan, target);
    let providers = provider_catalog_json(&capabilities);
    let mut checks = Vec::new();
    checks.push("broker.verify:safe-clj-admission-before-provider-link".to_string());
    checks.push("broker.dispatch:capability-command".to_string());
    checks.push("broker.audit:append-only-command-log".to_string());
    for component in &plan.components {
        if component.safe && component.status != ComponentStatus::Admitted {
            bail!(
                "safe component `{}` was not admitted before provider link",
                component.id
            );
        }
        if component.safe {
            checks.push(format!("component:{}:safe-admitted", component.id));
        }
    }
    for provider in &providers {
        let provider_id = provider
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("provider catalog entry missing id"))?;
        let capability = provider
            .get("capability")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("provider catalog entry missing capability"))?;
        let commands = provider
            .get("commands")
            .and_then(|v| v.as_array())
            .ok_or_else(|| anyhow!("provider catalog entry missing commands"))?;
        for command in commands.iter().filter_map(|v| v.as_str()) {
            checks.push(format!(
                "provider:{provider_id}:command:{command}:capability:{capability}"
            ));
        }
    }
    let dry_run = command
        .map(|command| broker_dry_run(plan, target, command, &providers))
        .transpose()?;
    let status = if dry_run.as_ref().is_some_and(|r| !r.allowed) {
        SdkCheckStatus::Failed
    } else {
        SdkCheckStatus::Passed
    };
    let detail = if dry_run.is_some() {
        "aiueos shell broker admission and dry dispatch evaluated".to_string()
    } else {
        "aiueos shell broker admission evaluated".to_string()
    };
    Ok(BrokerCheckReport {
        target,
        app_id: plan.app_id.clone(),
        status,
        checks,
        dry_run,
        detail,
    })
}

fn broker_dry_run(
    plan: &ShellPlan,
    target: Target,
    command: &str,
    providers: &[serde_json::Value],
) -> Result<BrokerDryRun> {
    for provider in providers {
        let commands = provider
            .get("commands")
            .and_then(|v| v.as_array())
            .ok_or_else(|| anyhow!("provider catalog entry missing commands"))?;
        if commands
            .iter()
            .filter_map(|v| v.as_str())
            .any(|c| c == command)
        {
            let provider_id = provider
                .get("id")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            let capability = provider
                .get("capability")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            return Ok(BrokerDryRun {
                command: command.to_string(),
                allowed: true,
                provider: provider_id.clone(),
                capability: capability.clone(),
                audit_event: broker_audit_event(
                    plan,
                    target,
                    command,
                    true,
                    provider_id.as_deref(),
                    capability.as_deref(),
                    None,
                ),
            });
        }
    }
    Ok(BrokerDryRun {
        command: command.to_string(),
        allowed: false,
        provider: None,
        capability: None,
        audit_event: broker_audit_event(
            plan,
            target,
            command,
            false,
            None,
            None,
            Some("command is not granted by aiueos shell surface"),
        ),
    })
}

fn broker_audit_event(
    plan: &ShellPlan,
    target: Target,
    command: &str,
    ok: bool,
    provider: Option<&str>,
    capability: Option<&str>,
    error: Option<&str>,
) -> serde_json::Value {
    serde_json::json!({
        "schema": "aiueos.shell.audit.v0",
        "phase": "broker-dry-run",
        "app": plan.app_id,
        "target": target.as_str(),
        "command": command,
        "ok": ok,
        "provider": provider,
        "capability": capability,
        "error": error,
    })
}

pub fn append_broker_audit(path: impl AsRef<Path>, event: &serde_json::Value) -> Result<()> {
    let path = path.as_ref();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .with_context(|| format!("open broker audit log {}", path.display()))?;
    serde_json::to_writer(&mut file, event)
        .with_context(|| format!("write broker audit event {}", path.display()))?;
    file.write_all(b"\n")
        .with_context(|| format!("write broker audit newline {}", path.display()))?;
    Ok(())
}

pub fn supervisor_check_plan(
    plan: &ShellPlan,
    target: Target,
    dry_run_request: Option<ComponentDryRunRequest>,
) -> Result<SupervisorCheckReport> {
    let capabilities = target_capabilities(plan, target);
    let providers = provider_catalog_json(&capabilities);
    let provider_commands = providers
        .iter()
        .flat_map(|provider| {
            provider
                .get("commands")
                .and_then(|v| v.as_array())
                .into_iter()
                .flatten()
                .filter_map(|v| v.as_str())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .collect::<BTreeSet<_>>();

    let mut checks = Vec::new();
    checks.push("supervisor.graph:manifest-components-loaded".to_string());
    checks.push("supervisor.broker:target-provider-surface-loaded".to_string());
    checks.push("supervisor.audit:component-start-plan".to_string());

    let mut components = Vec::new();
    for component in &plan.components {
        if component.safe {
            if component.status != ComponentStatus::Admitted {
                bail!(
                    "supervisor cannot start safe component `{}` before admission",
                    component.id
                );
            }
            if component.policy_edn.is_none() {
                bail!(
                    "safe component `{}` is missing minimal policy evidence",
                    component.id
                );
            }
            if component.wasm_bytes.unwrap_or_default() == 0 {
                bail!(
                    "safe component `{}` has no compiled wasm evidence",
                    component.id
                );
            }
            checks.push(format!("component:{}:safe-admitted", component.id));
            checks.push(format!("component:{}:policy-minimal", component.id));
            checks.push(format!("component:{}:wasm-compiled", component.id));
        } else {
            checks.push(format!("component:{}:host-declared", component.id));
        }
        for export in &component.exports {
            checks.push(format!("component:{}:export:{export}", component.id));
        }
        for import in &component.imports {
            if provider_commands.contains(import) || capabilities.iter().any(|c| c == import) {
                checks.push(format!("component:{}:import:{import}:linked", component.id));
            } else {
                bail!(
                    "component `{}` imports `{import}`, but target {} does not expose it",
                    component.id,
                    target.as_str()
                );
            }
        }
        components.push(ComponentSupervisorReport {
            id: component.id.clone(),
            safe: component.safe,
            status: component.status.clone(),
            source: component.source.clone(),
            wasm_bytes: component.wasm_bytes,
            exports: component.exports.clone(),
            imports: component.imports.clone(),
            capability_surface: component.capability_surface.clone(),
            inferred_effects: component.inferred_effects.clone(),
        });
    }

    let dry_run = dry_run_request
        .map(|request| supervisor_dry_run(plan, target, request))
        .transpose()?;
    let status = match dry_run.as_ref().map(|d| &d.status) {
        Some(SdkCheckStatus::Failed) => SdkCheckStatus::Failed,
        Some(SdkCheckStatus::Skipped) => SdkCheckStatus::Skipped,
        _ => SdkCheckStatus::Passed,
    };
    let detail = match &dry_run {
        Some(dry_run) => format!(
            "aiueos component supervisor plan verified; dry-run {}.{} is {:?}",
            dry_run.component, dry_run.function, dry_run.status
        ),
        None => "aiueos component supervisor plan verified".to_string(),
    };
    Ok(SupervisorCheckReport {
        target,
        app_id: plan.app_id.clone(),
        status,
        checks,
        components,
        dry_run,
        detail,
    })
}

fn supervisor_dry_run(
    plan: &ShellPlan,
    target: Target,
    request: ComponentDryRunRequest,
) -> Result<ComponentDryRunReport> {
    let component = match &request.component {
        Some(id) => plan
            .components
            .iter()
            .find(|component| &component.id == id)
            .ok_or_else(|| anyhow!("component `{id}` not found"))?,
        None => plan
            .components
            .iter()
            .find(|component| component.safe)
            .ok_or_else(|| anyhow!("no safe component available for supervisor dry-run"))?,
    };
    if !component.safe {
        return Ok(ComponentDryRunReport {
            component: component.id.clone(),
            function: request.function.unwrap_or_else(|| "run".to_string()),
            args: request.args,
            status: SdkCheckStatus::Skipped,
            result: None,
            host_events: Vec::new(),
            detail: "host-declared component requires native host runtime".to_string(),
        });
    }
    let shell_host_surface = component.capability_surface.iter().all(|iface| {
        iface == "kotoba:kais/auth@0.1.0"
            || iface == "kotoba:kais/kqe@0.1.0"
            || iface == "kotoba:kais/llm@0.1.0"
    });
    if component.imports.is_empty()
        && !component.capability_surface.is_empty()
        && shell_host_surface
    {
        let function = request
            .function
            .or_else(|| component.exports.first().cloned())
            .unwrap_or_else(|| "run".to_string());
        if !component.exports.is_empty()
            && !component.exports.iter().any(|export| export == &function)
        {
            bail!(
                "component `{}` does not declare export `{function}`",
                component.id
            );
        }
        let body = std::fs::read_to_string(&component.source)
            .with_context(|| format!("read safe component {}", component.source.display()))?;
        let policy = kotoba_clj::minimal_policy(&body)
            .map_err(|e| anyhow!("infer minimal policy for {}: {e}", component.id))?;
        let wasm = kotoba_clj::compile_safe_clj_with_prelude(&body, &policy)
            .map_err(|e| anyhow!("safe compile for supervisor {}: {e}", component.id))?;
        let live_adapters = request
            .host_adapter_manifest
            .as_deref()
            .map(|path| {
                load_supervisor_live_adapters(
                    target,
                    path,
                    Duration::from_secs(request.adapter_timeout_seconds.max(1)),
                )
            })
            .transpose()?;
        let (result, host_events) = run_with_supervisor_hosts(
            &wasm,
            &function,
            &request.args,
            request.fuel,
            live_adapters,
            &request.auth_grants,
            &request.kqe_snapshot,
            request.llm_echo,
            &request.llm_responses,
        )
        .with_context(|| format!("supervisor host-bound dry-run {}.{function}", component.id))?;
        return Ok(ComponentDryRunReport {
            component: component.id.clone(),
            function,
            args: request.args,
            status: SdkCheckStatus::Passed,
            result: Some(result),
            host_events,
            detail: if request.host_adapter_manifest.is_some() {
                "safe-clj component executed with live production auth/kqe/llm host adapters under wasmtime fuel".to_string()
            } else {
                "safe-clj component executed with auth/kqe/llm host bindings under wasmtime fuel"
                    .to_string()
            },
        });
    }
    if !component.capability_surface.is_empty() || !component.imports.is_empty() {
        return Ok(ComponentDryRunReport {
            component: component.id.clone(),
            function: request
                .function
                .or_else(|| component.exports.first().cloned())
                .unwrap_or_else(|| "run".to_string()),
            args: request.args,
            status: SdkCheckStatus::Skipped,
            result: None,
            host_events: Vec::new(),
            detail: format!(
                "component requires unsupported host capability binding on target {}",
                target.as_str()
            ),
        });
    }
    let function = request
        .function
        .or_else(|| component.exports.first().cloned())
        .unwrap_or_else(|| "run".to_string());
    if !component.exports.is_empty() && !component.exports.iter().any(|export| export == &function)
    {
        bail!(
            "component `{}` does not declare export `{function}`",
            component.id
        );
    }
    let body = std::fs::read_to_string(&component.source)
        .with_context(|| format!("read safe component {}", component.source.display()))?;
    let policy = kotoba_clj::minimal_policy(&body)
        .map_err(|e| anyhow!("infer minimal policy for {}: {e}", component.id))?;
    let wasm = kotoba_clj::compile_safe_clj_with_prelude(&body, &policy)
        .map_err(|e| anyhow!("safe compile for supervisor {}: {e}", component.id))?;
    let result = kotoba_clj::run::run_with_fuel(&wasm, &function, &request.args, request.fuel)
        .map_err(|e| anyhow!("supervisor dry-run {}.{}: {e}", component.id, function))?;
    Ok(ComponentDryRunReport {
        component: component.id.clone(),
        function,
        args: request.args,
        status: SdkCheckStatus::Passed,
        result: Some(result),
        host_events: Vec::new(),
        detail: "pure safe-clj component executed under wasmtime fuel".to_string(),
    })
}

fn run_with_supervisor_hosts(
    wasm: &[u8],
    function: &str,
    args: &[i64],
    fuel: u64,
    live_adapters: Option<SupervisorLiveAdapters>,
    auth_grants: &[String],
    kqe_snapshot: &[ComponentKqeQuad],
    llm_echo: bool,
    llm_responses: &[ComponentLlmResponse],
) -> Result<(i64, Vec<ComponentHostEvent>)> {
    let mut config = wasmtime::Config::new();
    config.consume_fuel(true);
    let engine = wasmtime::Engine::new(&config)?;
    let module = wasmtime::Module::new(&engine, wasm)?;
    let mut linker = wasmtime::Linker::new(&engine);
    let grants = auth_grants
        .iter()
        .filter_map(|grant| grant.split_once(':'))
        .map(|(resource, ability)| (resource.to_string(), ability.to_string()))
        .collect::<BTreeSet<_>>();
    let llm_responses = llm_responses
        .iter()
        .map(|response| (response.model.clone(), response.response.clone()))
        .collect::<BTreeMap<_, _>>();
    let mut store = wasmtime::Store::new(
        &engine,
        SupervisorHostState {
            auth_grants: grants,
            kqe_snapshot: kqe_snapshot.to_vec(),
            llm_echo,
            llm_responses,
            live_adapters,
            host_events: Vec::new(),
        },
    );
    store.set_fuel(fuel)?;
    let auth = wasmtime::Func::wrap(
        &mut store,
        move |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
              resource_ptr: i32,
              resource_len: i32,
              ability_ptr: i32,
              ability_len: i32|
              -> i32 {
            let resource = read_guest_string(&mut caller, resource_ptr, resource_len);
            let ability = read_guest_string(&mut caller, ability_ptr, ability_len);
            match (resource, ability) {
                (Some(resource), Some(ability)) => {
                    if let Some(adapters) = caller.data().live_adapters.clone() {
                        let response = invoke_live_adapter_json(
                            "auth",
                            &adapters,
                            serde_json::json!({
                                "schema": "kotoba-shell.adapter-call.v0",
                                "operation": "auth.has-capability",
                                "resource": resource,
                                "ability": ability
                            }),
                        );
                        match response.and_then(|json| live_response_bool(&json, "allowed")) {
                            Ok(allowed) => {
                                caller.data_mut().host_events.push(ComponentHostEvent {
                                    provider: "kotoba:kais/auth@0.1.0".to_string(),
                                    operation: "has-capability".to_string(),
                                    graph: "live-adapter".to_string(),
                                    subject: resource,
                                    predicate: ability,
                                    object: allowed.to_string(),
                                });
                                return allowed as i32;
                            }
                            Err(err) => {
                                caller.data_mut().host_events.push(ComponentHostEvent {
                                    provider: "kotoba:kais/auth@0.1.0".to_string(),
                                    operation: "has-capability".to_string(),
                                    graph: "live-adapter".to_string(),
                                    subject: resource,
                                    predicate: ability,
                                    object: format!("err:{err}"),
                                });
                                return 0;
                            }
                        }
                    }
                    caller.data().auth_grants.contains(&(resource, ability)) as i32
                }
                _ => 0,
            }
        },
    );
    linker.define(&mut store, "kotoba:kais/auth@0.1.0", "has-capability", auth)?;
    let infer = wasmtime::Func::wrap(
        &mut store,
        |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
         model_ptr: i32,
         model_len: i32,
         prompt_ptr: i32,
         prompt_len: i32,
         result_area: i32| {
            let model = read_guest_string(&mut caller, model_ptr, model_len).unwrap_or_default();
            let prompt = read_guest_string(&mut caller, prompt_ptr, prompt_len).unwrap_or_default();
            if let Some(adapters) = caller.data().live_adapters.clone() {
                let response = invoke_live_adapter_json(
                    "llm",
                    &adapters,
                    serde_json::json!({
                        "schema": "kotoba-shell.adapter-call.v0",
                        "operation": "llm.infer",
                        "model": model,
                        "prompt": prompt
                    }),
                );
                match response.and_then(|json| live_response_string(&json, "output")) {
                    Ok(response) => {
                        write_guest_u8(&mut caller, result_area, 0, 0);
                        if let Some(ptr) = write_guest_bytes(&mut caller, response.as_bytes()) {
                            write_guest_i32(&mut caller, result_area, 4, ptr);
                            write_guest_i32(&mut caller, result_area, 8, response.len() as i32);
                        } else {
                            write_guest_i32(&mut caller, result_area, 4, 0);
                            write_guest_i32(&mut caller, result_area, 8, 0);
                        }
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/llm@0.1.0".to_string(),
                            operation: "infer".to_string(),
                            graph: "live-adapter".to_string(),
                            subject: model,
                            predicate: "ok".to_string(),
                            object: response,
                        });
                    }
                    Err(err) => {
                        write_guest_u8(&mut caller, result_area, 0, 1);
                        write_guest_i32(&mut caller, result_area, 4, 0);
                        write_guest_i32(&mut caller, result_area, 8, 0);
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/llm@0.1.0".to_string(),
                            operation: "infer".to_string(),
                            graph: "live-adapter".to_string(),
                            subject: model,
                            predicate: "err".to_string(),
                            object: err.to_string(),
                        });
                    }
                }
                return;
            }
            let response = caller
                .data()
                .llm_responses
                .get(&model)
                .cloned()
                .or_else(|| caller.data().llm_echo.then(|| format!("echo:{prompt}")));
            match response {
                Some(response) => {
                    write_guest_u8(&mut caller, result_area, 0, 0);
                    if let Some(ptr) = write_guest_bytes(&mut caller, response.as_bytes()) {
                        write_guest_i32(&mut caller, result_area, 4, ptr);
                        write_guest_i32(&mut caller, result_area, 8, response.len() as i32);
                    } else {
                        write_guest_i32(&mut caller, result_area, 4, 0);
                        write_guest_i32(&mut caller, result_area, 8, 0);
                    }
                    caller.data_mut().host_events.push(ComponentHostEvent {
                        provider: "kotoba:kais/llm@0.1.0".to_string(),
                        operation: "infer".to_string(),
                        graph: model,
                        subject: prompt,
                        predicate: "ok".to_string(),
                        object: response,
                    });
                }
                None => {
                    write_guest_u8(&mut caller, result_area, 0, 1);
                    write_guest_i32(&mut caller, result_area, 4, 0);
                    write_guest_i32(&mut caller, result_area, 8, 0);
                    caller.data_mut().host_events.push(ComponentHostEvent {
                        provider: "kotoba:kais/llm@0.1.0".to_string(),
                        operation: "infer".to_string(),
                        graph: model,
                        subject: prompt,
                        predicate: "err".to_string(),
                        object: "no llm dry-run response configured".to_string(),
                    });
                }
            }
        },
    );
    linker.define(&mut store, "kotoba:kais/llm@0.1.0", "infer", infer)?;
    let assert_quad = wasmtime::Func::wrap(
        &mut store,
        |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
         graph_ptr: i32,
         graph_len: i32,
         subject_ptr: i32,
         subject_len: i32,
         predicate_ptr: i32,
         predicate_len: i32,
         object_ptr: i32,
         object_len: i32,
         result_area: i32| {
            record_kqe_mutation(
                &mut caller,
                "assert-quad",
                graph_ptr,
                graph_len,
                subject_ptr,
                subject_len,
                predicate_ptr,
                predicate_len,
                object_ptr,
                object_len,
                result_area,
            );
        },
    );
    linker.define(
        &mut store,
        "kotoba:kais/kqe@0.1.0",
        "assert-quad",
        assert_quad,
    )?;
    let retract_quad = wasmtime::Func::wrap(
        &mut store,
        |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
         graph_ptr: i32,
         graph_len: i32,
         subject_ptr: i32,
         subject_len: i32,
         predicate_ptr: i32,
         predicate_len: i32,
         object_ptr: i32,
         object_len: i32,
         result_area: i32| {
            record_kqe_mutation(
                &mut caller,
                "retract-quad",
                graph_ptr,
                graph_len,
                subject_ptr,
                subject_len,
                predicate_ptr,
                predicate_len,
                object_ptr,
                object_len,
                result_area,
            );
        },
    );
    linker.define(
        &mut store,
        "kotoba:kais/kqe@0.1.0",
        "retract-quad",
        retract_quad,
    )?;
    let get_objects = wasmtime::Func::wrap(
        &mut store,
        |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
         graph_ptr: i32,
         graph_len: i32,
         subject_ptr: i32,
         subject_len: i32,
         predicate_ptr: i32,
         predicate_len: i32,
         result_area: i32| {
            let graph = read_guest_string(&mut caller, graph_ptr, graph_len).unwrap_or_default();
            let subject =
                read_guest_string(&mut caller, subject_ptr, subject_len).unwrap_or_default();
            let predicate =
                read_guest_string(&mut caller, predicate_ptr, predicate_len).unwrap_or_default();
            if let Some(adapters) = caller.data().live_adapters.clone() {
                let response = invoke_live_adapter_json(
                    "kqe",
                    &adapters,
                    serde_json::json!({
                        "schema": "kotoba-shell.adapter-call.v0",
                        "operation": "kqe.get-objects",
                        "graph": graph,
                        "subject": subject,
                        "predicate": predicate
                    }),
                );
                match response.and_then(|json| live_response_string_array(&json, "objects")) {
                    Ok(objects) => {
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/kqe@0.1.0".to_string(),
                            operation: "get-objects".to_string(),
                            graph,
                            subject,
                            predicate,
                            object: format!("{} live object(s)", objects.len()),
                        });
                        write_guest_object_list(&mut caller, result_area, &objects);
                    }
                    Err(err) => {
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/kqe@0.1.0".to_string(),
                            operation: "get-objects".to_string(),
                            graph,
                            subject,
                            predicate,
                            object: format!("err:{err}"),
                        });
                        write_guest_object_list(&mut caller, result_area, &[]);
                    }
                }
                return;
            }
            let objects = caller
                .data()
                .kqe_snapshot
                .iter()
                .filter(|quad| {
                    quad.graph == graph && quad.subject == subject && quad.predicate == predicate
                })
                .map(|quad| quad.object.clone())
                .collect::<Vec<_>>();
            caller.data_mut().host_events.push(ComponentHostEvent {
                provider: "kotoba:kais/kqe@0.1.0".to_string(),
                operation: "get-objects".to_string(),
                graph,
                subject,
                predicate,
                object: format!("{} object(s)", objects.len()),
            });
            write_guest_object_list(&mut caller, result_area, &objects);
        },
    );
    linker.define(
        &mut store,
        "kotoba:kais/kqe@0.1.0",
        "get-objects",
        get_objects,
    )?;
    let query = wasmtime::Func::wrap(
        &mut store,
        |mut caller: wasmtime::Caller<'_, SupervisorHostState>,
         filter_ptr: i32,
         filter_len: i32,
         result_area: i32| {
            let filter = read_guest_string(&mut caller, filter_ptr, filter_len).unwrap_or_default();
            if let Some(adapters) = caller.data().live_adapters.clone() {
                let response = invoke_live_adapter_json(
                    "kqe",
                    &adapters,
                    serde_json::json!({
                        "schema": "kotoba-shell.adapter-call.v0",
                        "operation": "kqe.query",
                        "filter": filter
                    }),
                );
                match response.and_then(|json| live_response_quads(&json)) {
                    Ok(quads) => {
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/kqe@0.1.0".to_string(),
                            operation: "query".to_string(),
                            graph: "live-adapter".to_string(),
                            subject: "*".to_string(),
                            predicate: filter,
                            object: format!("{} live quad(s)", quads.len()),
                        });
                        write_guest_u8(&mut caller, result_area, 0, 0);
                        write_guest_quad_list(&mut caller, result_area, &quads);
                    }
                    Err(err) => {
                        caller.data_mut().host_events.push(ComponentHostEvent {
                            provider: "kotoba:kais/kqe@0.1.0".to_string(),
                            operation: "query".to_string(),
                            graph: "live-adapter".to_string(),
                            subject: "*".to_string(),
                            predicate: filter,
                            object: format!("err:{err}"),
                        });
                        write_guest_u8(&mut caller, result_area, 0, 1);
                        write_guest_i32(&mut caller, result_area, 4, 0);
                        write_guest_i32(&mut caller, result_area, 8, 0);
                    }
                }
                return;
            }
            let quads = caller.data().kqe_snapshot.clone();
            caller.data_mut().host_events.push(ComponentHostEvent {
                provider: "kotoba:kais/kqe@0.1.0".to_string(),
                operation: "query".to_string(),
                graph: "*".to_string(),
                subject: "*".to_string(),
                predicate: filter,
                object: format!("{} quad(s)", quads.len()),
            });
            write_guest_u8(&mut caller, result_area, 0, 0);
            write_guest_quad_list(&mut caller, result_area, &quads);
        },
    );
    linker.define(&mut store, "kotoba:kais/kqe@0.1.0", "query", query)?;
    let instance = linker.instantiate(&mut store, &module)?;
    let f = instance
        .get_func(&mut store, function)
        .ok_or_else(|| anyhow!("module has no exported function `{function}`"))?;
    let params = args
        .iter()
        .map(|arg| wasmtime::Val::I64(*arg))
        .collect::<Vec<_>>();
    let mut results = vec![wasmtime::Val::I64(0)];
    f.call(&mut store, &params, &mut results)?;
    match results.first() {
        Some(wasmtime::Val::I64(v)) => Ok((*v, store.data().host_events.clone())),
        other => bail!("unexpected result kind: {other:?}"),
    }
}

fn read_guest_string(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    ptr: i32,
    len: i32,
) -> Option<String> {
    let memory = caller
        .get_export("memory")
        .and_then(wasmtime::Extern::into_memory)?;
    let ptr = usize::try_from(ptr).ok()?;
    let len = usize::try_from(len).ok()?;
    let end = ptr.checked_add(len)?;
    let data = memory.data(&caller);
    let bytes = data.get(ptr..end)?;
    std::str::from_utf8(bytes).ok().map(str::to_string)
}

#[allow(clippy::too_many_arguments)]
fn record_kqe_mutation(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    operation: &str,
    graph_ptr: i32,
    graph_len: i32,
    subject_ptr: i32,
    subject_len: i32,
    predicate_ptr: i32,
    predicate_len: i32,
    object_ptr: i32,
    object_len: i32,
    result_area: i32,
) {
    let graph = read_guest_string(caller, graph_ptr, graph_len).unwrap_or_default();
    let subject = read_guest_string(caller, subject_ptr, subject_len).unwrap_or_default();
    let predicate = read_guest_string(caller, predicate_ptr, predicate_len).unwrap_or_default();
    let object = read_guest_string(caller, object_ptr, object_len).unwrap_or_default();
    if let Some(adapters) = caller.data().live_adapters.clone() {
        let response = invoke_live_adapter_json(
            "kqe",
            &adapters,
            serde_json::json!({
                "schema": "kotoba-shell.adapter-call.v0",
                "operation": format!("kqe.{operation}"),
                "graph": graph,
                "subject": subject,
                "predicate": predicate,
                "object": object
            }),
        );
        match response.and_then(|json| live_response_bool(&json, "ok")) {
            Ok(true) => {
                caller.data_mut().host_events.push(ComponentHostEvent {
                    provider: "kotoba:kais/kqe@0.1.0".to_string(),
                    operation: operation.to_string(),
                    graph,
                    subject,
                    predicate,
                    object,
                });
                write_guest_u8(caller, result_area, 0, 0);
                write_guest_i32(caller, result_area, 4, 0);
                write_guest_i32(caller, result_area, 8, 0);
            }
            Ok(false) => {
                caller.data_mut().host_events.push(ComponentHostEvent {
                    provider: "kotoba:kais/kqe@0.1.0".to_string(),
                    operation: operation.to_string(),
                    graph,
                    subject,
                    predicate,
                    object: "err:adapter returned ok=false".to_string(),
                });
                write_guest_u8(caller, result_area, 0, 1);
                write_guest_i32(caller, result_area, 4, 0);
                write_guest_i32(caller, result_area, 8, 0);
            }
            Err(err) => {
                caller.data_mut().host_events.push(ComponentHostEvent {
                    provider: "kotoba:kais/kqe@0.1.0".to_string(),
                    operation: operation.to_string(),
                    graph,
                    subject,
                    predicate,
                    object: format!("err:{err}"),
                });
                write_guest_u8(caller, result_area, 0, 1);
                write_guest_i32(caller, result_area, 4, 0);
                write_guest_i32(caller, result_area, 8, 0);
            }
        }
        return;
    }
    caller.data_mut().host_events.push(ComponentHostEvent {
        provider: "kotoba:kais/kqe@0.1.0".to_string(),
        operation: operation.to_string(),
        graph,
        subject,
        predicate,
        object,
    });
    write_guest_u8(caller, result_area, 0, 0);
    write_guest_i32(caller, result_area, 4, 0);
    write_guest_i32(caller, result_area, 8, 0);
}

fn write_guest_u8(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    ptr: i32,
    offset: usize,
    value: u8,
) {
    if let Some(memory) = caller
        .get_export("memory")
        .and_then(wasmtime::Extern::into_memory)
    {
        if let Some(slot) = usize::try_from(ptr)
            .ok()
            .and_then(|ptr| ptr.checked_add(offset))
            .and_then(|index| memory.data_mut(caller).get_mut(index))
        {
            *slot = value;
        }
    }
}

fn write_guest_i32(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    ptr: i32,
    offset: usize,
    value: i32,
) {
    if let Some(memory) = caller
        .get_export("memory")
        .and_then(wasmtime::Extern::into_memory)
    {
        if let Some(start) = usize::try_from(ptr)
            .ok()
            .and_then(|ptr| ptr.checked_add(offset))
        {
            let data = memory.data_mut(caller);
            if let Some(slot) = data.get_mut(start..start + 4) {
                slot.copy_from_slice(&value.to_le_bytes());
            }
        }
    }
}

fn write_guest_object_list(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    result_area: i32,
    objects: &[String],
) {
    let Some(list_ptr) = guest_alloc(caller, 4, objects.len().saturating_mul(8)) else {
        write_guest_i32(caller, result_area, 0, 0);
        write_guest_i32(caller, result_area, 4, 0);
        return;
    };
    for (index, object) in objects.iter().enumerate() {
        if let Some(object_ptr) = write_guest_bytes(caller, object.as_bytes()) {
            let entry = list_ptr + (index as i32 * 8);
            write_guest_i32(caller, entry, 0, object_ptr);
            write_guest_i32(caller, entry, 4, object.len() as i32);
        }
    }
    write_guest_i32(caller, result_area, 0, list_ptr);
    write_guest_i32(caller, result_area, 4, objects.len() as i32);
}

fn write_guest_quad_list(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    result_area: i32,
    quads: &[ComponentKqeQuad],
) {
    let Some(list_ptr) = guest_alloc(caller, 4, quads.len().saturating_mul(32)) else {
        write_guest_i32(caller, result_area, 4, 0);
        write_guest_i32(caller, result_area, 8, 0);
        return;
    };
    for (index, quad) in quads.iter().enumerate() {
        let entry = list_ptr + (index as i32 * 32);
        for (field, value) in [&quad.graph, &quad.subject, &quad.predicate, &quad.object]
            .iter()
            .enumerate()
        {
            if let Some(ptr) = write_guest_bytes(caller, value.as_bytes()) {
                let field_entry = entry + (field as i32 * 8);
                write_guest_i32(caller, field_entry, 0, ptr);
                write_guest_i32(caller, field_entry, 4, value.len() as i32);
            }
        }
    }
    write_guest_i32(caller, result_area, 4, list_ptr);
    write_guest_i32(caller, result_area, 8, quads.len() as i32);
}

fn write_guest_bytes(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    bytes: &[u8],
) -> Option<i32> {
    let ptr = guest_alloc(caller, 1, bytes.len())?;
    let memory = caller
        .get_export("memory")
        .and_then(wasmtime::Extern::into_memory)?;
    let start = usize::try_from(ptr).ok()?;
    let end = start.checked_add(bytes.len())?;
    memory
        .data_mut(caller)
        .get_mut(start..end)?
        .copy_from_slice(bytes);
    Some(ptr)
}

fn guest_alloc(
    caller: &mut wasmtime::Caller<'_, SupervisorHostState>,
    align: usize,
    size: usize,
) -> Option<i32> {
    if size == 0 {
        return Some(0);
    }
    let realloc = caller
        .get_export("cabi_realloc")
        .and_then(wasmtime::Extern::into_func)?;
    let mut results = [wasmtime::Val::I32(0)];
    realloc
        .call(
            caller,
            &[
                wasmtime::Val::I32(0),
                wasmtime::Val::I32(0),
                wasmtime::Val::I32(i32::try_from(align).ok()?),
                wasmtime::Val::I32(i32::try_from(size).ok()?),
            ],
            &mut results,
        )
        .ok()?;
    match results[0] {
        wasmtime::Val::I32(ptr) => Some(ptr),
        _ => None,
    }
}

pub fn build_target(plan: &ShellPlan, target: Target) -> Result<BuildArtifact> {
    match target {
        Target::Macos => build_macos_app(plan, Path::new("target/kotoba-shell/build")),
        Target::Ios => build_ios_scaffold(plan, Path::new("target/kotoba-shell/build")),
        Target::Android => build_android_scaffold(plan, Path::new("target/kotoba-shell/build")),
        Target::Windows => build_windows_scaffold(plan, Path::new("target/kotoba-shell/build")),
    }
}

pub fn export_release_artifacts(
    plan: &ShellPlan,
    target: Target,
    out_root: impl AsRef<Path>,
) -> Result<ExportArtifact> {
    let dir = out_root
        .as_ref()
        .join(target.as_str())
        .join(safe_path_segment(&plan.app_name));
    if dir.exists() {
        std::fs::remove_dir_all(&dir).with_context(|| format!("clear {}", dir.display()))?;
    }
    std::fs::create_dir_all(&dir).with_context(|| format!("create {}", dir.display()))?;
    write_shell_metadata(plan, target, &dir)?;
    std::fs::write(
        dir.join("kotoba-shell-release-checklist.md"),
        release_checklist(plan, target),
    )
    .with_context(|| {
        format!(
            "write {}",
            dir.join("kotoba-shell-release-checklist.md").display()
        )
    })?;
    std::fs::write(
        dir.join("kotoba-shell-updater-manifest.json"),
        updater_manifest_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            dir.join("kotoba-shell-updater-manifest.json").display()
        )
    })?;
    std::fs::write(
        dir.join("kotoba-shell-signing-plan.json"),
        signing_plan_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            dir.join("kotoba-shell-signing-plan.json").display()
        )
    })?;
    std::fs::write(
        dir.join("kotoba-shell-evidence-profile.json"),
        evidence_profile_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            dir.join("kotoba-shell-evidence-profile.json").display()
        )
    })?;
    if matches!(target, Target::Macos | Target::Windows) {
        std::fs::write(
            dir.join("aiueos-portable-plan.json"),
            aiueos_portable_plan_json(plan, target)?,
        )
        .with_context(|| format!("write {}", dir.join("aiueos-portable-plan.json").display()))?;
        let core_script = dir.join("build-aiueos-core.bb");
        std::fs::write(
            &core_script,
            aiueos_portable_build_script(plan, target, false),
        )
        .with_context(|| format!("write {}", core_script.display()))?;
        make_executable(&core_script)?;
        let runner_script = dir.join("build-aiueos-runner.bb");
        std::fs::write(
            &runner_script,
            aiueos_portable_build_script(plan, target, true),
        )
        .with_context(|| format!("write {}", runner_script.display()))?;
        make_executable(&runner_script)?;
    }
    match target {
        Target::Macos => {
            let notarize_script = dir.join("notarize-macos.sh");
            std::fs::write(&notarize_script, macos_notarize_script(plan))
                .with_context(|| format!("write {}", notarize_script.display()))?;
            make_executable(&notarize_script)?;
            let sign_script = dir.join("sign-macos.sh");
            std::fs::write(&sign_script, macos_sign_script(plan))
                .with_context(|| format!("write {}", sign_script.display()))?;
            make_executable(&sign_script)?;
            std::fs::write(
                dir.join("app-store-connect-macos.json"),
                apple_store_metadata_json(plan, Target::Macos)?,
            )
            .with_context(|| {
                format!(
                    "write {}",
                    dir.join("app-store-connect-macos.json").display()
                )
            })?;
        }
        Target::Ios => {
            std::fs::write(
                dir.join("xcode-export-options.plist"),
                ios_export_options_plist(),
            )
            .with_context(|| {
                format!("write {}", dir.join("xcode-export-options.plist").display())
            })?;
            let sign_script = dir.join("sign-ios.sh");
            std::fs::write(&sign_script, ios_sign_script(plan))
                .with_context(|| format!("write {}", sign_script.display()))?;
            make_executable(&sign_script)?;
            let submit_script = dir.join("submit-ios.sh");
            std::fs::write(&submit_script, ios_submit_script(plan))
                .with_context(|| format!("write {}", submit_script.display()))?;
            make_executable(&submit_script)?;
            std::fs::write(
                dir.join("app-store-connect-ios.json"),
                apple_store_metadata_json(plan, Target::Ios)?,
            )
            .with_context(|| {
                format!("write {}", dir.join("app-store-connect-ios.json").display())
            })?;
        }
        Target::Android => {
            std::fs::write(dir.join("play-store-review.md"), android_store_review(plan))
                .with_context(|| format!("write {}", dir.join("play-store-review.md").display()))?;
            let sign_script = dir.join("sign-android.sh");
            std::fs::write(&sign_script, android_sign_script(plan))
                .with_context(|| format!("write {}", sign_script.display()))?;
            make_executable(&sign_script)?;
            let submit_script = dir.join("submit-android.sh");
            std::fs::write(&submit_script, android_submit_script(plan))
                .with_context(|| format!("write {}", submit_script.display()))?;
            make_executable(&submit_script)?;
            std::fs::write(
                dir.join("play-store-data-safety.json"),
                android_data_safety_json(plan)?,
            )
            .with_context(|| {
                format!(
                    "write {}",
                    dir.join("play-store-data-safety.json").display()
                )
            })?;
        }
        Target::Windows => {
            std::fs::write(
                dir.join("windows-security-review.md"),
                windows_security_review(plan),
            )
            .with_context(|| {
                format!("write {}", dir.join("windows-security-review.md").display())
            })?;
            let sign_script = dir.join("sign-windows.sh");
            std::fs::write(&sign_script, windows_sign_script(plan))
                .with_context(|| format!("write {}", sign_script.display()))?;
            make_executable(&sign_script)?;
            let reputation_script = dir.join("smartscreen-windows.sh");
            std::fs::write(&reputation_script, windows_smartscreen_script(plan))
                .with_context(|| format!("write {}", reputation_script.display()))?;
            make_executable(&reputation_script)?;
        }
    }
    Ok(ExportArtifact {
        target,
        release_manifest: dir.join("kotoba-shell-release.json"),
        dir,
    })
}

pub fn release_check_artifacts(
    target: Target,
    release_dir: impl AsRef<Path>,
) -> Result<ReleaseCheckReport> {
    let dir = release_dir.as_ref();
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    for (file, markers) in common_release_files(target) {
        require_file(dir, file, &markers, &mut checks)?;
    }
    for (file, markers) in target_release_files(target) {
        require_file(dir, file, &markers, &mut checks)?;
    }
    for script in target_release_scripts(target) {
        require_executable_file(dir, script, &mut checks)?;
    }
    for env in target_release_env(target) {
        if std::env::var_os(env).is_some() {
            checks.push(format!("env:{env}"));
        } else {
            missing.push(env.to_string());
        }
    }
    let status = if missing.is_empty() {
        SdkCheckStatus::Passed
    } else {
        SdkCheckStatus::Skipped
    };
    let detail = if missing.is_empty() {
        "release artifacts and credential environment are present".to_string()
    } else {
        format!(
            "release artifacts are present; credential-backed signing/upload skipped because {} env var(s) are missing",
            missing.len()
        )
    };
    Ok(ReleaseCheckReport {
        target,
        dir: dir.to_path_buf(),
        status,
        checks,
        missing_credentials: missing,
        detail,
    })
}

pub fn signing_check_artifacts(
    target: Target,
    release_dir: impl AsRef<Path>,
    execute: bool,
    artifact_or_project: Option<&Path>,
    output: Option<&Path>,
    timeout: Duration,
) -> Result<SigningCheckReport> {
    let dir = release_dir.as_ref();
    let release = release_check_artifacts(target, dir)?;
    let mut checks = release.checks;
    let missing = release.missing_credentials;
    let script = target_signing_script(target);
    require_executable_file(dir, script, &mut checks)?;
    require_file(
        dir,
        "kotoba-shell-signing-plan.json",
        &[
            "\"schema\": \"kotoba-shell.signing-plan.v0\"",
            "\"artifacts\"",
            "\"environment\"",
        ],
        &mut checks,
    )?;
    if !execute {
        let status = if missing.is_empty() {
            SdkCheckStatus::Passed
        } else {
            SdkCheckStatus::Skipped
        };
        let detail = if missing.is_empty() {
            "credential-backed signing execution is ready; use --execute to run the target signing helper".to_string()
        } else {
            format!(
                "signing execution skipped because {} credential env var(s) are missing",
                missing.len()
            )
        };
        return Ok(SigningCheckReport {
            target,
            dir: dir.to_path_buf(),
            status,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail,
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    if !missing.is_empty() {
        return Ok(SigningCheckReport {
            target,
            dir: dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail: "credential-backed signing execution skipped because credential env vars are missing".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    if timeout.is_zero() {
        return Ok(SigningCheckReport {
            target,
            dir: dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail: "signing execution dry-run requested with zero timeout".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    let args = signing_script_args(target, dir, artifact_or_project, output);
    run_signing_command(target, dir, script, &args, timeout, checks, missing)
}

pub fn submission_check_artifacts(
    target: Target,
    release_dir: impl AsRef<Path>,
    execute: bool,
    artifact: Option<&Path>,
    output: Option<&Path>,
    timeout: Duration,
) -> Result<SubmissionCheckReport> {
    let dir = release_dir.as_ref();
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    for (file, markers) in target_submission_files(target) {
        require_file(dir, file, &markers, &mut checks)?;
    }
    if let Some(script) = target_submission_script(target) {
        require_executable_file(dir, script, &mut checks)?;
    }
    for env in target_submission_env(target) {
        if std::env::var_os(env).is_some() {
            checks.push(format!("env:{env}"));
        } else {
            missing.push(env.to_string());
        }
    }
    if !execute {
        let status = if missing.is_empty() {
            SdkCheckStatus::Passed
        } else {
            SdkCheckStatus::Skipped
        };
        let detail = if missing.is_empty() {
            "store/notarization submission metadata and credential environment are ready; use --execute to run supported submission helpers".to_string()
        } else {
            format!(
                "submission execution skipped because {} credential env var(s) are missing",
                missing.len()
            )
        };
        return Ok(SubmissionCheckReport {
            target,
            dir: dir.to_path_buf(),
            status,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail,
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    if !missing.is_empty() {
        return Ok(SubmissionCheckReport {
            target,
            dir: dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail: "submission execution skipped because credential env vars are missing"
                .to_string(),
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    if timeout.is_zero() {
        return Ok(SubmissionCheckReport {
            target,
            dir: dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail: "submission execution dry-run requested with zero timeout".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        });
    }
    let Some(script) = target_submission_script(target) else {
        return Ok(SubmissionCheckReport {
            target,
            dir: dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            checks,
            missing_credentials: missing,
            command: Vec::new(),
            detail: "no store upload helper is configured for this target".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        });
    };
    let args = submission_script_args(target, artifact, output);
    run_submission_command(target, dir, script, &args, timeout, checks, missing)
}

pub fn evidence_check_dir(
    dir: impl AsRef<Path>,
    require_passed: &[String],
    profiles: &[String],
    profile_file: Option<&Path>,
) -> Result<EvidenceCheckReport> {
    let dir = dir.as_ref();
    let mut entries = Vec::new();
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    let mut requirements = require_passed.to_vec();
    let file_profiles = profile_file
        .map(load_evidence_profile_file)
        .transpose()?
        .unwrap_or_default();
    for profile in profiles {
        let expanded = resolve_evidence_profile(profile, &file_profiles)
            .ok_or_else(|| anyhow!("unknown evidence profile `{profile}`"))?;
        checks.push(format!("profile:{profile}"));
        requirements.extend(expanded);
    }
    let mut json_files = std::fs::read_dir(dir)
        .with_context(|| format!("read evidence dir {}", dir.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect::<Vec<_>>();
    json_files.sort();
    if json_files.is_empty() {
        missing.push("no JSON evidence files found".to_string());
    }
    for path in json_files {
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("read evidence {}", path.display()))?;
        let json: serde_json::Value =
            serde_json::from_str(&text).with_context(|| format!("parse {}", path.display()))?;
        if is_evidence_profile_json(&json) {
            checks.push(format!(
                "evidence-profile:{}:ignored",
                path.file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or("<unknown>")
            ));
            continue;
        }
        if is_evidence_summary_json(&json) {
            checks.push(format!(
                "evidence-summary:{}:ignored",
                path.file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or("<unknown>")
            ));
            continue;
        }
        let status = json
            .get("status")
            .and_then(|v| v.as_str())
            .and_then(parse_evidence_status)
            .ok_or_else(|| anyhow!("{} is missing status", path.display()))?;
        let detail = json
            .get("detail")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        checks.push(format!(
            "evidence:{}:{:?}",
            path.file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("<unknown>"),
            status
        ));
        entries.push(EvidenceEntry {
            file: path,
            status,
            detail,
        });
    }
    requirements.sort();
    requirements.dedup();
    for required in &requirements {
        match entries
            .iter()
            .find(|entry| evidence_name_matches(entry, required))
        {
            Some(entry) if entry.status == SdkCheckStatus::Passed => {
                checks.push(format!("required:{required}:Passed"));
            }
            Some(entry) => {
                missing.push(format!("{required} is {:?}, expected Passed", entry.status))
            }
            None => missing.push(format!("{required} is missing")),
        }
    }
    let failed = entries
        .iter()
        .filter(|entry| entry.status == SdkCheckStatus::Failed)
        .count();
    let skipped = entries
        .iter()
        .filter(|entry| entry.status == SdkCheckStatus::Skipped)
        .count();
    let status = if failed > 0 || !missing.is_empty() {
        SdkCheckStatus::Failed
    } else if skipped > 0 {
        SdkCheckStatus::Skipped
    } else {
        SdkCheckStatus::Passed
    };
    let detail = format!(
        "{} evidence file(s), {failed} failed, {skipped} skipped, {} missing/unsatisfied requirement(s)",
        entries.len(),
        missing.len()
    );
    Ok(EvidenceCheckReport {
        dir: dir.to_path_buf(),
        status,
        checks,
        entries,
        missing,
        detail,
    })
}

fn evidence_profile_requirements(profile: &str) -> Option<Vec<&'static str>> {
    match profile {
        "ci" => Some(vec![
            "coverage-evidence.json",
            "live-adapter-supervisor-evidence.json",
        ]),
        "android-release" => Some(vec![
            "coverage-evidence.json",
            "android-runtime-doctor-evidence.json",
            "android-sdk-evidence.json",
            "android-runtime-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ]),
        "store-release" => Some(vec![
            "coverage-evidence.json",
            "runtime-doctor-evidence.json",
            "sdk-evidence.json",
            "runtime-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ]),
        _ => None,
    }
}

fn resolve_evidence_profile(
    profile: &str,
    file_profiles: &BTreeMap<String, Vec<String>>,
) -> Option<Vec<String>> {
    if profile == "release" {
        if let Some(requirements) = file_profiles.get("android-release") {
            return Some(requirements.clone());
        }
        if let Some(requirements) = file_profiles.get("store-release") {
            return Some(requirements.clone());
        }
    }
    file_profiles.get(profile).cloned().or_else(|| {
        evidence_profile_requirements(profile)
            .map(|requirements| requirements.into_iter().map(str::to_string).collect())
    })
}

fn release_evidence_profile_requirements(target: Target) -> Vec<&'static str> {
    match target {
        Target::Android => vec![
            "coverage-evidence.json",
            "android-runtime-doctor-evidence.json",
            "android-sdk-evidence.json",
            "android-runtime-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ],
        Target::Ios => vec![
            "coverage-evidence.json",
            "ios-runtime-doctor-evidence.json",
            "ios-sdk-evidence.json",
            "ios-runtime-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ],
        Target::Macos => vec![
            "coverage-evidence.json",
            "macos-runtime-doctor-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ],
        Target::Windows => vec![
            "coverage-evidence.json",
            "windows-runtime-doctor-evidence.json",
            "hosted-adapter-ready-evidence.json",
            "live-adapter-supervisor-evidence.json",
            "signing-ready-evidence.json",
            "submission-ready-evidence.json",
        ],
    }
}

fn load_evidence_profile_file(path: &Path) -> Result<BTreeMap<String, Vec<String>>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let json: serde_json::Value =
        serde_json::from_str(&text).with_context(|| format!("parse {}", path.display()))?;
    require_json_string(
        &json,
        "schema",
        "kotoba-shell.evidence-profile.v0",
        &mut Vec::new(),
    )?;
    let profiles = json
        .get("profiles")
        .and_then(|v| v.as_object())
        .ok_or_else(|| anyhow!("evidence profile manifest is missing profiles"))?;
    profiles
        .iter()
        .map(|(name, requirements)| {
            let requirements = requirements
                .as_array()
                .ok_or_else(|| anyhow!("profile `{name}` must be an array"))?
                .iter()
                .map(|v| {
                    v.as_str()
                        .map(str::to_string)
                        .ok_or_else(|| anyhow!("profile `{name}` entries must be strings"))
                })
                .collect::<Result<Vec<_>>>()?;
            Ok((name.clone(), requirements))
        })
        .collect()
}

fn is_evidence_summary_json(json: &serde_json::Value) -> bool {
    json.get("entries").and_then(|v| v.as_array()).is_some()
        && json.get("dir").and_then(|v| v.as_str()).is_some()
        && json.get("missing").and_then(|v| v.as_array()).is_some()
}

fn is_evidence_profile_json(json: &serde_json::Value) -> bool {
    json.get("schema").and_then(|v| v.as_str()) == Some("kotoba-shell.evidence-profile.v0")
}

pub fn adapter_check_manifest(
    target: Target,
    manifest_path: impl AsRef<Path>,
    probe: bool,
    smoke: bool,
    hosted: bool,
    timeout: Duration,
) -> Result<AdapterCheckReport> {
    let manifest_path = manifest_path.as_ref();
    let src = std::fs::read_to_string(manifest_path)
        .with_context(|| format!("read {}", manifest_path.display()))?;
    let json: serde_json::Value =
        serde_json::from_str(&src).with_context(|| format!("parse {}", manifest_path.display()))?;
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    require_json_string(
        &json,
        "schema",
        "kotoba-shell.host-adapters.v0",
        &mut checks,
    )?;
    require_json_string(&json, "target", target.as_str(), &mut checks)?;
    let adapters = json
        .get("adapters")
        .and_then(|v| v.as_array())
        .ok_or_else(|| anyhow!("host adapter manifest is missing adapters array"))?;
    for adapter in adapters {
        let id = adapter
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("host adapter entry missing id"))?;
        checks.push(format!("adapter:{id}"));
        let required = adapter
            .get("required")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let response_contract = adapter
            .pointer("/smokeInvocation/response")
            .ok_or_else(|| anyhow!("adapter:{id} missing smokeInvocation.response"))?;
        validate_adapter_smoke_response_contract(id, response_contract)?;
        checks.push(format!("adapter:{id}:smoke-response-contract"));
        for env in adapter
            .get("env")
            .and_then(|v| v.as_array())
            .into_iter()
            .flatten()
            .filter_map(|v| v.as_str())
        {
            if !required {
                checks.push(format!("adapter:{id}:env:{env}:optional"));
            } else if let Some(value) = std::env::var_os(env) {
                let url = value.to_string_lossy();
                checks.push(format!("adapter:{id}:env:{env}"));
                if hosted {
                    match validate_hosted_adapter_url(&url) {
                        Ok(detail) => checks.push(format!("adapter:{id}:hosted:{detail}")),
                        Err(err) => missing.push(format!("{id}:hosted:{err}")),
                    }
                }
                if probe {
                    match probe_adapter_endpoint(&url, timeout) {
                        Ok(detail) => checks.push(format!("adapter:{id}:probe:{detail}")),
                        Err(err) => missing.push(format!("{id}:probe:{err}")),
                    }
                }
                if smoke {
                    match smoke_adapter_endpoint(id, &url, timeout) {
                        Ok(detail) => checks.push(format!("adapter:{id}:smoke:{detail}")),
                        Err(err) => missing.push(format!("{id}:smoke:{err}")),
                    }
                }
            } else {
                missing.push(format!("{id}:{env}"));
            }
        }
    }
    let status = if missing.is_empty() {
        SdkCheckStatus::Passed
    } else {
        SdkCheckStatus::Skipped
    };
    let detail = if missing.is_empty() {
        if smoke {
            if hosted {
                "hosted production adapter environment, HTTPS deployment endpoints, endpoint probes, invocation smoke tests, and response contracts are ready".to_string()
            } else {
                "production host service adapter environment, endpoint probes, invocation smoke tests, and response contracts are ready".to_string()
            }
        } else if probe {
            "production host service adapter environment and endpoint probes are ready".to_string()
        } else if hosted {
            "hosted production adapter environment and HTTPS deployment endpoints are ready"
                .to_string()
        } else {
            "production host service adapter environment is ready".to_string()
        }
    } else {
        format!(
            "host adapter manifest is valid; production adapter execution skipped because {} env var(s) are missing",
            missing.len()
        )
    };
    Ok(AdapterCheckReport {
        target,
        manifest: manifest_path.to_path_buf(),
        status,
        checks,
        missing,
        detail,
    })
}

fn probe_adapter_endpoint(url: &str, timeout: Duration) -> Result<String> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        bail!("adapter URL must start with http:// or https://");
    }
    let curl = Command::new("curl")
        .arg("--fail")
        .arg("--silent")
        .arg("--show-error")
        .arg("--head")
        .arg("--max-time")
        .arg(timeout.as_secs().max(1).to_string())
        .arg(url)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();
    match curl {
        Ok(output) if output.status.success() => Ok(format!("ok:{url}")),
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            let msg = if stderr.is_empty() {
                format!("curl exited with {}", output.status)
            } else {
                stderr
            };
            bail!("{url}: {msg}")
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            bail!("curl not found")
        }
        Err(err) => Err(err).with_context(|| format!("probe {url}")),
    }
}

fn validate_hosted_adapter_url(url: &str) -> Result<String> {
    let Some(rest) = url.strip_prefix("https://") else {
        bail!("hosted adapter URL must start with https://");
    };
    let host_port = rest
        .split('/')
        .next()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow!("hosted adapter URL is missing host"))?;
    let host = host_port
        .strip_prefix('[')
        .and_then(|s| s.split_once(']').map(|(host, _)| host))
        .unwrap_or_else(|| host_port.split(':').next().unwrap_or(host_port))
        .trim_end_matches('.');
    if host.is_empty() {
        bail!("hosted adapter URL is missing host");
    }
    let lower = host.to_ascii_lowercase();
    if matches!(lower.as_str(), "localhost" | "0.0.0.0")
        || lower.ends_with(".localhost")
        || lower.ends_with(".local")
        || lower.ends_with(".invalid")
        || lower.ends_with(".test")
        || lower.ends_with(".example")
    {
        bail!("hosted adapter URL must not use local or reserved test host `{host}`");
    }
    if let Ok(ip) = lower.parse::<std::net::IpAddr>() {
        if !is_public_ip(ip) {
            bail!("hosted adapter URL must not use private/local IP `{host}`");
        }
    }
    Ok(format!("https:{host}"))
}

fn is_public_ip(ip: std::net::IpAddr) -> bool {
    match ip {
        std::net::IpAddr::V4(ip) => {
            !(ip.is_private()
                || ip.is_loopback()
                || ip.is_link_local()
                || ip.is_broadcast()
                || ip.is_documentation()
                || ip.is_unspecified())
        }
        std::net::IpAddr::V6(ip) => {
            !(ip.is_loopback()
                || ip.is_unspecified()
                || ip.is_unique_local()
                || ip.is_unicast_link_local())
        }
    }
}

fn parse_evidence_status(status: &str) -> Option<SdkCheckStatus> {
    match status {
        "Passed" => Some(SdkCheckStatus::Passed),
        "Skipped" => Some(SdkCheckStatus::Skipped),
        "Failed" => Some(SdkCheckStatus::Failed),
        _ => None,
    }
}

fn evidence_name_matches(entry: &EvidenceEntry, required: &str) -> bool {
    entry.file.file_name().and_then(|s| s.to_str()) == Some(required)
        || entry.file.display().to_string() == required
}

fn smoke_adapter_endpoint(id: &str, url: &str, timeout: Duration) -> Result<String> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        bail!("adapter URL must start with http:// or https://");
    }
    let payload = adapter_smoke_payload(id)?;
    let curl = Command::new("curl")
        .arg("--fail")
        .arg("--silent")
        .arg("--show-error")
        .arg("--max-time")
        .arg(timeout.as_secs().max(1).to_string())
        .arg("-H")
        .arg("content-type: application/json")
        .arg("-X")
        .arg("POST")
        .arg("--data")
        .arg(payload)
        .arg(url)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();
    match curl {
        Ok(output) if output.status.success() => {
            validate_adapter_smoke_response(id, &output.stdout)
                .with_context(|| format!("{url}: validate adapter smoke response"))?;
            Ok(format!("ok:{url}:contract"))
        }
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            let msg = if stderr.is_empty() {
                format!("curl exited with {}", output.status)
            } else {
                stderr
            };
            bail!("{url}: {msg}")
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            bail!("curl not found")
        }
        Err(err) => Err(err).with_context(|| format!("smoke {url}")),
    }
}

fn adapter_smoke_payload(id: &str) -> Result<String> {
    if !matches!(id, "auth" | "kqe" | "llm") {
        bail!("unknown adapter id `{id}`");
    }
    serde_json::to_string(&adapter_smoke_payload_value(id)).map_err(Into::into)
}

fn load_supervisor_live_adapters(
    target: Target,
    manifest_path: &Path,
    timeout: Duration,
) -> Result<SupervisorLiveAdapters> {
    let src = std::fs::read_to_string(manifest_path)
        .with_context(|| format!("read {}", manifest_path.display()))?;
    let json: serde_json::Value =
        serde_json::from_str(&src).with_context(|| format!("parse {}", manifest_path.display()))?;
    require_json_string(
        &json,
        "schema",
        "kotoba-shell.host-adapters.v0",
        &mut Vec::new(),
    )?;
    require_json_string(&json, "target", target.as_str(), &mut Vec::new())?;
    let adapters = json
        .get("adapters")
        .and_then(|v| v.as_array())
        .ok_or_else(|| anyhow!("host adapter manifest is missing adapters array"))?;
    let mut urls = BTreeMap::new();
    for adapter in adapters {
        let id = adapter
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow!("host adapter entry missing id"))?;
        let required = adapter
            .get("required")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let response_contract = adapter
            .pointer("/smokeInvocation/response")
            .ok_or_else(|| anyhow!("adapter:{id} missing smokeInvocation.response"))?;
        validate_adapter_smoke_response_contract(id, response_contract)?;
        let envs = adapter
            .get("env")
            .and_then(|v| v.as_array())
            .into_iter()
            .flatten()
            .filter_map(|v| v.as_str())
            .collect::<Vec<_>>();
        for env in envs {
            if let Some(value) = std::env::var_os(env) {
                let url = value.to_string_lossy().to_string();
                if !url.starts_with("http://") && !url.starts_with("https://") {
                    bail!("adapter:{id} env {env} must start with http:// or https://");
                }
                urls.insert(id.to_string(), url);
                break;
            }
        }
        if required && !urls.contains_key(id) {
            bail!("adapter:{id} has no configured URL env for live supervisor execution");
        }
    }
    Ok(SupervisorLiveAdapters { urls, timeout })
}

fn invoke_live_adapter_json(
    id: &str,
    adapters: &SupervisorLiveAdapters,
    payload: serde_json::Value,
) -> Result<serde_json::Value> {
    let url = adapters
        .urls
        .get(id)
        .ok_or_else(|| anyhow!("adapter:{id} URL is not configured"))?;
    let payload = serde_json::to_string(&payload)?;
    let curl = Command::new("curl")
        .arg("--fail")
        .arg("--silent")
        .arg("--show-error")
        .arg("--max-time")
        .arg(adapters.timeout.as_secs().max(1).to_string())
        .arg("-H")
        .arg("content-type: application/json")
        .arg("-X")
        .arg("POST")
        .arg("--data")
        .arg(payload)
        .arg(url)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();
    match curl {
        Ok(output) if output.status.success() => serde_json::from_slice(&output.stdout)
            .with_context(|| format!("parse adapter:{id} response JSON")),
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            let msg = if stderr.is_empty() {
                format!("curl exited with {}", output.status)
            } else {
                stderr
            };
            bail!("adapter:{id} {url}: {msg}")
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            bail!("curl not found")
        }
        Err(err) => Err(err).with_context(|| format!("invoke adapter:{id} {url}")),
    }
}

fn validate_adapter_smoke_response_contract(id: &str, response: &serde_json::Value) -> Result<()> {
    match id {
        "auth" => require_response_contract_field(id, response, "allowed", "boolean"),
        "kqe" => require_response_contract_field(id, response, "quads", "array"),
        "llm" => require_response_contract_field(id, response, "output", "string"),
        _ => bail!("unknown adapter id `{id}`"),
    }
}

fn require_response_contract_field(
    id: &str,
    response: &serde_json::Value,
    field: &str,
    expected: &str,
) -> Result<()> {
    let actual = response
        .get(field)
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("adapter:{id} response contract missing {field}"))?;
    if actual != expected {
        bail!("adapter:{id} response contract {field} must be {expected}");
    }
    Ok(())
}

fn validate_adapter_smoke_response(id: &str, stdout: &[u8]) -> Result<()> {
    let json: serde_json::Value = serde_json::from_slice(stdout)
        .with_context(|| format!("parse {id} smoke response JSON"))?;
    match id {
        "auth" => {
            let allowed = smoke_response_field(&json, "allowed");
            if allowed.and_then(|v| v.as_bool()).is_none() {
                bail!("auth smoke response must contain boolean `allowed`");
            }
        }
        "kqe" => {
            let quads = smoke_response_field(&json, "quads");
            if quads.and_then(|v| v.as_array()).is_none() {
                bail!("kqe smoke response must contain array `quads`");
            }
        }
        "llm" => {
            let output = smoke_response_field(&json, "output");
            if output.and_then(|v| v.as_str()).is_none() {
                bail!("llm smoke response must contain string `output`");
            }
        }
        _ => bail!("unknown adapter id `{id}`"),
    }
    Ok(())
}

fn smoke_response_field<'a>(
    json: &'a serde_json::Value,
    field: &str,
) -> Option<&'a serde_json::Value> {
    json.get(field)
        .or_else(|| json.pointer(&format!("/result/{field}")))
}

fn live_response_field<'a>(
    json: &'a serde_json::Value,
    field: &str,
) -> Option<&'a serde_json::Value> {
    smoke_response_field(json, field)
}

fn live_response_bool(json: &serde_json::Value, field: &str) -> Result<bool> {
    live_response_field(json, field)
        .and_then(|v| v.as_bool())
        .ok_or_else(|| anyhow!("live adapter response must contain boolean `{field}`"))
}

fn live_response_string(json: &serde_json::Value, field: &str) -> Result<String> {
    live_response_field(json, field)
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .ok_or_else(|| anyhow!("live adapter response must contain string `{field}`"))
}

fn live_response_string_array(json: &serde_json::Value, field: &str) -> Result<Vec<String>> {
    live_response_field(json, field)
        .and_then(|v| v.as_array())
        .ok_or_else(|| anyhow!("live adapter response must contain array `{field}`"))?
        .iter()
        .map(|v| {
            v.as_str()
                .map(str::to_string)
                .ok_or_else(|| anyhow!("live adapter `{field}` entries must be strings"))
        })
        .collect()
}

fn live_response_quads(json: &serde_json::Value) -> Result<Vec<ComponentKqeQuad>> {
    live_response_field(json, "quads")
        .and_then(|v| v.as_array())
        .ok_or_else(|| anyhow!("live adapter response must contain array `quads`"))?
        .iter()
        .map(|quad| {
            Ok(ComponentKqeQuad {
                graph: required_json_str(quad, "graph")?.to_string(),
                subject: required_json_str(quad, "subject")?.to_string(),
                predicate: required_json_str(quad, "predicate")?.to_string(),
                object: required_json_str(quad, "object")?.to_string(),
            })
        })
        .collect()
}

fn required_json_str<'a>(json: &'a serde_json::Value, field: &str) -> Result<&'a str> {
    json.get(field)
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("live adapter quad is missing string `{field}`"))
}

pub fn updater_check_manifest(
    target: Target,
    manifest_path: impl AsRef<Path>,
) -> Result<UpdaterCheckReport> {
    let manifest_path = manifest_path.as_ref();
    let src = std::fs::read_to_string(manifest_path)
        .with_context(|| format!("read {}", manifest_path.display()))?;
    let json: serde_json::Value =
        serde_json::from_str(&src).with_context(|| format!("parse {}", manifest_path.display()))?;
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    require_json_string(&json, "schema", "kotoba-shell.updater.v0", &mut checks)?;
    require_json_string(&json, "target", target.as_str(), &mut checks)?;
    if json
        .pointer("/requirements/verifyBeforeInstall")
        .and_then(|v| v.as_bool())
        == Some(true)
    {
        checks.push("requirements.verifyBeforeInstall".to_string());
    } else {
        bail!("updater manifest must set requirements.verifyBeforeInstall=true");
    }
    for pointer in [
        "/requirements/aiueosSurfaceContract",
        "/requirements/permissionsContract",
    ] {
        if json.pointer(pointer).and_then(|v| v.as_str()).is_some() {
            checks.push(pointer.trim_start_matches('/').replace('/', "."));
        } else {
            bail!("updater manifest is missing {pointer}");
        }
    }
    let artifact = json
        .get("artifact")
        .and_then(|v| v.as_object())
        .ok_or_else(|| anyhow!("updater manifest is missing artifact object"))?;
    let file_name = artifact
        .get("fileName")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("updater manifest is missing artifact.fileName"))?;
    checks.push("artifact.fileName".to_string());
    let release_dir = manifest_path.parent().unwrap_or_else(|| Path::new("."));
    let artifact_path = release_dir.join(file_name);
    if artifact_path.is_file() {
        checks.push(format!("artifact file: {}", artifact_path.display()));
    } else {
        missing.push(format!("artifact file: {}", artifact_path.display()));
    }
    let expected_sha = artifact.get("sha256").and_then(|v| v.as_str());
    match expected_sha {
        Some(expected) if !expected.is_empty() => {
            if artifact_path.is_file() {
                let actual = sha256_hex(&artifact_path)?;
                if actual != expected {
                    bail!(
                        "updater artifact sha256 mismatch for {}: expected {expected}, got {actual}",
                        artifact_path.display()
                    );
                }
                checks.push("artifact.sha256".to_string());
            } else {
                missing
                    .push("artifact.sha256 cannot be verified without artifact file".to_string());
            }
        }
        _ => missing.push("artifact.sha256".to_string()),
    }
    for field in ["signature", "url"] {
        match artifact.get(field).and_then(|v| v.as_str()) {
            Some(value) if !value.is_empty() => checks.push(format!("artifact.{field}")),
            _ => missing.push(format!("artifact.{field}")),
        }
    }
    let status = if missing.is_empty() {
        SdkCheckStatus::Passed
    } else {
        SdkCheckStatus::Skipped
    };
    let detail = if missing.is_empty() {
        "updater manifest is publish-ready".to_string()
    } else {
        format!(
            "updater manifest is structurally valid; publication skipped because {} updater field(s) are missing",
            missing.len()
        )
    };
    Ok(UpdaterCheckReport {
        target,
        manifest: manifest_path.to_path_buf(),
        status,
        checks,
        missing,
        detail,
    })
}

pub fn finalize_updater_manifest(
    target: Target,
    manifest_path: impl AsRef<Path>,
    artifact_path: impl AsRef<Path>,
    url: &str,
    signature: &str,
) -> Result<UpdaterFinalizeReport> {
    if url.trim().is_empty() {
        bail!("updater artifact URL is required");
    }
    if signature.trim().is_empty() {
        bail!("updater artifact signature is required");
    }
    let manifest_path = manifest_path.as_ref();
    let artifact_path = artifact_path.as_ref();
    let src = std::fs::read_to_string(manifest_path)
        .with_context(|| format!("read {}", manifest_path.display()))?;
    let mut json: serde_json::Value =
        serde_json::from_str(&src).with_context(|| format!("parse {}", manifest_path.display()))?;
    require_json_string(&json, "schema", "kotoba-shell.updater.v0", &mut Vec::new())?;
    require_json_string(&json, "target", target.as_str(), &mut Vec::new())?;
    let release_dir = manifest_path.parent().unwrap_or_else(|| Path::new("."));
    let artifact_file_name = artifact_path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| anyhow!("artifact path must have a file name"))?
        .to_string();
    let final_artifact = release_dir.join(&artifact_file_name);
    if !artifact_path.is_file() {
        bail!(
            "updater artifact does not exist: {}",
            artifact_path.display()
        );
    }
    if artifact_path != final_artifact {
        std::fs::copy(artifact_path, &final_artifact).with_context(|| {
            format!(
                "copy updater artifact {} -> {}",
                artifact_path.display(),
                final_artifact.display()
            )
        })?;
    }
    let sha256 = sha256_hex(&final_artifact)?;
    let artifact = json
        .get_mut("artifact")
        .and_then(|v| v.as_object_mut())
        .ok_or_else(|| anyhow!("updater manifest is missing artifact object"))?;
    artifact.insert(
        "fileName".to_string(),
        serde_json::Value::String(artifact_file_name),
    );
    artifact.insert(
        "sha256".to_string(),
        serde_json::Value::String(sha256.clone()),
    );
    artifact.insert(
        "signature".to_string(),
        serde_json::Value::String(signature.to_string()),
    );
    artifact.insert(
        "url".to_string(),
        serde_json::Value::String(url.to_string()),
    );
    std::fs::write(manifest_path, serde_json::to_string_pretty(&json)?)
        .with_context(|| format!("write {}", manifest_path.display()))?;
    Ok(UpdaterFinalizeReport {
        target,
        manifest: manifest_path.to_path_buf(),
        artifact: final_artifact,
        sha256,
        url: url.to_string(),
        signature: signature.to_string(),
    })
}

pub fn sign_macos_app(app_bundle: impl AsRef<Path>, identity: &str) -> Result<SignatureReport> {
    let app_bundle = app_bundle.as_ref();
    let status = Command::new("codesign")
        .arg("--force")
        .arg("--deep")
        .arg("--sign")
        .arg(identity)
        .arg(app_bundle)
        .status()
        .with_context(|| format!("codesign {}", app_bundle.display()))?;
    if !status.success() {
        bail!("codesign failed for {}", app_bundle.display());
    }
    verify_macos_signature(app_bundle)
}

pub fn verify_macos_signature(app_bundle: impl AsRef<Path>) -> Result<SignatureReport> {
    let app_bundle = app_bundle.as_ref();
    let status = Command::new("codesign")
        .arg("--verify")
        .arg("--deep")
        .arg("--strict")
        .arg("--verbose=2")
        .arg(app_bundle)
        .status()
        .with_context(|| format!("codesign verify {}", app_bundle.display()))?;
    Ok(SignatureReport {
        app_bundle: app_bundle.to_path_buf(),
        signed: status.success(),
    })
}

pub fn verify_generated_project(
    target: Target,
    project_dir: impl AsRef<Path>,
) -> Result<ProjectVerifyReport> {
    let project_dir = project_dir.as_ref();
    match target {
        Target::Macos => bail!("use verify_macos_signature for macOS .app bundles"),
        Target::Ios => verify_ios_project(project_dir),
        Target::Android => verify_android_project(project_dir),
        Target::Windows => verify_windows_project(project_dir),
    }
}

pub fn sdk_check_project(
    target: Target,
    project_dir: impl AsRef<Path>,
    timeout: Duration,
) -> Result<SdkCheckReport> {
    let project_dir = project_dir.as_ref();
    if timeout.is_zero() {
        return Ok(sdk_check_skipped(
            target,
            project_dir,
            Vec::new(),
            "SDK check dry-run requested with zero timeout",
        ));
    }
    match target {
        Target::Macos => Ok(SdkCheckReport {
            target,
            project_dir: project_dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            command: Vec::new(),
            detail: "macOS SDK check is covered by `kotoba shell verify --target macos` codesign verification".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        }),
        Target::Ios => sdk_check_ios_project(project_dir, timeout),
        Target::Android => sdk_check_android_project(project_dir, timeout),
        Target::Windows => Ok(SdkCheckReport {
            target,
            project_dir: project_dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            command: Vec::new(),
            detail: "Windows SDK check is a release-runner gate; use signing-check with signtool/osslsigncode on a Windows or signing runner".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        }),
    }
}

pub fn runtime_check_project(
    target: Target,
    project_dir: impl AsRef<Path>,
    timeout: Duration,
) -> Result<SdkCheckReport> {
    let project_dir = project_dir.as_ref();
    if timeout.is_zero() {
        return Ok(sdk_check_skipped(
            target,
            project_dir,
            Vec::new(),
            "runtime check dry-run requested with zero timeout",
        ));
    }
    match target {
        Target::Macos => Ok(SdkCheckReport {
            target,
            project_dir: project_dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            command: Vec::new(),
            detail: "macOS runtime check is covered by `kotoba shell dev --target macos` for now"
                .to_string(),
            stdout: String::new(),
            stderr: String::new(),
        }),
        Target::Ios => runtime_check_ios_project(project_dir, timeout),
        Target::Android => runtime_check_android_project(project_dir, timeout),
        Target::Windows => Ok(SdkCheckReport {
            target,
            project_dir: project_dir.to_path_buf(),
            status: SdkCheckStatus::Skipped,
            command: Vec::new(),
            detail: "Windows runtime check requires a WebView2/native host or portable aiueos runner artifact; release gates verify signing and SmartScreen evidence".to_string(),
            stdout: String::new(),
            stderr: String::new(),
        }),
    }
}

pub fn runtime_doctor_check(target: Target) -> Result<RuntimeDoctorReport> {
    runtime_doctor_check_with_probe(target, false, Duration::ZERO)
}

pub fn runtime_doctor_check_with_probe(
    target: Target,
    probe: bool,
    timeout: Duration,
) -> Result<RuntimeDoctorReport> {
    match target {
        Target::Macos => Ok(RuntimeDoctorReport {
            target,
            status: SdkCheckStatus::Passed,
            checks: vec!["macOS runtime uses local WKWebView dev shell".to_string()],
            missing: Vec::new(),
            remediation: Vec::new(),
            remediation_commands: Vec::new(),
            detail: "macOS runtime prerequisites are local to the generated app bundle".to_string(),
            command: Vec::new(),
            stdout: String::new(),
            stderr: String::new(),
        }),
        Target::Ios => runtime_doctor_ios(),
        Target::Android => runtime_doctor_android(probe, timeout),
        Target::Windows => Ok(RuntimeDoctorReport {
            target,
            status: SdkCheckStatus::Passed,
            checks: vec![
                "Windows scaffold generated; production host selected at release time".to_string(),
                "Authenticode and SmartScreen evidence are handled by release/signing/submission checks".to_string(),
            ],
            missing: Vec::new(),
            remediation: Vec::new(),
            remediation_commands: Vec::new(),
            detail: "Windows runtime prerequisites are represented as release runner gates".to_string(),
            command: Vec::new(),
            stdout: String::new(),
            stderr: String::new(),
        }),
    }
}

fn runtime_doctor_ios() -> Result<RuntimeDoctorReport> {
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    if command_available("xcrun") {
        checks.push("xcrun".to_string());
        match ios_first_runtime_id()? {
            Some(runtime) => checks.push(format!("ios-runtime:{runtime}")),
            None => missing.push("available iOS simulator runtime".to_string()),
        }
        match ios_first_device_type_id()? {
            Some(device_type) => checks.push(format!("ios-device-type:{device_type}")),
            None => missing.push("available iOS simulator device type".to_string()),
        }
    } else {
        missing.push("xcrun".to_string());
    }
    let status = if missing.is_empty() {
        SdkCheckStatus::Passed
    } else {
        SdkCheckStatus::Skipped
    };
    let detail = if missing.is_empty() {
        "iOS simulator runtime prerequisites are available for hermetic runtime-check".to_string()
    } else {
        format!(
            "iOS runtime-check prerequisites are incomplete: {}",
            missing.join(", ")
        )
    };
    Ok(RuntimeDoctorReport {
        target: Target::Ios,
        status,
        checks,
        remediation: runtime_doctor_remediation(Target::Ios, &missing),
        remediation_commands: runtime_doctor_remediation_commands(Target::Ios, &missing),
        missing,
        detail,
        command: Vec::new(),
        stdout: String::new(),
        stderr: String::new(),
    })
}

fn runtime_doctor_android(probe: bool, timeout: Duration) -> Result<RuntimeDoctorReport> {
    let mut checks = Vec::new();
    let mut missing = Vec::new();
    let mut command = Vec::new();
    let mut stdout = String::new();
    let mut stderr = String::new();
    let mut launchable_avd = None;
    if command_available("adb") {
        checks.push("adb".to_string());
    } else {
        missing.push("adb".to_string());
    }
    if let Some(sdk) = find_android_sdk_dir() {
        checks.push(format!("android-sdk:{}", sdk.display()));
    } else {
        missing.push("Android SDK with platforms directory".to_string());
    }
    if let Some(emulator) = find_android_emulator() {
        checks.push(format!("emulator:{}", emulator.display()));
        if let Some(avdmanager) = find_android_avdmanager() {
            checks.push(format!("avdmanager:{}", avdmanager.display()));
            match android_valid_avd_from_avdmanager(&avdmanager)? {
                Some(avd) => {
                    checks.push(format!("launchable-avd:{avd}"));
                    launchable_avd = Some(avd);
                }
                None => {
                    let detail = android_avd_diagnostic_detail()
                        .unwrap_or_else(|| "no launchable AVD".to_string());
                    missing.push(detail);
                }
            }
        } else {
            match android_runtime_emulator()? {
                Some((_, avd)) => {
                    checks.push(format!("launchable-avd:{avd}"));
                    launchable_avd = Some(avd);
                }
                None => missing.push("launchable Android AVD".to_string()),
            }
        }
    } else {
        missing.push("Android emulator binary".to_string());
    }
    if probe && missing.is_empty() {
        if let Some(avd) = launchable_avd.as_deref() {
            let probe_report = android_runtime_boot_probe(avd, timeout)?;
            match probe_report.status {
                SdkCheckStatus::Passed => checks.push(format!("boot-probe:{avd}")),
                SdkCheckStatus::Skipped | SdkCheckStatus::Failed => {
                    missing.push(android_boot_probe_missing_detail(avd, &probe_report));
                }
            }
            command = probe_report.command;
            stdout = probe_report.stdout;
            stderr = probe_report.stderr;
        }
    }
    let status = if missing.is_empty() {
        SdkCheckStatus::Passed
    } else {
        SdkCheckStatus::Skipped
    };
    let detail = if missing.is_empty() {
        "Android runtime prerequisites are available for AVD-backed runtime-check".to_string()
    } else {
        format!(
            "Android runtime-check prerequisites are incomplete: {}",
            missing.join("; ")
        )
    };
    Ok(RuntimeDoctorReport {
        target: Target::Android,
        status,
        checks,
        remediation: runtime_doctor_remediation(Target::Android, &missing),
        remediation_commands: runtime_doctor_remediation_commands(Target::Android, &missing),
        missing,
        detail,
        command,
        stdout,
        stderr,
    })
}

fn runtime_doctor_remediation(target: Target, missing: &[String]) -> Vec<String> {
    missing
        .iter()
        .flat_map(|item| match target {
            Target::Macos => Vec::new(),
            Target::Ios => ios_runtime_remediation(item),
            Target::Android => android_runtime_remediation(item),
            Target::Windows => Vec::new(),
        })
        .collect()
}

fn runtime_doctor_remediation_commands(target: Target, missing: &[String]) -> Vec<Vec<String>> {
    missing
        .iter()
        .flat_map(|item| match target {
            Target::Macos => Vec::new(),
            Target::Ios => ios_runtime_remediation_commands(item),
            Target::Android => android_runtime_remediation_commands(item),
            Target::Windows => Vec::new(),
        })
        .collect()
}

fn ios_runtime_remediation(item: &str) -> Vec<String> {
    if item == "xcrun" {
        return vec![
            "Install Xcode and run `sudo xcode-select -s /Applications/Xcode.app`.".to_string(),
            "Run `xcodebuild -runFirstLaunch` to finish simulator toolchain setup.".to_string(),
        ];
    }
    if item.contains("simulator runtime") {
        return vec![
            "Install an iOS Simulator runtime from Xcode Settings > Platforms.".to_string(),
            "Verify with `xcrun simctl list runtimes available`.".to_string(),
        ];
    }
    if item.contains("simulator device type") {
        return vec![
            "Install iOS Simulator device support through Xcode.".to_string(),
            "Verify with `xcrun simctl list devicetypes`.".to_string(),
        ];
    }
    Vec::new()
}

fn ios_runtime_remediation_commands(item: &str) -> Vec<Vec<String>> {
    if item == "xcrun" {
        return vec![
            vec![
                "sudo".to_string(),
                "xcode-select".to_string(),
                "-s".to_string(),
                "/Applications/Xcode.app".to_string(),
            ],
            vec!["xcodebuild".to_string(), "-runFirstLaunch".to_string()],
        ];
    }
    if item.contains("simulator runtime") {
        return vec![vec![
            "xcrun".to_string(),
            "simctl".to_string(),
            "list".to_string(),
            "runtimes".to_string(),
            "available".to_string(),
        ]];
    }
    if item.contains("simulator device type") {
        return vec![vec![
            "xcrun".to_string(),
            "simctl".to_string(),
            "list".to_string(),
            "devicetypes".to_string(),
        ]];
    }
    Vec::new()
}

fn android_runtime_remediation(item: &str) -> Vec<String> {
    if item == "adb" {
        return vec![
            "Install Android SDK Platform Tools and ensure `adb` is on PATH.".to_string(),
            "Verify with `adb devices -l`.".to_string(),
        ];
    }
    if item.contains("Android SDK") {
        return vec![
            "Set ANDROID_HOME or ANDROID_SDK_ROOT to an Android SDK with installed platforms."
                .to_string(),
            "Verify that `$ANDROID_HOME/platforms` exists.".to_string(),
        ];
    }
    if item.contains("emulator binary") {
        return vec![
            "Install the Android Emulator package with SDK Manager.".to_string(),
            "Verify that `$ANDROID_HOME/emulator/emulator -list-avds` runs.".to_string(),
        ];
    }
    if item.contains("Missing system image") {
        if let Some(command) = extract_backticked_sdkmanager_command(item) {
            return vec![
                format!("Run `{command}` to install the missing Android system image."),
                "Recreate the broken AVD or create a new AVD with an installed system image."
                    .to_string(),
                "Verify with `avdmanager list avd` that the AVD is listed under available devices, not under failed devices.".to_string(),
            ];
        }
        return vec![
            "Install the missing Android system image shown by `avdmanager list avd`.".to_string(),
            "Recreate the broken AVD or create a new AVD with an installed system image.".to_string(),
            "Verify with `avdmanager list avd` that the AVD is listed under available devices, not under failed devices.".to_string(),
        ];
    }
    if item.contains("launchable AVD") {
        return vec![
            "Create an Android Virtual Device with `avdmanager create avd` or Android Studio Device Manager.".to_string(),
            "Verify with `avdmanager list avd` and `emulator -list-avds`.".to_string(),
        ];
    }
    if item.contains("AVD boot probe failed") || item.contains("No initial system image") {
        let mut remediation = Vec::new();
        if let Some(package) = extract_backticked_sdkmanager_package(item) {
            remediation.push(format!(
                "Reinstall the Android system image with `sdkmanager --uninstall \"{package}\"` and `sdkmanager \"{package}\"`."
            ));
        } else {
            remediation.push("Reinstall the Android system image used by the AVD.".to_string());
        }
        remediation.push("Cold boot the AVD or recreate it from Android Studio Device Manager if the image still fails to initialize.".to_string());
        remediation.push("Verify with `kotoba shell doctor-check --target android --probe` before running runtime-check again.".to_string());
        return remediation;
    }
    Vec::new()
}

fn android_runtime_remediation_commands(item: &str) -> Vec<Vec<String>> {
    if item == "adb" {
        return vec![vec![
            "adb".to_string(),
            "devices".to_string(),
            "-l".to_string(),
        ]];
    }
    if item.contains("Android SDK") {
        return vec![vec![
            "sh".to_string(),
            "-c".to_string(),
            "test -d \"$ANDROID_HOME/platforms\" || test -d \"$ANDROID_SDK_ROOT/platforms\""
                .to_string(),
        ]];
    }
    if item.contains("emulator binary") {
        return vec![vec!["emulator".to_string(), "-list-avds".to_string()]];
    }
    if item.contains("Missing system image") {
        let mut commands = Vec::new();
        if let Some(package) = extract_backticked_sdkmanager_package(item) {
            commands.push(vec!["sdkmanager".to_string(), package]);
        }
        commands.push(vec![
            "avdmanager".to_string(),
            "list".to_string(),
            "avd".to_string(),
        ]);
        return commands;
    }
    if item.contains("launchable AVD") {
        return vec![
            vec![
                "avdmanager".to_string(),
                "list".to_string(),
                "avd".to_string(),
            ],
            vec!["emulator".to_string(), "-list-avds".to_string()],
        ];
    }
    if item.contains("AVD boot probe failed") || item.contains("No initial system image") {
        let mut commands = Vec::new();
        if let Some(package) = extract_backticked_sdkmanager_package(item) {
            commands.push(vec![
                "sdkmanager".to_string(),
                "--uninstall".to_string(),
                package.clone(),
            ]);
            commands.push(vec!["sdkmanager".to_string(), package]);
        }
        commands.push(vec![
            "avdmanager".to_string(),
            "list".to_string(),
            "avd".to_string(),
        ]);
        return commands;
    }
    Vec::new()
}

fn extract_backticked_sdkmanager_command(src: &str) -> Option<String> {
    let start = src.find("`sdkmanager ")?;
    let rest = &src[start + 1..];
    let end = rest.find('`')?;
    Some(rest[..end].to_string())
}

fn extract_backticked_sdkmanager_package(src: &str) -> Option<String> {
    let command = extract_backticked_sdkmanager_command(src)?;
    let package = command
        .strip_prefix("sdkmanager ")
        .map(str::trim)
        .map(|package| {
            package
                .strip_prefix("--uninstall ")
                .unwrap_or(package)
                .trim()
        })?;
    Some(package.trim_matches('"').to_string()).filter(|package| !package.is_empty())
}

fn sdk_check_ios_project(project_dir: &Path, timeout: Duration) -> Result<SdkCheckReport> {
    verify_ios_project(project_dir)?;
    if !command_available("xcodebuild") {
        return Ok(sdk_check_skipped(
            Target::Ios,
            project_dir,
            Vec::new(),
            "xcodebuild is not available on PATH",
        ));
    }
    let Some(project) = first_child_with_extension(project_dir, "xcodeproj")? else {
        return Ok(sdk_check_skipped(
            Target::Ios,
            project_dir,
            Vec::new(),
            "generated iOS scaffold has no .xcodeproj yet; import Sources/ and Resources/ into Xcode or add project generation",
        ));
    };
    let target_name = project
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("KotobaShell");
    let args = vec![
        "-project".to_string(),
        project
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("KotobaShell.xcodeproj")
            .to_string(),
        "-target".to_string(),
        target_name.to_string(),
        "-sdk".to_string(),
        "iphonesimulator".to_string(),
        "-configuration".to_string(),
        "Debug".to_string(),
        "ARCHS=arm64".to_string(),
        "ONLY_ACTIVE_ARCH=YES".to_string(),
        "CODE_SIGNING_ALLOWED=NO".to_string(),
        "build".to_string(),
    ];
    run_sdk_command(Target::Ios, project_dir, "xcodebuild", &args, timeout)
}

fn runtime_check_ios_project(project_dir: &Path, timeout: Duration) -> Result<SdkCheckReport> {
    verify_ios_project(project_dir)?;
    if !command_available("xcrun") {
        return Ok(sdk_check_skipped(
            Target::Ios,
            project_dir,
            Vec::new(),
            "xcrun is not available on PATH",
        ));
    }
    let app_bundle = ios_debug_app_bundle(project_dir)?;
    if !app_bundle.is_dir() {
        return Ok(sdk_check_skipped(
            Target::Ios,
            project_dir,
            Vec::new(),
            "iOS simulator app bundle is missing; run `kotoba shell sdk-check --target ios` first",
        ));
    }
    let Some((device, boot_command)) = ios_runtime_simulator()? else {
        return Ok(sdk_check_skipped(
            Target::Ios,
            project_dir,
            vec![
                "xcrun".to_string(),
                "simctl".to_string(),
                "list".to_string(),
                "devices".to_string(),
                "available".to_string(),
            ],
            "no available iOS simulator is installed",
        ));
    };
    let bundle_id = ios_bundle_identifier(project_dir)?;
    let app_bundle = absolute_path(&app_bundle)?;
    let script = format!(
        "run_with_timeout() {{ limit=\"$1\"; shift; \"$@\" & pid=$!; elapsed=0; while kill -0 \"$pid\" 2>/dev/null; do if [ \"$elapsed\" -ge \"$limit\" ]; then kill \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true; return 124; fi; sleep 1; elapsed=$((elapsed + 1)); done; wait \"$pid\"; }}; {}echo kotoba-shell-runtime:install; run_with_timeout 45 xcrun simctl install {} {} || exit $?; echo kotoba-shell-runtime:terminate; xcrun simctl terminate {} {} >/dev/null 2>&1 || true; echo kotoba-shell-runtime:launch; run_with_timeout 20 xcrun simctl launch --terminate-running-process {} {} >/tmp/kotoba-shell-simctl-launch.log 2>&1 || true; cat /tmp/kotoba-shell-simctl-launch.log; sleep 2; echo kotoba-shell-runtime:ready-log; run_with_timeout 30 xcrun simctl spawn {} log show --style compact --last 120s --predicate 'eventMessage CONTAINS \"KOTOBA_SHELL_READY\"' >/tmp/kotoba-shell-ready.log || {{ echo kotoba-shell-runtime:ready-log-timeout; exit 124; }}; grep KOTOBA_SHELL_READY /tmp/kotoba-shell-ready.log || {{ echo kotoba-shell-runtime:ready-marker-missing; exit 1; }}",
        boot_command,
        shell_quote(&device),
        shell_quote(&app_bundle.display().to_string()),
        shell_quote(&device),
        shell_quote(&bundle_id),
        shell_quote(&device),
        shell_quote(&bundle_id),
        shell_quote(&device)
    );
    run_sdk_command(
        Target::Ios,
        project_dir,
        "/bin/sh",
        &["-c".to_string(), script],
        timeout,
    )
}

fn sdk_check_android_project(project_dir: &Path, timeout: Duration) -> Result<SdkCheckReport> {
    verify_android_project(project_dir)?;
    let (program, args) = if project_dir.join("gradlew").is_file() {
        (
            "./gradlew".to_string(),
            vec![
                ":app:assembleDebug".to_string(),
                "--no-daemon".to_string(),
                "--console=plain".to_string(),
                "--stacktrace".to_string(),
            ],
        )
    } else if let Some(gradle) = find_cached_gradle("8.14.3") {
        (
            gradle,
            vec![
                ":app:assembleDebug".to_string(),
                "--no-daemon".to_string(),
                "--console=plain".to_string(),
                "--stacktrace".to_string(),
            ],
        )
    } else if command_available("gradle") {
        (
            "gradle".to_string(),
            vec![
                ":app:assembleDebug".to_string(),
                "--no-daemon".to_string(),
                "--console=plain".to_string(),
                "--stacktrace".to_string(),
            ],
        )
    } else {
        return Ok(sdk_check_skipped(
            Target::Android,
            project_dir,
            Vec::new(),
            "neither generated gradlew nor system gradle is available",
        ));
    };
    let env = find_jdk_home("21")
        .map(|java_home| vec![("JAVA_HOME".to_string(), java_home)])
        .unwrap_or_default();
    run_sdk_command_env(Target::Android, project_dir, &program, &args, timeout, &env)
}

fn runtime_check_android_project(project_dir: &Path, timeout: Duration) -> Result<SdkCheckReport> {
    verify_android_project(project_dir)?;
    if !command_available("adb") {
        return Ok(sdk_check_skipped(
            Target::Android,
            project_dir,
            Vec::new(),
            "adb is not available on PATH",
        ));
    }
    let boot_command = if android_adb_devices()?.is_empty() {
        match android_runtime_emulator()? {
            Some((emulator, avd)) => format!(
                "run_with_timeout() {{ limit=\"$1\"; shift; \"$@\" & pid=$!; elapsed=0; while kill -0 \"$pid\" 2>/dev/null; do if [ \"$elapsed\" -ge \"$limit\" ]; then kill \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true; return 124; fi; sleep 1; elapsed=$((elapsed + 1)); done; wait \"$pid\"; }}; {}; echo kotoba-shell-runtime:emulator-start; {} -avd {} -no-snapshot-save -no-window -no-audio >/tmp/kotoba-shell-android-emulator.log 2>&1 & emulator_pid=$!; trap 'adb emu kill >/dev/null 2>&1 || true; kill $emulator_pid >/dev/null 2>&1 || true' EXIT; echo kotoba-shell-runtime:wait-device; run_with_timeout 60 adb wait-for-device || {{ echo kotoba-shell-runtime:wait-device-timeout; sed -n '1,120p' /tmp/kotoba-shell-android-emulator.log; exit 124; }}; for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do booted=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r'); [ \"$booted\" = \"1\" ] && break; sleep 2; done; booted=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r'); [ \"$booted\" = \"1\" ] || {{ echo kotoba-shell-runtime:android-boot-timeout; sed -n '1,120p' /tmp/kotoba-shell-android-emulator.log; exit 124; }}; ",
                android_sdk_shell_exports(),
                shell_quote(&emulator.display().to_string()),
                shell_quote(&avd),
            ),
            None => {
                let detail = android_avd_diagnostic_detail()
                    .unwrap_or_else(|| "no connected Android device/emulator and no launchable AVD are available".to_string());
                return Ok(sdk_check_skipped(
                    Target::Android,
                    project_dir,
                    vec!["adb".to_string(), "devices".to_string(), "-l".to_string()],
                    &detail,
                ));
            }
        }
    } else {
        String::new()
    };
    if android_adb_devices()?.is_empty() && boot_command.is_empty() {
        return Ok(sdk_check_skipped(
            Target::Android,
            project_dir,
            vec!["adb".to_string(), "devices".to_string(), "-l".to_string()],
            "no connected Android device or emulator is available",
        ));
    }
    let apk = android_debug_apk(project_dir);
    if !apk.is_file() {
        return Ok(sdk_check_skipped(
            Target::Android,
            project_dir,
            Vec::new(),
            "Android debug APK is missing; run `kotoba shell sdk-check --target android` first",
        ));
    }
    let package = android_application_id(project_dir)?;
    let apk = absolute_path(&apk)?;
    let script = format!(
        "{}echo kotoba-shell-runtime:install; adb logcat -c && adb install -r {} && echo kotoba-shell-runtime:launch && adb shell monkey -p {} -c android.intent.category.LAUNCHER 1 && sleep 2 && echo kotoba-shell-runtime:ready-log && adb logcat -d -s KotobaShell:I '*:S' | grep KOTOBA_SHELL_READY",
        boot_command,
        shell_quote(&apk.display().to_string()),
        shell_quote(&package)
    );
    run_sdk_command(
        Target::Android,
        project_dir,
        "/bin/sh",
        &["-c".to_string(), script],
        timeout,
    )
}

fn android_runtime_boot_probe(avd: &str, timeout: Duration) -> Result<SdkCheckReport> {
    if timeout.is_zero() {
        return Ok(sdk_check_skipped(
            Target::Android,
            Path::new("."),
            Vec::new(),
            "Android boot probe dry-run requested with zero timeout",
        ));
    }
    let Some(emulator) = find_android_emulator() else {
        return Ok(sdk_check_skipped(
            Target::Android,
            Path::new("."),
            Vec::new(),
            "Android emulator binary is not available",
        ));
    };
    let script = format!(
        "run_with_timeout() {{ limit=\"$1\"; shift; \"$@\" & pid=$!; elapsed=0; while kill -0 \"$pid\" 2>/dev/null; do if [ \"$elapsed\" -ge \"$limit\" ]; then kill \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true; return 124; fi; sleep 1; elapsed=$((elapsed + 1)); done; wait \"$pid\"; }}; {}; echo kotoba-shell-doctor:emulator-start; {} -avd {} -no-snapshot-save -no-window -no-audio >/tmp/kotoba-shell-android-doctor-emulator.log 2>&1 & emulator_pid=$!; trap 'adb emu kill >/dev/null 2>&1 || true; kill $emulator_pid >/dev/null 2>&1 || true' EXIT; echo kotoba-shell-doctor:wait-device; run_with_timeout 60 adb wait-for-device || {{ echo kotoba-shell-doctor:wait-device-timeout; sed -n '1,160p' /tmp/kotoba-shell-android-doctor-emulator.log; exit 124; }}; for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do booted=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r'); [ \"$booted\" = \"1\" ] && break; sleep 2; done; booted=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r'); [ \"$booted\" = \"1\" ] || {{ echo kotoba-shell-doctor:android-boot-timeout; sed -n '1,160p' /tmp/kotoba-shell-android-doctor-emulator.log; exit 124; }}; echo kotoba-shell-doctor:boot-complete",
        android_sdk_shell_exports(),
        shell_quote(&emulator.display().to_string()),
        shell_quote(avd),
    );
    run_sdk_command(
        Target::Android,
        Path::new("."),
        "/bin/sh",
        &["-c".to_string(), script],
        timeout,
    )
}

fn android_sdk_shell_exports() -> String {
    let Some(sdk) = find_android_sdk_dir() else {
        return String::new();
    };
    let sdk = shell_quote(&sdk.display().to_string());
    format!("export ANDROID_SDK_ROOT={sdk}; export ANDROID_HOME={sdk}")
}

fn android_boot_probe_missing_detail(avd: &str, report: &SdkCheckReport) -> String {
    let combined = format!("{}\n{}", report.stdout, report.stderr);
    let mut reason = combined
        .lines()
        .map(str::trim)
        .find(|line| line.contains("No initial system image"))
        .or_else(|| {
            combined.lines().map(str::trim).find(|line| {
                line.contains("android-boot-timeout") || line.contains("wait-device-timeout")
            })
        })
        .unwrap_or(report.detail.as_str())
        .to_string();
    if reason.is_empty() {
        reason = report.detail.clone();
    }
    if reason.contains("No initial system image") {
        if let Some(avd_dir) = android_avd_dir_from_name(avd) {
            if let Some(package) = android_system_image_package_from_avd_dir(&avd_dir) {
                return format!(
                    "Android AVD boot probe failed for {avd}: {reason}; reinstall with `sdkmanager --uninstall \"{package}\"` then `sdkmanager \"{package}\"`, or recreate the AVD"
                );
            }
        }
    }
    format!("Android AVD boot probe failed for {avd}: {reason}")
}

fn sdk_check_skipped(
    target: Target,
    project_dir: &Path,
    command: Vec<String>,
    detail: &str,
) -> SdkCheckReport {
    SdkCheckReport {
        target,
        project_dir: project_dir.to_path_buf(),
        status: SdkCheckStatus::Skipped,
        command,
        detail: detail.to_string(),
        stdout: String::new(),
        stderr: String::new(),
    }
}

fn run_sdk_command(
    target: Target,
    project_dir: &Path,
    program: &str,
    args: &[String],
    timeout: Duration,
) -> Result<SdkCheckReport> {
    run_sdk_command_env(target, project_dir, program, args, timeout, &[])
}

fn run_sdk_command_env(
    target: Target,
    project_dir: &Path,
    program: &str,
    args: &[String],
    timeout: Duration,
    env: &[(String, String)],
) -> Result<SdkCheckReport> {
    let mut command_line = vec![program.to_string()];
    command_line.extend(args.iter().cloned());
    let log_id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let stdout_path = std::env::temp_dir().join(format!("kotoba-shell-sdk-{log_id}.stdout.log"));
    let stderr_path = std::env::temp_dir().join(format!("kotoba-shell-sdk-{log_id}.stderr.log"));
    let stdout_file =
        File::create(&stdout_path).with_context(|| format!("create {}", stdout_path.display()))?;
    let stderr_file =
        File::create(&stderr_path).with_context(|| format!("create {}", stderr_path.display()))?;
    let mut command = Command::new(program);
    command.args(args).current_dir(project_dir);
    for (key, value) in env {
        command.env(key, value);
    }
    let mut child = command
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .spawn()
        .with_context(|| format!("spawn SDK check `{}`", command_line.join(" ")))?;
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SdkCheckReport {
                target,
                project_dir: project_dir.to_path_buf(),
                status: if status.success() {
                    SdkCheckStatus::Passed
                } else {
                    SdkCheckStatus::Failed
                },
                command: command_line,
                detail: format!("SDK command exited with status {status}"),
                stdout,
                stderr,
            });
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SdkCheckReport {
                target,
                project_dir: project_dir.to_path_buf(),
                status: SdkCheckStatus::Failed,
                command: command_line,
                detail: format!("SDK command timed out after {}s", timeout.as_secs()),
                stdout,
                stderr,
            });
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn run_signing_command(
    target: Target,
    release_dir: &Path,
    script: &str,
    args: &[String],
    timeout: Duration,
    checks: Vec<String>,
    missing_credentials: Vec<String>,
) -> Result<SigningCheckReport> {
    let mut command_line = vec![format!("./{script}")];
    command_line.extend(args.iter().cloned());
    let log_id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let stdout_path =
        std::env::temp_dir().join(format!("kotoba-shell-signing-{log_id}.stdout.log"));
    let stderr_path =
        std::env::temp_dir().join(format!("kotoba-shell-signing-{log_id}.stderr.log"));
    let stdout_file =
        File::create(&stdout_path).with_context(|| format!("create {}", stdout_path.display()))?;
    let stderr_file =
        File::create(&stderr_path).with_context(|| format!("create {}", stderr_path.display()))?;
    let mut child = Command::new(format!("./{script}"))
        .args(args)
        .current_dir(release_dir)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .spawn()
        .with_context(|| format!("spawn signing check `{}`", command_line.join(" ")))?;
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SigningCheckReport {
                target,
                dir: release_dir.to_path_buf(),
                status: if status.success() {
                    SdkCheckStatus::Passed
                } else {
                    SdkCheckStatus::Failed
                },
                checks,
                missing_credentials,
                command: command_line,
                detail: format!("signing command exited with status {status}"),
                stdout,
                stderr,
            });
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SigningCheckReport {
                target,
                dir: release_dir.to_path_buf(),
                status: SdkCheckStatus::Failed,
                checks,
                missing_credentials,
                command: command_line,
                detail: format!("signing command timed out after {}s", timeout.as_secs()),
                stdout,
                stderr,
            });
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn run_submission_command(
    target: Target,
    release_dir: &Path,
    script: &str,
    args: &[String],
    timeout: Duration,
    checks: Vec<String>,
    missing_credentials: Vec<String>,
) -> Result<SubmissionCheckReport> {
    let mut command_line = vec![format!("./{script}")];
    command_line.extend(args.iter().cloned());
    let log_id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let stdout_path =
        std::env::temp_dir().join(format!("kotoba-shell-submission-{log_id}.stdout.log"));
    let stderr_path =
        std::env::temp_dir().join(format!("kotoba-shell-submission-{log_id}.stderr.log"));
    let stdout_file =
        File::create(&stdout_path).with_context(|| format!("create {}", stdout_path.display()))?;
    let stderr_file =
        File::create(&stderr_path).with_context(|| format!("create {}", stderr_path.display()))?;
    let mut child = Command::new(format!("./{script}"))
        .args(args)
        .current_dir(release_dir)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .spawn()
        .with_context(|| format!("spawn submission check `{}`", command_line.join(" ")))?;
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SubmissionCheckReport {
                target,
                dir: release_dir.to_path_buf(),
                status: if status.success() {
                    SdkCheckStatus::Passed
                } else {
                    SdkCheckStatus::Failed
                },
                checks,
                missing_credentials,
                command: command_line,
                detail: format!("submission command exited with status {status}"),
                stdout,
                stderr,
            });
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();
            let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();
            let _ = std::fs::remove_file(&stdout_path);
            let _ = std::fs::remove_file(&stderr_path);
            return Ok(SubmissionCheckReport {
                target,
                dir: release_dir.to_path_buf(),
                status: SdkCheckStatus::Failed,
                checks,
                missing_credentials,
                command: command_line,
                detail: format!("submission command timed out after {}s", timeout.as_secs()),
                stdout,
                stderr,
            });
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn find_jdk_home(version: &str) -> Option<String> {
    let output = Command::new("/usr/libexec/java_home")
        .arg("-v")
        .arg(version)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if path.is_empty() {
        None
    } else {
        Some(path)
    }
}

fn find_cached_gradle(version: &str) -> Option<String> {
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    let root = home
        .join(".gradle/wrapper/dists")
        .join(format!("gradle-{version}-bin"));
    let gradle_dir = find_dir_named(&root, &format!("gradle-{version}"))?;
    let gradle = gradle_dir.join("bin/gradle");
    if gradle.is_file() {
        Some(gradle.display().to_string())
    } else {
        None
    }
}

fn find_dir_named(root: &Path, name: &str) -> Option<PathBuf> {
    let entries = std::fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if path.file_name().and_then(|s| s.to_str()) == Some(name) {
                return Some(path);
            }
            if let Some(found) = find_dir_named(&path, name) {
                return Some(found);
            }
        }
    }
    None
}

fn command_available(program: &str) -> bool {
    Command::new(program)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
        || Command::new(program)
            .arg("-version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
}

fn android_debug_apk(project_dir: &Path) -> PathBuf {
    project_dir.join("app/build/outputs/apk/debug/app-debug.apk")
}

fn android_application_id(project_dir: &Path) -> Result<String> {
    let src =
        std::fs::read_to_string(project_dir.join("app/build.gradle.kts")).with_context(|| {
            format!(
                "read {}",
                project_dir.join("app/build.gradle.kts").display()
            )
        })?;
    extract_quoted_assignment(&src, "applicationId")
        .ok_or_else(|| anyhow!("applicationId not found in app/build.gradle.kts"))
}

fn android_adb_devices() -> Result<Vec<String>> {
    let output = Command::new("adb")
        .arg("devices")
        .arg("-l")
        .output()
        .context("run adb devices -l")?;
    if !output.status.success() {
        bail!(
            "adb devices -l failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .skip(1)
        .filter_map(|line| {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.contains(" offline") {
                None
            } else {
                trimmed.split_whitespace().next().map(str::to_string)
            }
        })
        .collect())
}

fn android_runtime_emulator() -> Result<Option<(PathBuf, String)>> {
    let Some(emulator) = find_android_emulator() else {
        return Ok(None);
    };
    if let Some(avdmanager) = find_android_avdmanager() {
        return Ok(android_valid_avd_from_avdmanager(&avdmanager)?.map(|avd| (emulator, avd)));
    }
    let output = Command::new(&emulator)
        .arg("-list-avds")
        .output()
        .with_context(|| format!("run {} -list-avds", emulator.display()))?;
    if !output.status.success() {
        return Ok(None);
    }
    let avd = parse_first_android_avd(&String::from_utf8_lossy(&output.stdout));
    Ok(avd.map(|avd| (emulator, avd)))
}

fn find_android_avdmanager() -> Option<PathBuf> {
    command_path("avdmanager")
        .or_else(|| {
            find_android_sdk_dir().map(|sdk| sdk.join("cmdline-tools/latest/bin/avdmanager"))
        })
        .filter(|path| path.is_file())
}

fn android_valid_avd_from_avdmanager(avdmanager: &Path) -> Result<Option<String>> {
    let output = Command::new(&avdmanager)
        .arg("list")
        .arg("avd")
        .output()
        .with_context(|| format!("run {} list avd", avdmanager.display()))?;
    if !output.status.success() {
        return Ok(None);
    }
    Ok(parse_first_valid_android_avd_from_avdmanager(
        &String::from_utf8_lossy(&output.stdout),
    ))
}

fn android_avd_diagnostic_detail() -> Option<String> {
    let avdmanager = find_android_avdmanager()?;
    let output = Command::new(&avdmanager)
        .arg("list")
        .arg("avd")
        .output()
        .ok()?;
    if !output.status.success() {
        return Some(
            "no connected Android device/emulator and avdmanager list avd failed".to_string(),
        );
    }
    let text = String::from_utf8_lossy(&output.stdout);
    if let Some(reason) = parse_first_invalid_android_avd_reason(&text) {
        let reason = enrich_android_invalid_avd_reason(&text, reason);
        return Some(format!(
            "no connected Android device/emulator and no launchable AVD are available: {reason}"
        ));
    }
    Some("no connected Android device/emulator and no launchable AVD are available".to_string())
}

fn find_android_emulator() -> Option<PathBuf> {
    if let Some(path) = command_path("emulator") {
        return Some(path);
    }
    find_android_sdk_dir()
        .map(|sdk| sdk.join("emulator/emulator"))
        .filter(|path| path.is_file())
}

fn command_path(program: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(program);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn parse_first_android_avd(src: &str) -> Option<String> {
    src.lines()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .map(str::to_string)
}

fn parse_first_valid_android_avd_from_avdmanager(src: &str) -> Option<String> {
    if src.contains("could not be loaded") {
        let before_invalid = src
            .split("The following Android Virtual Devices could not be loaded:")
            .next()
            .unwrap_or(src);
        return parse_first_avdmanager_name(before_invalid);
    }
    parse_first_avdmanager_name(src)
}

fn parse_first_invalid_android_avd_reason(src: &str) -> Option<String> {
    let invalid = src
        .split("The following Android Virtual Devices could not be loaded:")
        .nth(1)?;
    let name = parse_first_avdmanager_name(invalid).unwrap_or_else(|| "unknown AVD".to_string());
    let error = invalid.lines().find_map(|line| {
        line.trim()
            .strip_prefix("Error:")
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string)
    })?;
    Some(format!("{name}: {error}"))
}

fn enrich_android_invalid_avd_reason(src: &str, reason: String) -> String {
    if !reason.contains("Missing system image") {
        return reason;
    }
    let Some(path) = parse_first_invalid_android_avd_path(src) else {
        return reason;
    };
    let Some(package) = android_system_image_package_from_avd_dir(Path::new(&path)) else {
        return reason;
    };
    format!("{reason}; install with `sdkmanager \"{package}\"`")
}

fn parse_first_invalid_android_avd_path(src: &str) -> Option<String> {
    let invalid = src
        .split("The following Android Virtual Devices could not be loaded:")
        .nth(1)?;
    invalid.lines().find_map(|line| {
        line.trim()
            .strip_prefix("Path:")
            .map(str::trim)
            .filter(|path| !path.is_empty())
            .map(str::to_string)
    })
}

fn android_system_image_package_from_avd_dir(avd_dir: &Path) -> Option<String> {
    let config = std::fs::read_to_string(avd_dir.join("config.ini")).ok()?;
    android_system_image_package_from_config(&config)
}

fn android_avd_dir_from_name(avd: &str) -> Option<PathBuf> {
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    let ini = home.join(".android/avd").join(format!("{avd}.ini"));
    let text = std::fs::read_to_string(ini).ok()?;
    text.lines().find_map(|line| {
        line.trim()
            .strip_prefix("path=")
            .map(str::trim)
            .filter(|path| !path.is_empty())
            .map(PathBuf::from)
    })
}

fn android_system_image_package_from_config(config: &str) -> Option<String> {
    let sysdir = config.lines().find_map(|line| {
        line.trim()
            .strip_prefix("image.sysdir.1=")
            .map(str::trim)
            .filter(|value| !value.is_empty())
    })?;
    let trimmed = sysdir.trim_matches('/');
    let parts = trimmed.split('/').collect::<Vec<_>>();
    if parts.len() != 4 || parts.first().copied() != Some("system-images") {
        return None;
    }
    Some(parts.join(";"))
}

fn parse_first_avdmanager_name(src: &str) -> Option<String> {
    src.lines().find_map(|line| {
        let trimmed = line.trim();
        trimmed
            .strip_prefix("Name:")
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .map(str::to_string)
    })
}

fn ios_debug_app_bundle(project_dir: &Path) -> Result<PathBuf> {
    let Some(project) = first_child_with_extension(project_dir, "xcodeproj")? else {
        bail!("generated iOS scaffold has no .xcodeproj");
    };
    let target_name = project
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("KotobaShell");
    Ok(project_dir
        .join("build/Debug-iphonesimulator")
        .join(format!("{target_name}.app")))
}

fn ios_bundle_identifier(project_dir: &Path) -> Result<String> {
    let src =
        std::fs::read_to_string(project_dir.join("Resources/Info.plist")).with_context(|| {
            format!(
                "read {}",
                project_dir.join("Resources/Info.plist").display()
            )
        })?;
    let key = "<key>CFBundleIdentifier</key>";
    let Some(after_key) = src.split(key).nth(1) else {
        bail!("CFBundleIdentifier not found in Resources/Info.plist");
    };
    let Some(after_open) = after_key.split("<string>").nth(1) else {
        bail!("CFBundleIdentifier string not found in Resources/Info.plist");
    };
    let Some(value) = after_open.split("</string>").next() else {
        bail!("CFBundleIdentifier value not found in Resources/Info.plist");
    };
    Ok(value.trim().to_string())
}

fn ios_runtime_simulator() -> Result<Option<(String, String)>> {
    if let Some(device) = std::env::var("KOTOBA_IOS_SIMULATOR_UDID")
        .ok()
        .filter(|s| !s.trim().is_empty())
    {
        return Ok(Some((device, String::new())));
    }
    if let Some(device) = ios_create_temporary_simulator()? {
        let quoted = shell_quote(&device);
        return Ok(Some((
            device,
            format!(
                "trap \"xcrun simctl shutdown {quoted} >/dev/null 2>&1 || true; xcrun simctl delete {quoted} >/dev/null 2>&1 || true\" EXIT; echo kotoba-shell-runtime:boot; xcrun simctl boot {quoted} 2>/dev/null || true; run_with_timeout 90 xcrun simctl bootstatus {quoted} -b || {{ echo kotoba-shell-runtime:boot-timeout; exit 124; }}; "
            ),
        )));
    }
    if let Some(device) = ios_first_simulator_from_simctl("booted")? {
        return Ok(Some((device, String::new())));
    }
    let Some(device) = ios_first_simulator_from_simctl("available")? else {
        return Ok(None);
    };
    let quoted = shell_quote(&device);
    Ok(Some((
        device,
        format!(
            "echo kotoba-shell-runtime:boot; xcrun simctl boot {quoted} 2>/dev/null || true; run_with_timeout 90 xcrun simctl bootstatus {quoted} -b || {{ echo kotoba-shell-runtime:boot-timeout; exit 124; }}; "
        ),
    )))
}

fn ios_create_temporary_simulator() -> Result<Option<String>> {
    let Some(runtime) = ios_first_runtime_id()? else {
        return Ok(None);
    };
    let Some(device_type) = ios_first_device_type_id()? else {
        return Ok(None);
    };
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let name = format!("kotoba-shell-runtime-{}-{nanos}", std::process::id());
    let output = Command::new("xcrun")
        .arg("simctl")
        .arg("create")
        .arg(&name)
        .arg(device_type)
        .arg(runtime)
        .output()
        .context("run xcrun simctl create")?;
    if !output.status.success() {
        return Ok(None);
    }
    let udid = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if udid.is_empty() {
        Ok(None)
    } else {
        Ok(Some(udid))
    }
}

fn ios_first_simulator_from_simctl(kind: &str) -> Result<Option<String>> {
    let output = Command::new("xcrun")
        .arg("simctl")
        .arg("list")
        .arg("devices")
        .arg(kind)
        .output()
        .with_context(|| format!("run xcrun simctl list devices {kind}"))?;
    if !output.status.success() {
        bail!(
            "xcrun simctl list devices {kind} failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(parse_first_ios_simulator_udid(&String::from_utf8_lossy(
        &output.stdout,
    )))
}

fn ios_first_runtime_id() -> Result<Option<String>> {
    let output = Command::new("xcrun")
        .arg("simctl")
        .arg("list")
        .arg("runtimes")
        .arg("available")
        .output()
        .context("run xcrun simctl list runtimes available")?;
    if !output.status.success() {
        bail!(
            "xcrun simctl list runtimes available failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(parse_first_ios_runtime_id(&String::from_utf8_lossy(
        &output.stdout,
    )))
}

fn ios_first_device_type_id() -> Result<Option<String>> {
    let output = Command::new("xcrun")
        .arg("simctl")
        .arg("list")
        .arg("devicetypes")
        .output()
        .context("run xcrun simctl list devicetypes")?;
    if !output.status.success() {
        bail!(
            "xcrun simctl list devicetypes failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(parse_first_iphone_device_type_id(&String::from_utf8_lossy(
        &output.stdout,
    )))
}

fn parse_first_ios_simulator_udid(src: &str) -> Option<String> {
    let mut in_ios_runtime = false;
    for line in src.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("-- ") {
            in_ios_runtime = trimmed.starts_with("-- iOS ");
            continue;
        }
        if !in_ios_runtime {
            continue;
        }
        if !trimmed.contains("iPhone") && !trimmed.contains("iPad") {
            continue;
        }
        let Some(after_open) = trimmed.split('(').nth(1) else {
            continue;
        };
        let Some(udid) = after_open.split(')').next() else {
            continue;
        };
        if udid.chars().all(|c| c.is_ascii_hexdigit() || c == '-') {
            return Some(udid.to_string());
        }
    }
    None
}

fn parse_first_ios_runtime_id(src: &str) -> Option<String> {
    src.lines().find_map(|line| {
        let trimmed = line.trim();
        if !trimmed.starts_with("iOS ") {
            return None;
        }
        trimmed
            .rsplit(" - ")
            .next()
            .filter(|id| id.starts_with("com.apple.CoreSimulator.SimRuntime.iOS-"))
            .map(str::to_string)
    })
}

fn parse_first_iphone_device_type_id(src: &str) -> Option<String> {
    src.lines().find_map(|line| {
        let trimmed = line.trim();
        if !trimmed.starts_with("iPhone ") {
            return None;
        }
        let open = trimmed.rfind('(')?;
        let close = trimmed.rfind(')')?;
        let id = &trimmed[open + 1..close];
        id.starts_with("com.apple.CoreSimulator.SimDeviceType.")
            .then(|| id.to_string())
    })
}

fn extract_quoted_assignment(src: &str, key: &str) -> Option<String> {
    let key_pos = src.find(key)?;
    let after_key = &src[key_pos + key.len()..];
    let quote_start = after_key.find('"')?;
    let after_quote = &after_key[quote_start + 1..];
    let quote_end = after_quote.find('"')?;
    Some(after_quote[..quote_end].to_string())
}

fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

fn absolute_path(path: &Path) -> Result<PathBuf> {
    if path.is_absolute() {
        Ok(path.to_path_buf())
    } else {
        Ok(std::env::current_dir()?.join(path))
    }
}

fn first_child_with_extension(root: &Path, extension: &str) -> Result<Option<PathBuf>> {
    for entry in std::fs::read_dir(root).with_context(|| format!("read {}", root.display()))? {
        let path = entry?.path();
        if path.extension().and_then(|s| s.to_str()) == Some(extension) {
            return Ok(Some(path));
        }
    }
    Ok(None)
}

fn verify_ios_project(project_dir: &Path) -> Result<ProjectVerifyReport> {
    let mut checks = Vec::new();
    require_file(
        project_dir,
        "Sources/KotobaShellApp.swift",
        &[
            "WKWebView",
            "UNUserNotificationCenter",
            "UIPasteboard.general",
            "URLSession.shared.dataTask",
            "SecItemCopyMatching",
            "CNContactStore",
            "EKEventStore",
            "KOTOBA_SHELL_READY",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/Info.plist",
        &["CFBundleIdentifier", "CFBundleName"],
        &mut checks,
    )?;
    let xcode_project = project_dir.join(format!(
        "{}.xcodeproj/project.pbxproj",
        safe_path_segment(
            project_dir
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("KotobaShell")
        )
    ));
    require_file_at(
        &xcode_project,
        &[
            "PBXNativeTarget",
            "PBXSourcesBuildPhase",
            "PBXResourcesBuildPhase",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/index.html",
        &["kotobaShell"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/kotoba-shell-release.json",
        &["\"target\": \"ios\"", "\"providers\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/kotoba-shell-permissions.json",
        &["\"target\": \"ios\"", "\"capabilities\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/kotoba-shell-capabilities.edn",
        &[":target :ios"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/aiueos-shell-surface.json",
        &[
            "\"schema\": \"aiueos.shell.surface.v0\"",
            "\"surface\": \"shell\"",
            "\"providers\"",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "Resources/aiueos-shell-surface.edn",
        &[":schema :aiueos.shell/surface.v0", ":aiueos/surface :shell"],
        &mut checks,
    )?;
    Ok(ProjectVerifyReport {
        target: Target::Ios,
        project_dir: project_dir.to_path_buf(),
        checks,
    })
}

fn verify_android_project(project_dir: &Path) -> Result<ProjectVerifyReport> {
    let mut checks = Vec::new();
    require_file(
        project_dir,
        "settings.gradle.kts",
        &["include(\":app\")"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "gradlew",
        &["gradle-8.14.3-bin", "KOTOBA_GRADLE"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "gradle.properties",
        &[
            "org.gradle.daemon=false",
            "android.nonTransitiveRClass=true",
        ],
        &mut checks,
    )?;
    require_file(project_dir, "local.properties", &["sdk.dir="], &mut checks)?;
    require_file(
        project_dir,
        "app/build.gradle.kts",
        &["com.android.application", "compileSdk = 35"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/AndroidManifest.xml",
        &["<manifest", ".MainActivity"],
        &mut checks,
    )?;
    let activity = find_android_main_activity(project_dir)?;
    require_file_at(
        &activity,
        &[
            "WebView",
            "NotificationManager",
            "ClipboardManager",
            "HttpURLConnection",
            "AndroidKeyStore",
            "AES/GCM/NoPadding",
            "ContactsContract",
            "CalendarContract",
            "requestPermissions(new String[] { permission }, requestCode)",
            "KOTOBA_SHELL_READY",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/index.html",
        &["kotobaShell"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/kotoba-shell-release.json",
        &["\"target\": \"android\"", "\"providers\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/kotoba-shell-permissions.json",
        &["\"target\": \"android\"", "\"capabilities\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/kotoba-shell-capabilities.edn",
        &[":target :android"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/aiueos-shell-surface.json",
        &[
            "\"schema\": \"aiueos.shell.surface.v0\"",
            "\"surface\": \"shell\"",
            "\"providers\"",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/src/main/assets/aiueos-shell-surface.edn",
        &[":schema :aiueos.shell/surface.v0", ":aiueos/surface :shell"],
        &mut checks,
    )?;
    Ok(ProjectVerifyReport {
        target: Target::Android,
        project_dir: project_dir.to_path_buf(),
        checks,
    })
}

fn verify_windows_project(project_dir: &Path) -> Result<ProjectVerifyReport> {
    let mut checks = Vec::new();
    require_file(project_dir, "README.md", &["Windows scaffold"], &mut checks)?;
    require_file(
        project_dir,
        "run.ps1",
        &["kotoba-shell Windows scaffold"],
        &mut checks,
    )?;
    require_file(project_dir, "app/index.html", &["kotobaShell"], &mut checks)?;
    require_file(
        project_dir,
        "app/kotoba-shell-release.json",
        &["\"target\": \"windows\"", "\"providers\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/kotoba-shell-permissions.json",
        &["\"target\": \"windows\"", "\"capabilities\""],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/kotoba-shell-capabilities.edn",
        &[":target :windows"],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/aiueos-shell-surface.json",
        &[
            "\"schema\": \"aiueos.shell.surface.v0\"",
            "\"surface\": \"shell\"",
            "\"providers\"",
        ],
        &mut checks,
    )?;
    require_file(
        project_dir,
        "app/aiueos-shell-surface.edn",
        &[":schema :aiueos.shell/surface.v0", ":aiueos/surface :shell"],
        &mut checks,
    )?;
    Ok(ProjectVerifyReport {
        target: Target::Windows,
        project_dir: project_dir.to_path_buf(),
        checks,
    })
}

fn require_file(root: &Path, rel: &str, needles: &[&str], checks: &mut Vec<String>) -> Result<()> {
    require_file_at(&root.join(rel), needles, checks)
}

fn require_executable_file(root: &Path, rel: &str, checks: &mut Vec<String>) -> Result<()> {
    let path = root.join(rel);
    let metadata =
        std::fs::metadata(&path).with_context(|| format!("metadata {}", path.display()))?;
    if !metadata.is_file() {
        bail!("{} is not a file", path.display());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if metadata.permissions().mode() & 0o111 == 0 {
            bail!("{} is not executable", path.display());
        }
    }
    checks.push(path.display().to_string());
    Ok(())
}

fn common_release_files(target: Target) -> Vec<(&'static str, Vec<&'static str>)> {
    vec![
        (
            "kotoba-shell-release.json",
            vec!["\"schema\": \"kotoba-shell.release.v0\"", "\"providers\""],
        ),
        (
            "kotoba-shell-permissions.json",
            vec![
                "\"schema\": \"kotoba-shell.permissions.v0\"",
                "\"capabilities\"",
            ],
        ),
        (
            "kotoba-shell-capabilities.edn",
            vec![match target {
                Target::Macos => ":target :macos",
                Target::Ios => ":target :ios",
                Target::Android => ":target :android",
                Target::Windows => ":target :windows",
            }],
        ),
        (
            "aiueos-shell-surface.json",
            vec!["\"schema\": \"aiueos.shell.surface.v0\"", "\"providers\""],
        ),
        (
            "aiueos-shell-surface.edn",
            vec![":schema :aiueos.shell/surface.v0", ":aiueos/surface :shell"],
        ),
        (
            "kotoba-shell-host-adapters.json",
            vec![
                "\"schema\": \"kotoba-shell.host-adapters.v0\"",
                "\"adapters\"",
            ],
        ),
        (
            "kotoba-shell-release-checklist.md",
            vec!["kotoba shell verify", "kotoba shell sdk-check"],
        ),
        (
            "kotoba-shell-updater-manifest.json",
            vec!["\"schema\": \"kotoba-shell.updater.v0\"", "\"artifact\""],
        ),
        (
            "kotoba-shell-signing-plan.json",
            vec![
                "\"schema\": \"kotoba-shell.signing-plan.v0\"",
                "\"environment\"",
            ],
        ),
        (
            "kotoba-shell-evidence-profile.json",
            vec![
                "\"schema\": \"kotoba-shell.evidence-profile.v0\"",
                "\"profiles\"",
            ],
        ),
    ]
}

fn target_release_files(target: Target) -> Vec<(&'static str, Vec<&'static str>)> {
    match target {
        Target::Macos => vec![
            (
                "aiueos-portable-plan.json",
                vec!["\"schema\": \"aiueos.portable-plan.v0\"", "\"flavors\""],
            ),
            (
                "kotoba-shell.entitlements",
                vec!["com.apple.security.app-sandbox"],
            ),
            (
                "app-store-connect-macos.json",
                vec!["kotoba-shell.apple-store.v0", "\"target\": \"macos\""],
            ),
        ],
        Target::Ios => vec![
            (
                "kotoba-shell.entitlements",
                vec!["com.apple.security.app-sandbox"],
            ),
            ("xcode-export-options.plist", vec!["signingStyle"]),
            (
                "submit-ios.sh",
                vec!["altool", "KOTOBA_APP_STORE_CONNECT_KEY_ID"],
            ),
            (
                "app-store-connect-ios.json",
                vec!["kotoba-shell.apple-store.v0", "\"target\": \"ios\""],
            ),
        ],
        Target::Android => vec![
            (
                "kotoba-shell-android-permissions.xml",
                vec!["<manifest", "uses-permission"],
            ),
            (
                "play-store-review.md",
                vec!["Android Store Review", "Capabilities"],
            ),
            (
                "play-store-data-safety.json",
                vec!["kotoba-shell.play-store-data-safety.v0", "\"dataTypes\""],
            ),
            (
                "submit-android.sh",
                vec!["androidpublisher", "KOTOBA_PLAY_SERVICE_ACCOUNT_JSON"],
            ),
        ],
        Target::Windows => vec![
            (
                "aiueos-portable-plan.json",
                vec!["\"schema\": \"aiueos.portable-plan.v0\"", "\"windows\""],
            ),
            (
                "windows-security-review.md",
                vec!["Windows Security Review", "SmartScreen", "Authenticode"],
            ),
        ],
    }
}

fn target_release_scripts(target: Target) -> &'static [&'static str] {
    match target {
        Target::Macos => &[
            "build-aiueos-core.bb",
            "build-aiueos-runner.bb",
            "sign-macos.sh",
            "notarize-macos.sh",
        ],
        Target::Ios => &["sign-ios.sh", "submit-ios.sh"],
        Target::Android => &["sign-android.sh", "submit-android.sh"],
        Target::Windows => &[
            "build-aiueos-core.bb",
            "build-aiueos-runner.bb",
            "sign-windows.sh",
            "smartscreen-windows.sh",
        ],
    }
}

fn target_signing_script(target: Target) -> &'static str {
    match target {
        Target::Macos => "sign-macos.sh",
        Target::Ios => "sign-ios.sh",
        Target::Android => "sign-android.sh",
        Target::Windows => "sign-windows.sh",
    }
}

fn signing_script_args(
    target: Target,
    release_dir: &Path,
    artifact_or_project: Option<&Path>,
    output: Option<&Path>,
) -> Vec<String> {
    let mut args = Vec::new();
    if let Some(path) = artifact_or_project {
        args.push(path.display().to_string());
        match target {
            Target::Macos => {
                args.push(
                    release_dir
                        .join("kotoba-shell.entitlements")
                        .display()
                        .to_string(),
                );
            }
            Target::Ios | Target::Android | Target::Windows => {
                if let Some(output) = output {
                    args.push(output.display().to_string());
                }
            }
        }
    } else if target == Target::Android {
        if let Some(output) = output {
            args.push("target/kotoba-shell/build/android".to_string());
            args.push(output.display().to_string());
        }
    }
    args
}

fn target_release_env(target: Target) -> &'static [&'static str] {
    match target {
        Target::Macos => &["KOTOBA_APPLE_CODESIGN_IDENTITY", "KOTOBA_NOTARY_PROFILE"],
        Target::Ios => &["KOTOBA_APPLE_TEAM_ID", "KOTOBA_IOS_SIGNING_STYLE"],
        Target::Android => &[
            "KOTOBA_ANDROID_KEYSTORE",
            "KOTOBA_ANDROID_KEY_ALIAS",
            "KOTOBA_ANDROID_KEYSTORE_PASS",
            "KOTOBA_ANDROID_KEY_PASS",
        ],
        Target::Windows => &[
            "KOTOBA_WINDOWS_CERT_PATH",
            "KOTOBA_WINDOWS_CERT_PASS",
            "KOTOBA_WINDOWS_TIMESTAMP_URL",
        ],
    }
}

fn target_submission_files(target: Target) -> Vec<(&'static str, Vec<&'static str>)> {
    match target {
        Target::Macos => vec![
            (
                "app-store-connect-macos.json",
                vec!["kotoba-shell.apple-store.v0", "\"target\": \"macos\""],
            ),
            ("notarize-macos.sh", vec!["notarytool", "stapler"]),
        ],
        Target::Ios => vec![
            (
                "app-store-connect-ios.json",
                vec!["kotoba-shell.apple-store.v0", "\"target\": \"ios\""],
            ),
            (
                "submit-ios.sh",
                vec!["altool", "KOTOBA_APP_STORE_CONNECT_KEY_ID"],
            ),
        ],
        Target::Android => vec![
            (
                "play-store-review.md",
                vec!["Android Store Review", "Capabilities"],
            ),
            (
                "play-store-data-safety.json",
                vec!["kotoba-shell.play-store-data-safety.v0", "\"dataTypes\""],
            ),
            (
                "submit-android.sh",
                vec!["androidpublisher", "KOTOBA_PLAY_SERVICE_ACCOUNT_JSON"],
            ),
        ],
        Target::Windows => vec![(
            "windows-security-review.md",
            vec![
                "Windows Security Review",
                "SmartScreen",
                "download reputation",
            ],
        )],
    }
}

fn target_submission_env(target: Target) -> &'static [&'static str] {
    match target {
        Target::Macos => &["KOTOBA_NOTARY_PROFILE"],
        Target::Ios => &[
            "KOTOBA_APP_STORE_CONNECT_KEY_ID",
            "KOTOBA_APP_STORE_CONNECT_ISSUER_ID",
            "KOTOBA_APP_STORE_CONNECT_API_KEY",
        ],
        Target::Android => &["KOTOBA_PLAY_SERVICE_ACCOUNT_JSON"],
        Target::Windows => &["KOTOBA_WINDOWS_DOWNLOAD_URL"],
    }
}

fn target_submission_script(target: Target) -> Option<&'static str> {
    match target {
        Target::Macos => Some("notarize-macos.sh"),
        Target::Ios => Some("submit-ios.sh"),
        Target::Android => Some("submit-android.sh"),
        Target::Windows => Some("smartscreen-windows.sh"),
    }
}

fn submission_script_args(
    target: Target,
    artifact: Option<&Path>,
    output: Option<&Path>,
) -> Vec<String> {
    match target {
        Target::Macos => {
            let mut args = Vec::new();
            if let Some(artifact) = artifact {
                args.push(artifact.display().to_string());
                if let Some(output) = output {
                    args.push(output.display().to_string());
                }
            }
            args
        }
        Target::Ios | Target::Android | Target::Windows => artifact
            .map(|artifact| vec![artifact.display().to_string()])
            .unwrap_or_default(),
    }
}

fn require_json_string(
    json: &serde_json::Value,
    key: &str,
    expected: &str,
    checks: &mut Vec<String>,
) -> Result<()> {
    let actual = json
        .get(key)
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("updater manifest is missing string field {key}"))?;
    if actual != expected {
        bail!("updater manifest field {key} expected `{expected}`, got `{actual}`");
    }
    checks.push(key.to_string());
    Ok(())
}

fn sha256_hex(path: &Path) -> Result<String> {
    let bytes = std::fs::read(path).with_context(|| format!("read {}", path.display()))?;
    Ok(format!("{:x}", Sha256::digest(&bytes)))
}

fn require_file_at(path: &Path, needles: &[&str], checks: &mut Vec<String>) -> Result<()> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    for needle in needles {
        if !text.contains(needle) {
            bail!("{} is missing required marker `{needle}`", path.display());
        }
    }
    checks.push(path.display().to_string());
    Ok(())
}

fn find_android_main_activity(project_dir: &Path) -> Result<PathBuf> {
    let root = project_dir.join("app/src/main/java");
    find_file_named(&root, "MainActivity.java")
        .ok_or_else(|| anyhow!("MainActivity.java not found under {}", root.display()))
}

fn find_file_named(root: &Path, name: &str) -> Option<PathBuf> {
    let entries = std::fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file() && path.file_name().and_then(|s| s.to_str()) == Some(name) {
            return Some(path);
        }
        if path.is_dir() {
            if let Some(found) = find_file_named(&path, name) {
                return Some(found);
            }
        }
    }
    None
}

pub fn prepare_dev_session(plan: &ShellPlan, out_root: impl AsRef<Path>) -> Result<DevSession> {
    let dir = out_root.as_ref().join(safe_path_segment(&plan.app_id));
    std::fs::create_dir_all(&dir).with_context(|| format!("create {}", dir.display()))?;
    let app_assets = dir.join("app");
    prepare_ui_assets(plan, &app_assets)?;
    let index_html = dir.join("index.html");
    let swift_runner = dir.join("KotobaShellDev.swift");
    std::fs::write(&index_html, dev_html(plan))
        .with_context(|| format!("write {}", index_html.display()))?;
    std::fs::write(&swift_runner, macos_swift_runner(plan))
        .with_context(|| format!("write {}", swift_runner.display()))?;
    Ok(DevSession {
        dir,
        index_html,
        swift_runner,
    })
}

pub fn run_macos_dev(session: &DevSession) -> Result<()> {
    let status = Command::new("swift")
        .arg(&session.swift_runner)
        .arg(&session.index_html)
        .status()
        .with_context(|| {
            format!(
                "launch Swift WKWebView runner {}",
                session.swift_runner.display()
            )
        })?;
    if status.success() {
        Ok(())
    } else {
        bail!("Swift WKWebView runner exited with status {status}")
    }
}

fn build_macos_app(plan: &ShellPlan, out_root: &Path) -> Result<BuildArtifact> {
    let bundle_name = format!("{}.app", safe_path_segment(&plan.app_name));
    let app_bundle = out_root.join(bundle_name);
    let contents = app_bundle.join("Contents");
    let macos = contents.join("MacOS");
    let resources = contents.join("Resources");
    let build_tmp = out_root
        .join(".build")
        .join(safe_path_segment(&plan.app_id));
    if app_bundle.exists() {
        std::fs::remove_dir_all(&app_bundle)
            .with_context(|| format!("clear {}", app_bundle.display()))?;
    }
    if build_tmp.exists() {
        std::fs::remove_dir_all(&build_tmp)
            .with_context(|| format!("clear {}", build_tmp.display()))?;
    }
    std::fs::create_dir_all(&macos).with_context(|| format!("create {}", macos.display()))?;
    std::fs::create_dir_all(&resources)
        .with_context(|| format!("create {}", resources.display()))?;
    std::fs::create_dir_all(&build_tmp)
        .with_context(|| format!("create {}", build_tmp.display()))?;
    prepare_ui_assets(plan, &resources.join("app"))?;

    let index_html = resources.join("index.html");
    let swift_runner = build_tmp.join("KotobaShellApp.swift");
    let executable = macos.join(safe_path_segment(&plan.app_name));
    let info_plist_path = contents.join("Info.plist");

    std::fs::write(&index_html, shell_html(plan, Some(Target::Macos)))
        .with_context(|| format!("write {}", index_html.display()))?;
    std::fs::write(&swift_runner, macos_swift_runner(plan))
        .with_context(|| format!("write {}", swift_runner.display()))?;
    std::fs::write(&info_plist_path, info_plist(plan, &executable))
        .with_context(|| format!("write {}", info_plist_path.display()))?;
    write_shell_metadata(plan, Target::Macos, &resources)?;

    let status = Command::new("swiftc")
        .arg("-framework")
        .arg("Cocoa")
        .arg("-framework")
        .arg("WebKit")
        .arg("-framework")
        .arg("UserNotifications")
        .arg("-framework")
        .arg("Security")
        .arg("-framework")
        .arg("Contacts")
        .arg("-framework")
        .arg("EventKit")
        .arg(&swift_runner)
        .arg("-o")
        .arg(&executable)
        .status()
        .with_context(|| format!("compile Swift runner {}", swift_runner.display()))?;
    if !status.success() {
        bail!("swiftc failed while building {}", executable.display());
    }

    Ok(BuildArtifact {
        target: Target::Macos,
        project_dir: app_bundle.clone(),
        app_bundle,
        executable,
        release_manifest: resources.join("kotoba-shell-release.json"),
    })
}

fn build_ios_scaffold(plan: &ShellPlan, out_root: &Path) -> Result<BuildArtifact> {
    let project_dir = out_root.join("ios").join(safe_path_segment(&plan.app_name));
    let sources = project_dir.join("Sources");
    let resources = project_dir.join("Resources");
    if project_dir.exists() {
        std::fs::remove_dir_all(&project_dir)
            .with_context(|| format!("clear {}", project_dir.display()))?;
    }
    std::fs::create_dir_all(&sources).with_context(|| format!("create {}", sources.display()))?;
    std::fs::create_dir_all(&resources)
        .with_context(|| format!("create {}", resources.display()))?;
    prepare_ui_assets(plan, &resources.join("app"))?;
    std::fs::write(
        resources.join("index.html"),
        shell_html(plan, Some(Target::Ios)),
    )
    .with_context(|| format!("write {}", resources.join("index.html").display()))?;
    std::fs::write(resources.join("Info.plist"), ios_info_plist(plan))
        .with_context(|| format!("write {}", resources.join("Info.plist").display()))?;
    write_shell_metadata(plan, Target::Ios, &resources)?;

    let runner = sources.join("KotobaShellApp.swift");
    std::fs::write(&runner, ios_swift_runner(plan))
        .with_context(|| format!("write {}", runner.display()))?;
    let xcodeproj = project_dir.join(format!("{}.xcodeproj", safe_path_segment(&plan.app_name)));
    std::fs::create_dir_all(&xcodeproj)
        .with_context(|| format!("create {}", xcodeproj.display()))?;
    std::fs::write(xcodeproj.join("project.pbxproj"), ios_xcode_project(plan))
        .with_context(|| format!("write {}", xcodeproj.join("project.pbxproj").display()))?;
    std::fs::write(project_dir.join("README.md"), ios_scaffold_readme(plan))
        .with_context(|| format!("write {}", project_dir.join("README.md").display()))?;
    Ok(BuildArtifact {
        target: Target::Ios,
        project_dir: project_dir.clone(),
        app_bundle: project_dir,
        executable: runner,
        release_manifest: resources.join("kotoba-shell-release.json"),
    })
}

fn build_android_scaffold(plan: &ShellPlan, out_root: &Path) -> Result<BuildArtifact> {
    let project_dir = out_root
        .join("android")
        .join(safe_path_segment(&plan.app_name));
    let app_dir = project_dir.join("app");
    let main_dir = app_dir.join("src/main");
    let java_dir = main_dir
        .join("java")
        .join(android_package_path(&plan.app_id));
    let assets_dir = main_dir.join("assets");
    if project_dir.exists() {
        std::fs::remove_dir_all(&project_dir)
            .with_context(|| format!("clear {}", project_dir.display()))?;
    }
    std::fs::create_dir_all(&java_dir).with_context(|| format!("create {}", java_dir.display()))?;
    std::fs::create_dir_all(&assets_dir)
        .with_context(|| format!("create {}", assets_dir.display()))?;
    prepare_ui_assets(plan, &assets_dir.join("app"))?;
    std::fs::write(
        assets_dir.join("index.html"),
        shell_html(plan, Some(Target::Android)),
    )
    .with_context(|| format!("write {}", assets_dir.join("index.html").display()))?;
    write_shell_metadata(plan, Target::Android, &assets_dir)?;
    std::fs::write(
        project_dir.join("settings.gradle.kts"),
        android_settings(plan),
    )
    .with_context(|| {
        format!(
            "write {}",
            project_dir.join("settings.gradle.kts").display()
        )
    })?;
    std::fs::write(project_dir.join("build.gradle.kts"), android_root_gradle())
        .with_context(|| format!("write {}", project_dir.join("build.gradle.kts").display()))?;
    let gradlew = project_dir.join("gradlew");
    std::fs::write(&gradlew, android_gradlew_script())
        .with_context(|| format!("write {}", gradlew.display()))?;
    make_executable(&gradlew)?;
    std::fs::write(project_dir.join("gradlew.bat"), android_gradlew_bat())
        .with_context(|| format!("write {}", project_dir.join("gradlew.bat").display()))?;
    std::fs::write(
        project_dir.join("gradle.properties"),
        android_gradle_properties(),
    )
    .with_context(|| format!("write {}", project_dir.join("gradle.properties").display()))?;
    std::fs::write(
        project_dir.join("local.properties"),
        android_local_properties(),
    )
    .with_context(|| format!("write {}", project_dir.join("local.properties").display()))?;
    std::fs::write(app_dir.join("build.gradle.kts"), android_app_gradle(plan))
        .with_context(|| format!("write {}", app_dir.join("build.gradle.kts").display()))?;
    std::fs::write(main_dir.join("AndroidManifest.xml"), android_manifest(plan))
        .with_context(|| format!("write {}", main_dir.join("AndroidManifest.xml").display()))?;
    let runner = java_dir.join("MainActivity.java");
    std::fs::write(&runner, android_main_activity(plan))
        .with_context(|| format!("write {}", runner.display()))?;
    std::fs::write(project_dir.join("README.md"), android_scaffold_readme(plan))
        .with_context(|| format!("write {}", project_dir.join("README.md").display()))?;
    Ok(BuildArtifact {
        target: Target::Android,
        project_dir: project_dir.clone(),
        app_bundle: project_dir,
        executable: runner,
        release_manifest: assets_dir.join("kotoba-shell-release.json"),
    })
}

fn build_windows_scaffold(plan: &ShellPlan, out_root: &Path) -> Result<BuildArtifact> {
    let project_dir = out_root
        .join("windows")
        .join(safe_path_segment(&plan.app_name));
    let app_dir = project_dir.join("app");
    if project_dir.exists() {
        std::fs::remove_dir_all(&project_dir)
            .with_context(|| format!("clear {}", project_dir.display()))?;
    }
    std::fs::create_dir_all(&app_dir).with_context(|| format!("create {}", app_dir.display()))?;
    prepare_ui_assets(plan, &app_dir.join("app"))?;
    std::fs::write(
        app_dir.join("index.html"),
        shell_html(plan, Some(Target::Windows)),
    )
    .with_context(|| format!("write {}", app_dir.join("index.html").display()))?;
    write_shell_metadata(plan, Target::Windows, &app_dir)?;
    std::fs::write(project_dir.join("README.md"), windows_scaffold_readme(plan))
        .with_context(|| format!("write {}", project_dir.join("README.md").display()))?;
    std::fs::write(project_dir.join("run.ps1"), windows_run_script(plan))
        .with_context(|| format!("write {}", project_dir.join("run.ps1").display()))?;
    Ok(BuildArtifact {
        target: Target::Windows,
        project_dir: project_dir.clone(),
        app_bundle: project_dir.clone(),
        executable: project_dir.join("run.ps1"),
        release_manifest: app_dir.join("kotoba-shell-release.json"),
    })
}

fn admit_safe_component(component: &ComponentSpec, source: &Path) -> Result<ComponentPlan> {
    let body = std::fs::read_to_string(source)
        .with_context(|| format!("read safe component {}", source.display()))?;
    let policy = kotoba_clj::minimal_policy(&body)
        .map_err(|e| anyhow!("infer minimal policy for {}: {e}", component.id))?;
    let wasm = kotoba_clj::compile_safe_clj_with_prelude(&body, &policy)
        .map_err(|e| anyhow!("safe admission rejected {}: {e}", component.id))?;
    let capability_surface = kotoba_clj::embedded_capability_ifaces(&wasm)
        .into_iter()
        .map(str::to_string)
        .collect();
    let inferred_effects = kotoba_clj::infer_effects(&body)
        .unwrap_or_default()
        .into_iter()
        .map(|(k, v)| (k, v.into_iter().collect()))
        .collect();

    Ok(ComponentPlan {
        id: component.id.clone(),
        source: source.to_path_buf(),
        safe: true,
        status: ComponentStatus::Admitted,
        exports: component.exports.clone(),
        imports: component.imports.clone(),
        wasm_bytes: Some(wasm.len()),
        policy_edn: Some(policy.to_edn()),
        capability_surface,
        inferred_effects,
    })
}

fn prepare_ui_assets(plan: &ShellPlan, out_dir: &Path) -> Result<()> {
    if !plan.ui_build_command.is_empty() {
        let (program, args) = plan
            .ui_build_command
            .split_first()
            .ok_or_else(|| anyhow!("empty ui build command"))?;
        let status = Command::new(program)
            .args(args)
            .current_dir(&plan.manifest_dir)
            .status()
            .with_context(|| {
                format!(
                    "run ui build command `{}` in {}",
                    plan.ui_build_command.join(" "),
                    plan.manifest_dir.display()
                )
            })?;
        if !status.success() {
            bail!(
                "ui build command `{}` exited with status {status}",
                plan.ui_build_command.join(" ")
            );
        }
    }

    let Some(dist) = &plan.ui_dist else {
        return Ok(());
    };
    let src = plan.manifest_dir.join(dist);
    if !src.is_dir() {
        bail!("ui dist directory does not exist: {}", src.display());
    }
    if out_dir.exists() {
        std::fs::remove_dir_all(out_dir).with_context(|| format!("clear {}", out_dir.display()))?;
    }
    copy_dir_all(&src, out_dir)
        .with_context(|| format!("copy ui dist {} -> {}", src.display(), out_dir.display()))?;
    Ok(())
}

fn copy_dir_all(src: &Path, dst: &Path) -> Result<()> {
    std::fs::create_dir_all(dst).with_context(|| format!("create {}", dst.display()))?;
    for entry in std::fs::read_dir(src).with_context(|| format!("read dir {}", src.display()))? {
        let entry = entry?;
        let ty = entry.file_type()?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if ty.is_dir() {
            copy_dir_all(&from, &to)?;
        } else if ty.is_file() {
            std::fs::copy(&from, &to)
                .with_context(|| format!("copy {} -> {}", from.display(), to.display()))?;
        }
    }
    Ok(())
}

fn safe_path_segment(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_') {
                c
            } else {
                '_'
            }
        })
        .collect()
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn js_string(s: &str) -> String {
    format!("{:?}", s)
}

fn swift_string(s: &str) -> String {
    format!(
        "\"{}\"",
        s.replace('\\', "\\\\")
            .replace('"', "\\\"")
            .replace('\n', "\\n")
            .replace('\r', "\\r")
    )
}

fn write_shell_metadata(plan: &ShellPlan, target: Target, out_dir: &Path) -> Result<()> {
    std::fs::create_dir_all(out_dir).with_context(|| format!("create {}", out_dir.display()))?;
    let permissions = target_capabilities(plan, target);
    let permissions_json = serde_json::json!({
        "schema": "kotoba-shell.permissions.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "capabilities": permissions,
        "components": plan.components.iter().map(|c| {
            serde_json::json!({
                "id": c.id,
                "safe": c.safe,
                "status": format!("{:?}", c.status),
                "source": c.source.display().to_string(),
                "exports": c.exports,
                "imports": c.imports,
                "capabilitySurface": c.capability_surface,
                "inferredEffects": c.inferred_effects,
            })
        }).collect::<Vec<_>>(),
    });
    let json = serde_json::to_string_pretty(&permissions_json)?;
    std::fs::write(out_dir.join("kotoba-shell-permissions.json"), json).with_context(|| {
        format!(
            "write {}",
            out_dir.join("kotoba-shell-permissions.json").display()
        )
    })?;
    std::fs::write(
        out_dir.join("kotoba-shell-capabilities.edn"),
        capability_metadata_edn(plan, target),
    )
    .with_context(|| {
        format!(
            "write {}",
            out_dir.join("kotoba-shell-capabilities.edn").display()
        )
    })?;
    std::fs::write(
        out_dir.join("kotoba-shell-release.json"),
        release_manifest_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            out_dir.join("kotoba-shell-release.json").display()
        )
    })?;
    std::fs::write(
        out_dir.join("aiueos-shell-surface.json"),
        aiueos_shell_surface_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            out_dir.join("aiueos-shell-surface.json").display()
        )
    })?;
    std::fs::write(
        out_dir.join("aiueos-shell-surface.edn"),
        aiueos_shell_surface_edn(plan, target),
    )
    .with_context(|| {
        format!(
            "write {}",
            out_dir.join("aiueos-shell-surface.edn").display()
        )
    })?;
    std::fs::write(
        out_dir.join("kotoba-shell-host-adapters.json"),
        host_adapter_manifest_json(plan, target)?,
    )
    .with_context(|| {
        format!(
            "write {}",
            out_dir.join("kotoba-shell-host-adapters.json").display()
        )
    })?;
    match target {
        Target::Macos | Target::Ios => {
            std::fs::write(
                out_dir.join("kotoba-shell.entitlements"),
                apple_entitlements_plist(plan, target),
            )
            .with_context(|| {
                format!(
                    "write {}",
                    out_dir.join("kotoba-shell.entitlements").display()
                )
            })?;
        }
        Target::Android => {
            std::fs::write(
                out_dir.join("kotoba-shell-android-permissions.xml"),
                android_permissions_xml(plan),
            )
            .with_context(|| {
                format!(
                    "write {}",
                    out_dir
                        .join("kotoba-shell-android-permissions.xml")
                        .display()
                )
            })?;
        }
        Target::Windows => {}
    }
    Ok(())
}

fn release_manifest_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let capabilities = target_capabilities(plan, target);
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.release.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "ui": {
            "entry": plan.ui_entry,
            "dist": plan.ui_dist.as_ref().map(|p| p.display().to_string()),
            "index": plan.ui_index,
        },
        "capabilities": capabilities,
        "aiueos": {
            "surface": "shell",
            "brokerContract": "aiueos.shell.surface.v0",
            "componentSupervisor": {
                "verify": "safe-clj-admission-policy-and-provider-link",
                "pureDryRun": "wasmtime-fuel"
            },
            "audit": {
                "mode": "append-only-command-log",
                "macosDevPath": "Application Support/kotoba-shell-dev/{appId}/audit/commands.jsonl"
            },
            "surfaceMetadata": ["aiueos-shell-surface.json", "aiueos-shell-surface.edn"]
        },
        "nativeReview": {
            "requiresNetworkClient": capabilities.iter().any(|c| is_network_capability(c)),
            "requiresNotifications": capabilities.iter().any(|c| c == "notify/show"),
            "requiresClipboard": capabilities.iter().any(|c| is_clipboard_capability(c)),
            "requiresContacts": capabilities.iter().any(|c| is_contacts_capability(c)),
            "requiresCalendar": capabilities.iter().any(|c| is_calendar_capability(c)),
            "requiresExternalFileAccess": capabilities.iter().any(|c| c.starts_with("fs/user") || c.starts_with("fs/external")),
            "usesOnlyAppDataStorage": capabilities.iter().any(|c| c == "fs/app-data")
        },
        "providers": provider_catalog_json(&capabilities),
        "components": plan.components.iter().map(|c| {
            serde_json::json!({
                "id": c.id,
                "safe": c.safe,
                "status": format!("{:?}", c.status),
                "wasmBytes": c.wasm_bytes,
                "policyEdn": c.policy_edn,
                "exports": c.exports,
                "imports": c.imports,
                "capabilitySurface": c.capability_surface,
                "inferredEffects": c.inferred_effects,
            })
        }).collect::<Vec<_>>(),
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn host_adapter_manifest_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let surfaces = component_host_surfaces(plan);
    let adapters = [
        (
            "auth",
            "kotoba:kais/auth@0.1.0",
            vec!["KOTOBA_AUTH_ADAPTER_URL"],
            "CACAO/capability introspection service",
        ),
        (
            "kqe",
            "kotoba:kais/kqe@0.1.0",
            vec!["KOTOBA_KQE_ADAPTER_URL"],
            "KQE graph read/write service",
        ),
        (
            "llm",
            "kotoba:kais/llm@0.1.0",
            vec!["KOTOBA_LLM_ADAPTER_URL"],
            "LLM inference service",
        ),
    ]
    .into_iter()
    .map(|(id, iface, env, description)| {
        let required = surfaces.contains(iface);
        serde_json::json!({
            "id": id,
            "interface": iface,
            "required": required,
            "env": env,
            "description": description,
            "healthProbe": {
                "tool": "curl",
                "method": "HEAD",
                "urlEnv": env.first().copied().unwrap_or("")
            },
            "smokeInvocation": {
                "tool": "curl",
                "method": "POST",
                "contentType": "application/json",
                "request": adapter_smoke_payload_value(id),
                "response": adapter_smoke_response_contract_value(id)
            },
            "fallback": if required { "supervisor dry-run only; production adapter required" } else { "not used by this app" }
        })
    })
    .collect::<Vec<_>>();
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.host-adapters.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "componentSupervisor": {
            "mode": "production-host-service-adapters",
            "dryRun": "wasmtime-fuel",
            "requiredInterfaces": surfaces.iter().cloned().collect::<Vec<_>>()
        },
        "adapters": adapters,
        "components": plan.components.iter().map(|component| {
            serde_json::json!({
                "id": component.id,
                "capabilitySurface": component.capability_surface,
                "inferredEffects": component.inferred_effects,
            })
        }).collect::<Vec<_>>()
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn adapter_smoke_payload_value(id: &str) -> serde_json::Value {
    match id {
        "auth" => serde_json::json!({
            "schema": "kotoba-shell.adapter-smoke.v0",
            "operation": "auth.has-capability",
            "resource": "graph/x",
            "ability": "read"
        }),
        "kqe" => serde_json::json!({
            "schema": "kotoba-shell.adapter-smoke.v0",
            "operation": "kqe.query",
            "filter": ""
        }),
        "llm" => serde_json::json!({
            "schema": "kotoba-shell.adapter-smoke.v0",
            "operation": "llm.infer",
            "model": "modelA",
            "prompt": "ping"
        }),
        _ => serde_json::json!({
            "schema": "kotoba-shell.adapter-smoke.v0",
            "operation": "unknown"
        }),
    }
}

fn adapter_smoke_response_contract_value(id: &str) -> serde_json::Value {
    match id {
        "auth" => serde_json::json!({
            "allowed": "boolean"
        }),
        "kqe" => serde_json::json!({
            "quads": "array"
        }),
        "llm" => serde_json::json!({
            "output": "string"
        }),
        _ => serde_json::json!({}),
    }
}

fn component_host_surfaces(plan: &ShellPlan) -> BTreeSet<String> {
    plan.components
        .iter()
        .flat_map(|component| component.capability_surface.iter().cloned())
        .collect()
}

fn aiueos_shell_surface_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let capabilities = target_capabilities(plan, target);
    let surface = serde_json::json!({
        "schema": "aiueos.shell.surface.v0",
        "surface": "shell",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "broker": {
            "verify": "safe-clj-admission-before-provider-link",
            "dispatch": "capability-command",
            "audit": "append-only-command-log"
        },
        "componentSupervisor": {
            "verify": "safe-clj-admission-policy-and-provider-link",
            "pureDryRun": "wasmtime-fuel"
        },
        "audit": {
            "schema": "aiueos.shell.audit.v0",
            "events": ["request", "reply"],
            "fields": ["ts", "app", "command", "requestId", "ok", "phase", "value", "error"],
            "macosDevPath": format!("Application Support/kotoba-shell-dev/{}/audit/commands.jsonl", plan.app_id)
        },
        "providers": provider_catalog_json(&capabilities),
        "components": plan.components.iter().map(|c| {
            serde_json::json!({
                "id": c.id,
                "safe": c.safe,
                "status": format!("{:?}", c.status),
                "policyEdn": c.policy_edn,
                "exports": c.exports,
                "imports": c.imports,
                "capabilitySurface": c.capability_surface,
                "inferredEffects": c.inferred_effects,
            })
        }).collect::<Vec<_>>(),
    });
    serde_json::to_string_pretty(&surface).map_err(Into::into)
}

fn aiueos_shell_surface_edn(plan: &ShellPlan, target: Target) -> String {
    let capabilities = target_capabilities(plan, target);
    let providers = provider_catalog_json(&capabilities)
        .into_iter()
        .filter_map(|p| {
            let id = p.get("id")?.as_str()?;
            let capability = p.get("capability")?.as_str()?;
            let commands = p
                .get("commands")?
                .as_array()?
                .iter()
                .filter_map(|c| c.as_str())
                .map(|c| format!(":{}", c.replace('/', "/")))
                .collect::<Vec<_>>()
                .join(" ");
            Some(format!(
                "{{:id :{} :capability :{} :commands #{{{}}}}}",
                id, capability, commands
            ))
        })
        .collect::<Vec<_>>()
        .join("\n  ");
    format!(
        "{{:schema :aiueos.shell/surface.v0\n :aiueos/surface :shell\n :app/id {:?}\n :app/name {:?}\n :target :{}\n :broker {{:verify :safe-clj-admission-before-provider-link\n          :dispatch :capability-command\n          :audit :append-only-command-log}}\n :component-supervisor {{:verify :safe-clj-admission-policy-and-provider-link\n                        :pure-dry-run :wasmtime-fuel}}\n :audit {{:schema :aiueos.shell/audit.v0\n         :events [:request :reply]\n         :macos-dev-path {:?}}}\n :providers [{}]}}\n",
        plan.app_id,
        plan.app_name,
        target.as_str(),
        format!(
            "Application Support/kotoba-shell-dev/{}/audit/commands.jsonl",
            plan.app_id
        ),
        providers
    )
}

fn provider_catalog_json(capabilities: &[String]) -> Vec<serde_json::Value> {
    let mut providers = Vec::new();
    if capabilities.iter().any(|c| c == "fs/app-data") {
        providers.push(serde_json::json!({
            "id": "shell/fs-app-data",
            "capability": "fs/app-data",
            "commands": ["fs/read-text", "fs/write-text", "fs/append-text"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| c == "notify/show") {
        providers.push(serde_json::json!({
            "id": "shell/notification",
            "capability": "notify/show",
            "commands": ["notify/show"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| is_clipboard_capability(c)) {
        providers.push(serde_json::json!({
            "id": "shell/clipboard",
            "capability": "clipboard/text",
            "commands": ["clipboard/read-text", "clipboard/write-text"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| is_http_fetch_capability(c)) {
        providers.push(serde_json::json!({
            "id": "shell/http-fetch",
            "capability": "http/fetch",
            "commands": ["http/fetch"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| is_keychain_capability(c)) {
        providers.push(serde_json::json!({
            "id": "shell/keychain",
            "capability": "keychain/text",
            "commands": ["keychain/read-text", "keychain/write-text", "keychain/delete"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| is_contacts_capability(c)) {
        providers.push(serde_json::json!({
            "id": "shell/contacts",
            "capability": "contacts/read",
            "commands": ["contacts/list"],
            "status": "implemented-shell-provider"
        }));
    }
    if capabilities.iter().any(|c| is_calendar_capability(c)) {
        providers.push(serde_json::json!({
            "id": "shell/calendar",
            "capability": "calendar/read",
            "commands": ["calendar/list-events"],
            "status": "implemented-shell-provider"
        }));
    }
    providers
}

fn apple_entitlements_plist(plan: &ShellPlan, target: Target) -> String {
    let caps = target_capabilities(plan, target);
    let network = caps.iter().any(|c| is_network_capability(c));
    let user_files = caps
        .iter()
        .any(|c| c.starts_with("fs/user") || c.starts_with("fs/external"));
    let push = caps.iter().any(|c| c == "notify/push");
    let mut entries = String::new();
    entries.push_str("  <key>com.apple.security.app-sandbox</key>\n  <true/>\n");
    if network {
        entries.push_str("  <key>com.apple.security.network.client</key>\n  <true/>\n");
    }
    if user_files {
        entries.push_str(
            "  <key>com.apple.security.files.user-selected.read-write</key>\n  <true/>\n",
        );
    }
    if target == Target::Ios && push {
        entries.push_str("  <key>aps-environment</key>\n  <string>development</string>\n");
    }
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
{entries}</dict>
</plist>
"#
    )
}

fn android_permissions_xml(plan: &ShellPlan) -> String {
    let caps = target_capabilities(plan, Target::Android);
    let body = android_permission_lines(&caps);
    format!(
        r#"<manifest xmlns:android="http://schemas.android.com/apk/res/android">
{body}
</manifest>
"#
    )
}

fn android_permission_lines(caps: &[String]) -> String {
    let mut permissions = Vec::new();
    if caps
        .iter()
        .any(|c| c == "notify/show" || c == "notify/push")
    {
        permissions.push("android.permission.POST_NOTIFICATIONS");
    }
    if caps.iter().any(|c| is_network_capability(c)) {
        permissions.push("android.permission.INTERNET");
    }
    if caps.iter().any(|c| is_contacts_capability(c)) {
        permissions.push("android.permission.READ_CONTACTS");
    }
    if caps.iter().any(|c| is_calendar_capability(c)) {
        permissions.push("android.permission.READ_CALENDAR");
    }
    permissions
        .into_iter()
        .map(|p| format!(r#"  <uses-permission android:name="{p}" />"#))
        .collect::<Vec<_>>()
        .join("\n")
}

fn is_network_capability(capability: &str) -> bool {
    matches!(
        capability,
        "http/fetch" | "net/fetch" | "net/connect" | "ledger/append"
    ) || capability.starts_with("http/")
        || capability.starts_with("net/")
}

fn is_http_fetch_capability(capability: &str) -> bool {
    matches!(capability, "http/fetch" | "net/fetch") || capability.starts_with("http/")
}

fn is_clipboard_capability(capability: &str) -> bool {
    matches!(
        capability,
        "clipboard/read" | "clipboard/write" | "clipboard/read-text" | "clipboard/write-text"
    ) || capability.starts_with("clipboard/")
}

fn is_keychain_capability(capability: &str) -> bool {
    matches!(
        capability,
        "keychain/read" | "keychain/write" | "keychain/read-text" | "keychain/write-text"
    ) || capability.starts_with("keychain/")
}

fn is_contacts_capability(capability: &str) -> bool {
    matches!(capability, "contacts/read" | "contacts/list") || capability.starts_with("contacts/")
}

fn is_calendar_capability(capability: &str) -> bool {
    matches!(capability, "calendar/read" | "calendar/list-events")
        || capability.starts_with("calendar/")
}

fn macos_notarize_script(plan: &ShellPlan) -> String {
    let zip_name = format!("{}.zip", safe_path_segment(&plan.app_name));
    let app_name = format!("{}.app", safe_path_segment(&plan.app_name));
    format!(
        r#"#!/bin/sh
set -eu

APP_BUNDLE="${{1:-target/kotoba-shell/build/{app_name}}}"
ZIP_PATH="${{2:-target/kotoba-shell/release/{zip_name}}}"

ditto -c -k --keepParent "$APP_BUNDLE" "$ZIP_PATH"

echo "Created $ZIP_PATH"
echo "Submit with:"
echo "  xcrun notarytool submit \"$ZIP_PATH\" --keychain-profile <profile> --wait"
echo "Then staple with:"
echo "  xcrun stapler staple \"$APP_BUNDLE\""
"#,
        app_name = app_name,
        zip_name = zip_name
    )
}

fn signing_plan_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.signing-plan.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "version": "0.1.0",
        "artifacts": match target {
            Target::Macos => serde_json::json!({
                "bundle": format!("target/kotoba-shell/build/{}.app", safe_path_segment(&plan.app_name)),
                "entitlements": "kotoba-shell.entitlements",
                "signedArchive": format!("{}.zip", safe_path_segment(&plan.app_name)),
            }),
            Target::Ios => serde_json::json!({
                "xcodeProject": format!("target/kotoba-shell/build/ios/{}", safe_path_segment(&plan.app_name)),
                "exportOptions": "xcode-export-options.plist",
                "archive": format!("{}.xcarchive", safe_path_segment(&plan.app_name)),
                "ipa": format!("{}.ipa", safe_path_segment(&plan.app_name)),
            }),
            Target::Android => serde_json::json!({
                "gradleProject": format!("target/kotoba-shell/build/android/{}", safe_path_segment(&plan.app_name)),
                "aab": "app/build/outputs/bundle/release/app-release.aab",
                "signedAab": format!("{}-release-signed.aab", safe_path_segment(&plan.app_name)),
            }),
            Target::Windows => serde_json::json!({
                "project": format!("target/kotoba-shell/build/windows/{}", safe_path_segment(&plan.app_name)),
                "executable": format!("target/kotoba-shell/build/windows/{}/dist/{}.exe", safe_path_segment(&plan.app_name), safe_path_segment(&plan.app_name)),
                "archive": format!("{}.zip", safe_path_segment(&plan.app_name)),
                "signedExecutable": format!("{}-signed.exe", safe_path_segment(&plan.app_name)),
            }),
        },
        "environment": match target {
            Target::Macos => serde_json::json!({
                "KOTOBA_APPLE_CODESIGN_IDENTITY": "Developer ID Application: ...",
                "KOTOBA_NOTARY_PROFILE": "notarytool keychain profile"
            }),
            Target::Ios => serde_json::json!({
                "KOTOBA_APPLE_TEAM_ID": "Apple Developer Team ID",
                "KOTOBA_IOS_SIGNING_STYLE": "automatic or manual"
            }),
            Target::Android => serde_json::json!({
                "KOTOBA_ANDROID_KEYSTORE": "path to upload keystore",
                "KOTOBA_ANDROID_KEY_ALIAS": "upload key alias",
                "KOTOBA_ANDROID_KEYSTORE_PASS": "keystore password",
                "KOTOBA_ANDROID_KEY_PASS": "key password"
            }),
            Target::Windows => serde_json::json!({
                "KOTOBA_WINDOWS_CERT_PATH": "path to Authenticode PFX/P12 certificate",
                "KOTOBA_WINDOWS_CERT_PASS": "certificate password",
                "KOTOBA_WINDOWS_TIMESTAMP_URL": "timestamp URL",
                "KOTOBA_WINDOWS_DOWNLOAD_URL": "stable HTTPS download URL for SmartScreen reputation"
            }),
        },
        "gates": [
            "kotoba shell verify",
            "store disclosure metadata review",
            "aiueos shell surface review",
            "updater manifest signature review"
        ]
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn evidence_profile_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let release_profile = match target {
        Target::Android => "android-release",
        Target::Ios | Target::Macos | Target::Windows => "store-release",
    };
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.evidence-profile.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "profiles": {
            "ci": evidence_profile_requirements("ci").unwrap_or_default(),
            release_profile: release_evidence_profile_requirements(target)
        },
        "commands": {
            "ci": "kotoba shell evidence-check <evidence-dir> --profile ci --evidence <summary.json>",
            "coverage": "kotoba shell coverage --json --evidence <coverage-evidence.json>",
            "doctor": format!("kotoba shell doctor-check --target {} --probe --evidence <{}-runtime-doctor-evidence.json>", target.as_str(), target.as_str()),
            "release": format!("kotoba shell evidence-check <evidence-dir> --profile {release_profile} --evidence <summary.json>")
        },
        "statusSemantics": {
            "Passed": "all required evidence for the selected profile passed",
            "Skipped": "no failures and no required evidence missing, but at least one non-required evidence was skipped",
            "Failed": "a required evidence file is missing, failed, or skipped"
        }
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn macos_sign_script(plan: &ShellPlan) -> String {
    let app_name = format!("{}.app", safe_path_segment(&plan.app_name));
    format!(
        r#"#!/bin/sh
set -eu

APP_BUNDLE="${{1:-target/kotoba-shell/build/{app_name}}}"
IDENTITY="${{KOTOBA_APPLE_CODESIGN_IDENTITY:?set KOTOBA_APPLE_CODESIGN_IDENTITY}}"
ENTITLEMENTS="${{2:-kotoba-shell.entitlements}}"

codesign --force --deep --options runtime --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
"#,
        app_name = app_name
    )
}

fn ios_sign_script(plan: &ShellPlan) -> String {
    let project = format!(
        "target/kotoba-shell/build/ios/{}",
        safe_path_segment(&plan.app_name)
    );
    let archive = format!("{}.xcarchive", safe_path_segment(&plan.app_name));
    format!(
        r#"#!/bin/sh
set -eu

PROJECT_DIR="${{1:-{project}}}"
ARCHIVE_PATH="${{2:-target/kotoba-shell/release/{archive}}}"
EXPORT_DIR="${{3:-target/kotoba-shell/release/ios-export}}"
EXPORT_OPTIONS="${{4:-xcode-export-options.plist}}"

xcodebuild archive -project "$PROJECT_DIR" -scheme "{scheme}" -archivePath "$ARCHIVE_PATH"
xcodebuild -exportArchive -archivePath "$ARCHIVE_PATH" -exportOptionsPlist "$EXPORT_OPTIONS" -exportPath "$EXPORT_DIR"
"#,
        project = project,
        archive = archive,
        scheme = safe_path_segment(&plan.app_name)
    )
}

fn android_sign_script(plan: &ShellPlan) -> String {
    let project = format!(
        "target/kotoba-shell/build/android/{}",
        safe_path_segment(&plan.app_name)
    );
    format!(
        r#"#!/bin/sh
set -eu

PROJECT_DIR="${{1:-{project}}}"
KEYSTORE="${{KOTOBA_ANDROID_KEYSTORE:?set KOTOBA_ANDROID_KEYSTORE}}"
KEY_ALIAS="${{KOTOBA_ANDROID_KEY_ALIAS:?set KOTOBA_ANDROID_KEY_ALIAS}}"
STORE_PASS="${{KOTOBA_ANDROID_KEYSTORE_PASS:?set KOTOBA_ANDROID_KEYSTORE_PASS}}"
KEY_PASS="${{KOTOBA_ANDROID_KEY_PASS:?set KOTOBA_ANDROID_KEY_PASS}}"
GRADLE="${{KOTOBA_GRADLE:-./gradlew}}"

if [ ! -x "$PROJECT_DIR/gradlew" ] && [ "$GRADLE" = "./gradlew" ]; then
  GRADLE="gradle"
fi

(cd "$PROJECT_DIR" && "$GRADLE" bundleRelease)

AAB="$PROJECT_DIR/app/build/outputs/bundle/release/app-release.aab"
SIGNED_AAB="${{2:-$PROJECT_DIR/app-release-signed.aab}}"

jarsigner -keystore "$KEYSTORE" -storepass "$STORE_PASS" -keypass "$KEY_PASS" "$AAB" "$KEY_ALIAS"
cp "$AAB" "$SIGNED_AAB"
"#,
        project = project
    )
}

fn ios_submit_script(plan: &ShellPlan) -> String {
    let ipa = format!(
        "target/kotoba-shell/release/ios-export/{}.ipa",
        safe_path_segment(&plan.app_name)
    );
    format!(
        r#"#!/bin/sh
set -eu

IPA_PATH="${{1:-{ipa}}}"
KEY_ID="${{KOTOBA_APP_STORE_CONNECT_KEY_ID:?set KOTOBA_APP_STORE_CONNECT_KEY_ID}}"
ISSUER_ID="${{KOTOBA_APP_STORE_CONNECT_ISSUER_ID:?set KOTOBA_APP_STORE_CONNECT_ISSUER_ID}}"
API_KEY_PATH="${{KOTOBA_APP_STORE_CONNECT_API_KEY:?set KOTOBA_APP_STORE_CONNECT_API_KEY}}"

if [ ! -f "$IPA_PATH" ]; then
  echo "IPA does not exist: $IPA_PATH" >&2
  exit 2
fi

xcrun altool --upload-app \
  --type ios \
  --file "$IPA_PATH" \
  --apiKey "$KEY_ID" \
  --apiIssuer "$ISSUER_ID" \
  --apiKeyPath "$API_KEY_PATH"
"#,
        ipa = ipa
    )
}

fn android_submit_script(plan: &ShellPlan) -> String {
    let aab = format!(
        "target/kotoba-shell/build/android/{}/app-release-signed.aab",
        safe_path_segment(&plan.app_name)
    );
    format!(
        r#"#!/bin/sh
set -eu

AAB_PATH="${{1:-{aab}}}"
SERVICE_ACCOUNT_JSON="${{KOTOBA_PLAY_SERVICE_ACCOUNT_JSON:?set KOTOBA_PLAY_SERVICE_ACCOUNT_JSON}}"
PACKAGE_NAME="${{KOTOBA_ANDROID_PACKAGE_NAME:-{package}}}"
TRACK="${{KOTOBA_PLAY_TRACK:-internal}}"
COMMIT="${{KOTOBA_PLAY_COMMIT:-false}}"

if [ ! -f "$AAB_PATH" ]; then
  echo "AAB does not exist: $AAB_PATH" >&2
  exit 2
fi
if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is required to mint an Android Publisher API access token" >&2
  exit 2
fi

gcloud auth activate-service-account --key-file "$SERVICE_ACCOUNT_JSON" >/dev/null
TOKEN="$(gcloud auth print-access-token)"
API_ROOT="https://androidpublisher.googleapis.com/androidpublisher/v3/applications/$PACKAGE_NAME"
UPLOAD_ROOT="https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/$PACKAGE_NAME"

EDIT_JSON="$(curl --fail --silent --show-error -X POST \
  -H "authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  "$API_ROOT/edits")"
EDIT_ID="$(printf "%s" "$EDIT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

BUNDLE_JSON="$(curl --fail --silent --show-error -X POST \
  -H "authorization: Bearer $TOKEN" \
  -H "content-type: application/octet-stream" \
  --data-binary "@$AAB_PATH" \
  "$UPLOAD_ROOT/edits/$EDIT_ID/bundles?uploadType=media")"
VERSION_CODE="$(printf "%s" "$BUNDLE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["versionCode"])')"

curl --fail --silent --show-error -X PUT \
  -H "authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  --data "{{\"releases\":[{{\"versionCodes\":[\"$VERSION_CODE\"],\"status\":\"draft\"}}]}}" \
  "$API_ROOT/edits/$EDIT_ID/tracks/$TRACK" >/dev/null

if [ "$COMMIT" = "true" ]; then
  curl --fail --silent --show-error -X POST \
    -H "authorization: Bearer $TOKEN" \
    "$API_ROOT/edits/$EDIT_ID:commit" >/dev/null
  echo "Uploaded and committed $AAB_PATH to $PACKAGE_NAME track $TRACK versionCode $VERSION_CODE"
else
  echo "Uploaded $AAB_PATH to draft edit $EDIT_ID for $PACKAGE_NAME track $TRACK versionCode $VERSION_CODE"
  echo "Set KOTOBA_PLAY_COMMIT=true to commit the edit."
fi
"#,
        aab = aab,
        package = plan.app_id
    )
}

fn windows_sign_script(plan: &ShellPlan) -> String {
    let exe_name = format!("{}.exe", safe_path_segment(&plan.app_name));
    format!(
        r#"#!/bin/sh
set -eu

ARTIFACT="${{1:-target/kotoba-shell/build/windows/{app}/dist/{exe_name}}}"
OUTPUT="${{2:-$ARTIFACT}}"
CERT_PATH="${{KOTOBA_WINDOWS_CERT_PATH:?set KOTOBA_WINDOWS_CERT_PATH}}"
CERT_PASS="${{KOTOBA_WINDOWS_CERT_PASS:?set KOTOBA_WINDOWS_CERT_PASS}}"
TIMESTAMP_URL="${{KOTOBA_WINDOWS_TIMESTAMP_URL:-http://timestamp.digicert.com}}"

if [ "$OUTPUT" != "$ARTIFACT" ]; then
  cp "$ARTIFACT" "$OUTPUT"
fi

if command -v signtool.exe >/dev/null 2>&1; then
  signtool.exe sign /fd SHA256 /tr "$TIMESTAMP_URL" /td SHA256 /f "$CERT_PATH" /p "$CERT_PASS" "$OUTPUT"
elif command -v signtool >/dev/null 2>&1; then
  signtool sign /fd SHA256 /tr "$TIMESTAMP_URL" /td SHA256 /f "$CERT_PATH" /p "$CERT_PASS" "$OUTPUT"
elif command -v osslsigncode >/dev/null 2>&1; then
  TMP="$OUTPUT.signed"
  osslsigncode sign -pkcs12 "$CERT_PATH" -pass "$CERT_PASS" -n "{name}" -t "$TIMESTAMP_URL" -in "$OUTPUT" -out "$TMP"
  mv "$TMP" "$OUTPUT"
else
  echo "signtool.exe, signtool, or osslsigncode is required for Authenticode signing" >&2
  exit 2
fi

echo "signed: $OUTPUT"
"#,
        app = safe_path_segment(&plan.app_name),
        exe_name = exe_name,
        name = plan.app_name
    )
}

fn windows_smartscreen_script(plan: &ShellPlan) -> String {
    let archive = format!("{}.zip", safe_path_segment(&plan.app_name));
    format!(
        r#"#!/bin/sh
set -eu

ARTIFACT="${{1:-target/kotoba-shell/release/{archive}}}"
DOWNLOAD_URL="${{KOTOBA_WINDOWS_DOWNLOAD_URL:?set KOTOBA_WINDOWS_DOWNLOAD_URL}}"

test -f "$ARTIFACT"
case "$DOWNLOAD_URL" in
  https://*) ;;
  *) echo "KOTOBA_WINDOWS_DOWNLOAD_URL must be HTTPS for SmartScreen reputation" >&2; exit 2 ;;
esac

echo "SmartScreen has no notarization equivalent."
echo "Release gate evidence to collect:"
echo "  publisher: same Authenticode subject across releases"
echo "  artifact:  $ARTIFACT"
echo "  url:       $DOWNLOAD_URL"
echo "  channel:   stable HTTPS domain, no rotating unsigned mirrors"
echo "  telemetry: first-run support reports for Windows protected your PC warnings"
"#,
        archive = archive
    )
}

fn release_checklist(plan: &ShellPlan, target: Target) -> String {
    let caps = target_capabilities(plan, target);
    let target_name = target.as_str();
    format!(
        r#"# {name} {target_name} Release Checklist

Generated from `app.kotoba.edn`.

## Required gates

- [ ] `kotoba shell check app.kotoba.edn`
- [ ] `kotoba shell build app.kotoba.edn --target {target_name}`
- [ ] `kotoba shell verify --target {target_name} <artifact-or-project>`
- [ ] `kotoba shell broker-check app.kotoba.edn --target {target_name}`
- [ ] `kotoba shell broker-check app.kotoba.edn --target {target_name} --command <capability-command> --audit-log <audit.jsonl>`
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --arg <i64>` for pure safe components
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --auth-grant <resource:ability> --arg <i64>` for auth host-bound safe components
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --component <kqe-component>` for kqe mutate host-bound safe components
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --component <kqe-component> --kqe-quad <graph,subject,predicate,object>` for kqe read/query host-bound safe components
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --component <llm-component> --llm-echo` for llm host-bound safe components
- [ ] `kotoba shell adapter-check --target {target_name} --probe --smoke <release-dir>/kotoba-shell-host-adapters.json`
- [ ] `kotoba shell adapter-check --target {target_name} --hosted --probe --smoke --evidence <hosted-adapter-evidence.json> <release-dir>/kotoba-shell-host-adapters.json`
- [ ] `kotoba shell supervisor-check app.kotoba.edn --target {target_name} --run --adapter-manifest <release-dir>/kotoba-shell-host-adapters.json --component <host-bound-component> --evidence <evidence.json>` for live production adapter-backed safe components
- [ ] `kotoba shell doctor-check --target {target_name} --probe --evidence <{target_name}-runtime-doctor-evidence.json>`
- [ ] `kotoba shell sdk-check --target {target_name} --evidence <sdk-evidence.json> <generated-project>` when native SDK tools are available
- [ ] `kotoba shell runtime-check --target {target_name} --evidence <runtime-evidence.json> <generated-project>` when a device/simulator is available
- [ ] `kotoba shell release-check --target {target_name} <release-dir>`
- [ ] `kotoba shell signing-check --target {target_name} --execute --evidence <signing-evidence.json> <release-dir>` when production signing credentials are available
- [ ] `kotoba shell submission-check --target {target_name} --execute --evidence <submission-evidence.json> <release-dir>` when notarization/store credentials are available
- [ ] `kotoba shell coverage --json --evidence <coverage-evidence.json>`
- [ ] Review `kotoba-shell-evidence-profile.json`
- [ ] `kotoba shell evidence-check <evidence-dir> --profile-file <release-dir>/kotoba-shell-evidence-profile.json --profile release --evidence <summary.json>`
- [ ] `kotoba shell updater-finalize --target {target_name} <release-dir>/kotoba-shell-updater-manifest.json --artifact <artifact> --url <url> --signature-file <signature>`
- [ ] `kotoba shell updater-check --target {target_name} <release-dir>/kotoba-shell-updater-manifest.json`
- [ ] Review `kotoba-shell-release.json`
- [ ] Review `kotoba-shell-permissions.json`
- [ ] Review `aiueos-shell-surface.json`
- [ ] Confirm safe-clj component policies are minimal and accepted
- [ ] Confirm store permission disclosures match native capabilities

## Target capabilities

{caps}

## Remaining manual gates

- Passing SDK compiler/device build
- Production signing identity
- Store submission account credentials
- Notarization or store review upload
- Updater channel URL and signature material
"#,
        name = plan.app_name,
        target_name = target_name,
        caps = caps
            .iter()
            .map(|c| format!("- `{c}`"))
            .collect::<Vec<_>>()
            .join("\n")
    )
}

fn aiueos_portable_plan_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let target_triple = match target {
        Target::Macos => "aarch64-apple-darwin",
        Target::Windows => "x86_64-pc-windows-msvc",
        Target::Ios | Target::Android => "unsupported-mobile-target",
    };
    let archive_ext = match target {
        Target::Windows => "zip",
        _ => "zip",
    };
    let manifest = serde_json::json!({
        "schema": "aiueos.portable-plan.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "targetTriple": target_triple,
        "source": {
            "env": "AIUEOS_DIR",
            "defaultRelativeToKotoba": "../aiueos"
        },
        "flavors": {
            "core": {
                "cargoArgs": ["build", "--release", "--locked", "--no-default-features"],
                "purpose": "verify/inspect/check/audit without embedded wasm-runtime",
                "archive": format!("{}-aiueos-core-{target}.{}", safe_path_segment(&plan.app_name), archive_ext, target = target.as_str())
            },
            "runner": {
                "cargoArgs": ["build", "--release", "--locked"],
                "purpose": "run/up Wasm components with embedded wasm-runtime; no global wasmtime or Node install",
                "archive": format!("{}-aiueos-runner-{target}.{}", safe_path_segment(&plan.app_name), archive_ext, target = target.as_str())
            }
        },
        "security": match target {
            Target::Macos => serde_json::json!({
                "required": ["codesign", "notarytool", "stapler"],
                "gate": "Developer ID signing + notarization + staple"
            }),
            Target::Windows => serde_json::json!({
                "required": ["Authenticode signature", "timestamp", "stable HTTPS download URL"],
                "gate": "SmartScreen reputation evidence"
            }),
            Target::Ios | Target::Android => serde_json::json!({
                "required": [],
                "gate": "not generated for mobile targets"
            }),
        }
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn aiueos_portable_build_script(plan: &ShellPlan, target: Target, runner: bool) -> String {
    let target_triple = match target {
        Target::Macos => "aarch64-apple-darwin",
        Target::Windows => "x86_64-pc-windows-msvc",
        Target::Ios | Target::Android => "unsupported-mobile-target",
    };
    let flavor = if runner { "runner" } else { "core" };
    let feature_args = if runner {
        "[]"
    } else {
        "[\"--no-default-features\"]"
    };
    let exe = if target == Target::Windows {
        "aiueos.exe"
    } else {
        "aiueos"
    };
    let template = r##"#!/usr/bin/env bb
(require '[babashka.fs :as fs]
         '[babashka.process :refer [shell]]
         '[clojure.java.io :as io]
         '[clojure.string :as str])

(def target-default "__TARGET_TRIPLE__")
(def flavor "__FLAVOR__")
(def app "__APP__")
(def exe "__EXE__")
(def feature-args __FEATURE_ARGS__)

(defn env [k default]
  (let [v (System/getenv k)]
    (if (str/blank? v) default v)))

(def script-dir (fs/parent (fs/absolutize *file*)))
(def git-root
  (let [result (shell {:out :string :err :string :continue true}
                      "git" "-C" (str script-dir) "rev-parse" "--show-toplevel")]
    (when (zero? (:exit result))
      (str/trim (:out result)))))
(def kotoba-dir (env "KOTOBA_DIR" (or git-root (str (fs/absolutize ".")))))
(def aiueos-dir (fs/path (env "AIUEOS_DIR" (str (fs/path kotoba-dir ".." "aiueos")))))
(def target (env "AIUEOS_TARGET" target-default))
(def out-root (fs/path (env "KOTOBA_AIUEOS_DIST" "target/kotoba-shell/aiueos-portable")))

(when-not (fs/regular-file? (fs/path aiueos-dir "Cargo.toml"))
  (binding [*out* *err*]
    (println "AIUEOS_DIR does not point to an aiueos checkout:" (str aiueos-dir)))
  (System/exit 2))

(apply shell {:dir (str aiueos-dir)}
       (concat ["cargo" "build" "--release" "--locked" "--target" target] feature-args))

(def dist (fs/path out-root (str app "-aiueos-" flavor "-" target)))
(when (fs/exists? dist)
  (fs/delete-tree dist))
(fs/create-dirs (fs/path dist "bin"))
(fs/create-dirs (fs/path dist "app"))
(fs/create-dirs (fs/path dist "state"))
(fs/copy (fs/path aiueos-dir "target" target "release" exe)
         (fs/path dist "bin" exe)
         {:replace-existing true})

(spit (str (fs/path dist "README.md"))
      (str "# " app " aiueos " flavor "\n\n"
           "Target: " target "\n"
           "Flavor: " flavor "\n\n"
           "core: verify/inspect/check/audit without embedded wasm-runtime.\n"
           "runner: run/up Wasm components with embedded wasm-runtime.\n"))

(def archive-name (str app "-aiueos-" flavor "-" target ".zip"))
(fs/create-dirs out-root)
(shell {:dir (str out-root)} "zip" "-qr" archive-name (fs/file-name dist))
(println (str (fs/path out-root archive-name)))
"##;
    template
        .replace("__TARGET_TRIPLE__", target_triple)
        .replace("__FLAVOR__", flavor)
        .replace("__APP__", &safe_path_segment(&plan.app_name))
        .replace("__FEATURE_ARGS__", feature_args)
        .replace("__EXE__", exe)
}

fn updater_manifest_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.updater.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "version": "0.1.0",
        "channel": "dev",
        "artifact": {
            "fileName": match target {
                Target::Macos => format!("{}.zip", safe_path_segment(&plan.app_name)),
                Target::Ios => format!("{}.ipa", safe_path_segment(&plan.app_name)),
                Target::Android => format!("{}.aab", safe_path_segment(&plan.app_name)),
                Target::Windows => format!("{}.zip", safe_path_segment(&plan.app_name)),
            },
            "sha256": serde_json::Value::Null,
            "signature": serde_json::Value::Null,
            "url": serde_json::Value::Null,
        },
        "requirements": {
            "verifyBeforeInstall": true,
            "aiueosSurfaceContract": "aiueos-shell-surface.json",
            "permissionsContract": "kotoba-shell-permissions.json"
        }
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn apple_store_metadata_json(plan: &ShellPlan, target: Target) -> Result<String> {
    let caps = target_capabilities(plan, target);
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.apple-store.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": target.as_str(),
        "bundleId": plan.app_id,
        "version": "0.1.0",
        "reviewNotes": {
            "capabilityModel": "kotoba-shell capabilities are declared in app.kotoba.edn and exported in kotoba-shell-permissions.json",
            "aiueosSurface": "aiueos-shell-surface.json",
            "safeCljAdmission": "safe components are admitted before packaging"
        },
        "privacy": {
            "usesNetwork": caps.iter().any(|c| is_network_capability(c)),
            "usesClipboard": caps.iter().any(|c| is_clipboard_capability(c)),
            "usesContacts": caps.iter().any(|c| is_contacts_capability(c)),
            "usesCalendar": caps.iter().any(|c| is_calendar_capability(c)),
            "usesNotifications": caps.iter().any(|c| c == "notify/show"),
            "usesKeychain": caps.iter().any(|c| is_keychain_capability(c))
        }
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn ios_export_options_plist() -> &'static str {
    r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>development</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>stripSwiftSymbols</key>
  <true/>
</dict>
</plist>
"#
}

fn android_data_safety_json(plan: &ShellPlan) -> Result<String> {
    let caps = target_capabilities(plan, Target::Android);
    let manifest = serde_json::json!({
        "schema": "kotoba-shell.play-store-data-safety.v0",
        "appId": plan.app_id,
        "appName": plan.app_name,
        "target": "android",
        "permissions": android_permission_lines(&caps)
            .lines()
            .filter_map(|line| line.split('"').nth(1).map(str::to_string))
            .collect::<Vec<_>>(),
        "dataTypes": {
            "contacts": caps.iter().any(|c| is_contacts_capability(c)),
            "calendar": caps.iter().any(|c| is_calendar_capability(c)),
            "clipboard": caps.iter().any(|c| is_clipboard_capability(c)),
            "network": caps.iter().any(|c| is_network_capability(c)),
            "notifications": caps.iter().any(|c| c == "notify/show"),
            "localSecrets": caps.iter().any(|c| is_keychain_capability(c))
        },
        "disclosures": {
            "dataSharedWithThirdParties": false,
            "dataEncryptedInTransit": caps.iter().any(|c| is_network_capability(c)),
            "userCanRequestDeletion": true,
            "aiueosSurface": "aiueos-shell-surface.json"
        }
    });
    serde_json::to_string_pretty(&manifest).map_err(Into::into)
}

fn android_store_review(plan: &ShellPlan) -> String {
    let caps = target_capabilities(plan, Target::Android);
    let permissions = android_permissions_xml(plan);
    format!(
        r#"# {name} Android Store Review

Generated from `app.kotoba.edn`.

Capabilities:
{caps}

Android permission manifest:

```xml
{permissions}```
"#,
        name = plan.app_name,
        caps = caps
            .iter()
            .map(|c| format!("- `{c}`"))
            .collect::<Vec<_>>()
            .join("\n"),
        permissions = permissions
    )
}

fn target_capabilities(plan: &ShellPlan, target: Target) -> Vec<String> {
    plan.capability_platforms
        .iter()
        .filter_map(|(name, platforms)| {
            if platforms.is_empty() || platforms.contains(&target) {
                Some(name.clone())
            } else {
                None
            }
        })
        .collect()
}

fn capability_metadata_edn(plan: &ShellPlan, target: Target) -> String {
    let caps = target_capabilities(plan, target)
        .into_iter()
        .map(|c| format!(":{}", c))
        .collect::<Vec<_>>()
        .join(" ");
    let components = plan
        .components
        .iter()
        .map(|c| {
            format!(
                "{{:id :{} :safe {} :status :{} :source {:?}}}",
                c.id,
                c.safe,
                match c.status {
                    ComponentStatus::Admitted => "admitted",
                    ComponentStatus::DeclaredOnly => "declared-only",
                },
                c.source.display().to_string()
            )
        })
        .collect::<Vec<_>>()
        .join("\n              ");
    format!(
        "{{:schema :kotoba-shell/permissions.v0\n :app/id {:?}\n :app/name {:?}\n :target :{}\n :capabilities #{{{}}}\n :components [{}]}}\n",
        plan.app_id,
        plan.app_name,
        target.as_str(),
        caps,
        components
    )
}

fn info_plist(plan: &ShellPlan, executable: &Path) -> String {
    let exec_name = executable
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("kotoba-shell");
    let caps = target_capabilities(plan, Target::Macos);
    let contacts_usage = if caps.iter().any(|c| is_contacts_capability(c)) {
        "  <key>NSContactsUsageDescription</key>\n  <string>This app uses contacts only when granted by the kotoba-shell capability manifest.</string>\n"
    } else {
        ""
    };
    let calendar_usage = if caps.iter().any(|c| is_calendar_capability(c)) {
        "  <key>NSCalendarsUsageDescription</key>\n  <string>This app uses calendar data only when granted by the kotoba-shell capability manifest.</string>\n"
    } else {
        ""
    };
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>{exec}</string>
  <key>CFBundleIdentifier</key>
  <string>{id}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>{name}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
{contacts_usage}{calendar_usage}
</dict>
</plist>
"#,
        exec = html_escape(exec_name),
        id = html_escape(&plan.app_id),
        name = html_escape(&plan.app_name),
        contacts_usage = contacts_usage,
        calendar_usage = calendar_usage
    )
}

fn ios_info_plist(plan: &ShellPlan) -> String {
    let caps = target_capabilities(plan, Target::Ios);
    let contacts_usage = if caps.iter().any(|c| is_contacts_capability(c)) {
        "  <key>NSContactsUsageDescription</key>\n  <string>This app uses contacts only when granted by the kotoba-shell capability manifest.</string>\n"
    } else {
        ""
    };
    let calendar_usage = if caps.iter().any(|c| is_calendar_capability(c)) {
        "  <key>NSCalendarsUsageDescription</key>\n  <string>This app uses calendar data only when granted by the kotoba-shell capability manifest.</string>\n"
    } else {
        ""
    };
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$(EXECUTABLE_NAME)</string>
  <key>CFBundleIdentifier</key>
  <string>{id}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>{name}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
{contacts_usage}{calendar_usage}
</dict>
</plist>
"#,
        id = html_escape(&plan.app_id),
        name = html_escape(&plan.app_name),
        contacts_usage = contacts_usage,
        calendar_usage = calendar_usage
    )
}

fn ios_xcode_project(plan: &ShellPlan) -> String {
    let target_name = pbx_string(&safe_path_segment(&plan.app_name));
    let product_name = pbx_string(&safe_path_segment(&plan.app_name));
    let bundle_id = pbx_string(&plan.app_id);
    format!(
        r#"// !$*UTF8*$!
{{
	archiveVersion = 1;
	classes = {{}};
	objectVersion = 56;
	objects = {{

/* Begin PBXBuildFile section */
		000000000000000000000101 /* KotobaShellApp.swift in Sources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000201 /* KotobaShellApp.swift */; }};
		000000000000000000000102 /* index.html in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000202 /* index.html */; }};
		000000000000000000000104 /* app in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000204 /* app */; }};
		000000000000000000000105 /* kotoba-shell-release.json in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000205 /* kotoba-shell-release.json */; }};
		000000000000000000000106 /* kotoba-shell-permissions.json in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000206 /* kotoba-shell-permissions.json */; }};
		000000000000000000000107 /* kotoba-shell-capabilities.edn in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000207 /* kotoba-shell-capabilities.edn */; }};
		000000000000000000000108 /* aiueos-shell-surface.json in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000208 /* aiueos-shell-surface.json */; }};
		000000000000000000000109 /* aiueos-shell-surface.edn in Resources */ = {{isa = PBXBuildFile; fileRef = 000000000000000000000209 /* aiueos-shell-surface.edn */; }};
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		000000000000000000000201 /* KotobaShellApp.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = KotobaShellApp.swift; sourceTree = "<group>"; }};
		000000000000000000000202 /* index.html */ = {{isa = PBXFileReference; lastKnownFileType = text.html; path = index.html; sourceTree = "<group>"; }};
		000000000000000000000204 /* app */ = {{isa = PBXFileReference; lastKnownFileType = folder; path = app; sourceTree = "<group>"; }};
		000000000000000000000205 /* kotoba-shell-release.json */ = {{isa = PBXFileReference; lastKnownFileType = text.json; path = "kotoba-shell-release.json"; sourceTree = "<group>"; }};
		000000000000000000000206 /* kotoba-shell-permissions.json */ = {{isa = PBXFileReference; lastKnownFileType = text.json; path = "kotoba-shell-permissions.json"; sourceTree = "<group>"; }};
		000000000000000000000207 /* kotoba-shell-capabilities.edn */ = {{isa = PBXFileReference; lastKnownFileType = text; path = "kotoba-shell-capabilities.edn"; sourceTree = "<group>"; }};
		000000000000000000000208 /* aiueos-shell-surface.json */ = {{isa = PBXFileReference; lastKnownFileType = text.json; path = "aiueos-shell-surface.json"; sourceTree = "<group>"; }};
		000000000000000000000209 /* aiueos-shell-surface.edn */ = {{isa = PBXFileReference; lastKnownFileType = text; path = "aiueos-shell-surface.edn"; sourceTree = "<group>"; }};
		000000000000000000000301 /* {product_name}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = "{product_name}.app"; sourceTree = BUILT_PRODUCTS_DIR; }};
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		000000000000000000000401 /* Frameworks */ = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
		000000000000000000000501 = {{
			isa = PBXGroup;
			children = (
				000000000000000000000502 /* Sources */,
				000000000000000000000503 /* Resources */,
				000000000000000000000504 /* Products */,
			);
			sourceTree = "<group>";
		}};
		000000000000000000000502 /* Sources */ = {{
			isa = PBXGroup;
			children = (000000000000000000000201 /* KotobaShellApp.swift */);
			path = Sources;
			sourceTree = "<group>";
		}};
		000000000000000000000503 /* Resources */ = {{
			isa = PBXGroup;
			children = (
				000000000000000000000202 /* index.html */,
				000000000000000000000204 /* app */,
				000000000000000000000205 /* kotoba-shell-release.json */,
				000000000000000000000206 /* kotoba-shell-permissions.json */,
				000000000000000000000207 /* kotoba-shell-capabilities.edn */,
				000000000000000000000208 /* aiueos-shell-surface.json */,
				000000000000000000000209 /* aiueos-shell-surface.edn */,
			);
			path = Resources;
			sourceTree = "<group>";
		}};
		000000000000000000000504 /* Products */ = {{
			isa = PBXGroup;
			children = (000000000000000000000301 /* {product_name}.app */);
			name = Products;
			sourceTree = "<group>";
		}};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		000000000000000000000601 /* {target_name} */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = 000000000000000000000901 /* Build configuration list for PBXNativeTarget "{target_name}" */;
			buildPhases = (
				000000000000000000000701 /* Sources */,
				000000000000000000000401 /* Frameworks */,
				000000000000000000000801 /* Resources */,
			);
			buildRules = ();
			dependencies = ();
			name = "{target_name}";
			productName = "{product_name}";
			productReference = 000000000000000000000301 /* {product_name}.app */;
			productType = "com.apple.product-type.application";
		}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		000000000000000000000001 /* Project object */ = {{
			isa = PBXProject;
			attributes = {{
				BuildIndependentTargetsInParallel = 1;
				LastSwiftUpdateCheck = 1600;
				LastUpgradeCheck = 1600;
				TargetAttributes = {{000000000000000000000601 = {{CreatedOnToolsVersion = 16.0; }}; }};
			}};
			buildConfigurationList = 000000000000000000000902 /* Build configuration list for PBXProject "{target_name}" */;
			compatibilityVersion = "Xcode 14.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (en, Base);
			mainGroup = 000000000000000000000501;
			productRefGroup = 000000000000000000000504 /* Products */;
			projectDirPath = "";
			projectRoot = "";
			targets = (000000000000000000000601 /* {target_name} */);
		}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		000000000000000000000801 /* Resources */ = {{
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				000000000000000000000102 /* index.html in Resources */,
				000000000000000000000104 /* app in Resources */,
				000000000000000000000105 /* kotoba-shell-release.json in Resources */,
				000000000000000000000106 /* kotoba-shell-permissions.json in Resources */,
				000000000000000000000107 /* kotoba-shell-capabilities.edn in Resources */,
				000000000000000000000108 /* aiueos-shell-surface.json in Resources */,
				000000000000000000000109 /* aiueos-shell-surface.edn in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		000000000000000000000701 /* Sources */ = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (000000000000000000000101 /* KotobaShellApp.swift in Sources */);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		000000000000000000001001 /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
				CODE_SIGNING_ALLOWED = NO;
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = dwarf;
				DEVELOPMENT_TEAM = "";
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				GCC_C_LANGUAGE_STANDARD = gnu17;
				GCC_DYNAMIC_NO_PIC = NO;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_OPTIMIZATION_LEVEL = 0;
				GCC_PREPROCESSOR_DEFINITIONS = ("DEBUG=1", "$(inherited)");
				IPHONEOS_DEPLOYMENT_TARGET = 15.0;
				MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
				ONLY_ACTIVE_ARCH = YES;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SDKROOT = iphoneos;
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
				SWIFT_VERSION = 5.0;
			}};
			name = Debug;
		}};
		000000000000000000001002 /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				CODE_SIGNING_ALLOWED = NO;
				COPY_PHASE_STRIP = NO;
				IPHONEOS_DEPLOYMENT_TARGET = 15.0;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SDKROOT = iphoneos;
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SWIFT_COMPILATION_MODE = wholemodule;
				SWIFT_OPTIMIZATION_LEVEL = "-O";
				SWIFT_VERSION = 5.0;
			}};
			name = Release;
		}};
		000000000000000000001101 /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = "";
				CODE_SIGN_STYLE = Automatic;
				CODE_SIGNING_ALLOWED = NO;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = Resources/Info.plist;
				IPHONEOS_DEPLOYMENT_TARGET = 15.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}";
				PRODUCT_NAME = "{product_name}";
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SWIFT_VERSION = 5.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Debug;
		}};
		000000000000000000001102 /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = "";
				CODE_SIGN_STYLE = Automatic;
				CODE_SIGNING_ALLOWED = NO;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = Resources/Info.plist;
				IPHONEOS_DEPLOYMENT_TARGET = 15.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}";
				PRODUCT_NAME = "{product_name}";
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SWIFT_VERSION = 5.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Release;
		}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		000000000000000000000902 /* Build configuration list for PBXProject "{target_name}" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (000000000000000000001001 /* Debug */, 000000000000000000001002 /* Release */);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		000000000000000000000901 /* Build configuration list for PBXNativeTarget "{target_name}" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (000000000000000000001101 /* Debug */, 000000000000000000001102 /* Release */);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
/* End XCConfigurationList section */
	}};
	rootObject = 000000000000000000000001 /* Project object */;
}}
"#,
        target_name = target_name,
        product_name = product_name,
        bundle_id = bundle_id
    )
}

fn pbx_string(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn dev_html(plan: &ShellPlan) -> String {
    shell_html(plan, None)
}

fn shell_html(plan: &ShellPlan, target: Option<Target>) -> String {
    let components = plan
        .components
        .iter()
        .map(|c| {
            let policy = c
                .policy_edn
                .as_deref()
                .map(html_escape)
                .unwrap_or_else(|| "-".to_string());
            format!(
                r#"<section class="component">
  <h2>{}</h2>
  <p><b>source</b> {}</p>
  <p><b>status</b> {:?} · <b>safe</b> {} · <b>wasm</b> {}</p>
  <p><b>capability surface</b> {}</p>
  <details><summary>minimal policy</summary><pre>{}</pre></details>
</section>"#,
                html_escape(&c.id),
                html_escape(&c.source.display().to_string()),
                c.status,
                c.safe,
                c.wasm_bytes
                    .map(|n| n.to_string())
                    .unwrap_or_else(|| "-".to_string()),
                html_escape(&if c.capability_surface.is_empty() {
                    "none".to_string()
                } else {
                    c.capability_surface.join(", ")
                }),
                policy
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    let effective_capabilities = target
        .map(|target| target_capabilities(plan, target))
        .unwrap_or_else(|| plan.native_capabilities.clone());
    let caps = if effective_capabilities.is_empty() {
        "none".to_string()
    } else {
        effective_capabilities.join(", ")
    };
    let targets = target
        .map(|target| target.as_str().to_string())
        .unwrap_or_else(|| {
            plan.targets
                .iter()
                .map(|t| t.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        });
    let fs_controls = if effective_capabilities.iter().any(|c| c == "fs/app-data") {
        r#"<section class="component">
  <h2>fs/app-data</h2>
  <p>Capability-gated text read/write inside the app data directory.</p>
  <div class="bridge">
    <button id="fs-write">Write note</button>
    <button id="fs-read">Read note</button>
    <button id="fs-append">Append note</button>
  </div>
  <pre id="fs-output">fs idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let notify_controls = if effective_capabilities.iter().any(|c| c == "notify/show") {
        r#"<section class="component">
  <h2>notify/show</h2>
  <p>Capability-gated native notification request.</p>
  <div class="bridge">
    <button id="notify-show">Show notification</button>
  </div>
  <pre id="notify-output">notify idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let clipboard_controls = if effective_capabilities
        .iter()
        .any(|c| is_clipboard_capability(c))
    {
        r#"<section class="component">
  <h2>clipboard/text</h2>
  <p>Capability-gated text clipboard read/write.</p>
  <div class="bridge">
    <button id="clipboard-write">Write clipboard</button>
    <button id="clipboard-read">Read clipboard</button>
  </div>
  <pre id="clipboard-output">clipboard idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let http_controls = if effective_capabilities
        .iter()
        .any(|c| is_http_fetch_capability(c))
    {
        r#"<section class="component">
  <h2>http/fetch</h2>
  <p>Capability-gated HTTP fetch through the native provider.</p>
  <div class="bridge">
    <button id="http-fetch">Fetch example</button>
  </div>
  <pre id="http-output">http idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let keychain_controls = if effective_capabilities
        .iter()
        .any(|c| is_keychain_capability(c))
    {
        r#"<section class="component">
  <h2>keychain/text</h2>
  <p>Capability-gated generic password read/write in the native keychain.</p>
  <div class="bridge">
    <button id="keychain-write">Write secret</button>
    <button id="keychain-read">Read secret</button>
    <button id="keychain-delete">Delete secret</button>
  </div>
  <pre id="keychain-output">keychain idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let contacts_controls = if effective_capabilities
        .iter()
        .any(|c| is_contacts_capability(c))
    {
        r#"<section class="component">
  <h2>contacts/read</h2>
  <p>Capability-gated contacts provider surface.</p>
  <div class="bridge">
    <button id="contacts-list">List contacts</button>
  </div>
  <pre id="contacts-output">contacts idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let calendar_controls = if effective_capabilities
        .iter()
        .any(|c| is_calendar_capability(c))
    {
        r#"<section class="component">
  <h2>calendar/read</h2>
  <p>Capability-gated calendar provider surface.</p>
  <div class="bridge">
    <button id="calendar-list">List events</button>
  </div>
  <pre id="calendar-output">calendar idle</pre>
</section>"#
            .to_string()
    } else {
        String::new()
    };
    let audit_controls = r#"<section class="component">
  <h2>runtime audit</h2>
  <p>Append-only JSONL of native bridge requests and results.</p>
  <div class="bridge">
    <button id="audit-read">Read audit</button>
  </div>
  <pre id="audit-output">audit idle</pre>
</section>"#;
    let ui_frame = plan
        .ui_dist
        .as_ref()
        .map(|_| {
            let index = plan.ui_index.as_deref().unwrap_or("index.html");
            format!(
                r#"<section class="component">
  <h2>packaged UI</h2>
  <p><b>dist</b> {} · <b>index</b> {}</p>
  <iframe src="app/{}" title="packaged UI"></iframe>
</section>"#,
                html_escape(&plan.ui_dist.as_ref().unwrap().display().to_string()),
                html_escape(index),
                html_escape(index)
            )
        })
        .unwrap_or_default();
    format!(
        r#"<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: Canvas; color: CanvasText; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 28px; }}
    header {{ border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent); padding-bottom: 18px; margin-bottom: 22px; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 16px; margin: 0 0 10px; letter-spacing: 0; }}
    p {{ margin: 6px 0; line-height: 1.45; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .component {{ border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 8px; padding: 14px; margin: 12px 0; }}
    iframe {{ width: 100%; min-height: 260px; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 6px; background: Canvas; }}
    .bridge {{ display: flex; gap: 8px; align-items: center; margin-top: 16px; }}
    button {{ font: inherit; padding: 7px 11px; border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); background: ButtonFace; color: ButtonText; }}
    button:disabled {{ opacity: .45; }}
    pre {{ overflow: auto; padding: 10px; border-radius: 6px; background: color-mix(in srgb, CanvasText 7%, transparent); }}
    #bridge-status {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{title}</h1>
    <p><b>app id</b> {app_id}</p>
    <p><b>ui entry</b> {ui_entry}</p>
    <p><b>targets</b> {targets}</p>
    <p><b>native capabilities</b> {caps}</p>
    <div class="bridge">
      <button id="bridge-ping">Ping native bridge</button>
      <span id="bridge-status">bridge idle</span>
    </div>
  </header>
  {components}
  {ui_frame}
  {fs_controls}
  {notify_controls}
  {clipboard_controls}
  {http_controls}
  {keychain_controls}
  {contacts_controls}
  {calendar_controls}
  {audit_controls}
</main>
<script>
var kotobaShellPending = Object.create(null);
window.kotobaShell = {{
  invoke: function(command, payload) {{
    var requestId = "req-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    var message = {{ requestId: requestId, command: command, payload: payload || null, ts: Date.now() }};
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.kotoba) {{
      window.webkit.messageHandlers.kotoba.postMessage(message);
      return new Promise(function(resolve, reject) {{
        kotobaShellPending[requestId] = {{ resolve: resolve, reject: reject }};
        setTimeout(function() {{
          if (kotobaShellPending[requestId]) {{
            delete kotobaShellPending[requestId];
            reject(new Error("kotoba-shell request timed out: " + command));
          }}
        }}, 10000);
      }});
    }}
    if (window.kotobaAndroid && window.kotobaAndroid.postMessage) {{
      window.kotobaAndroid.postMessage(JSON.stringify(message));
      return new Promise(function(resolve, reject) {{
        kotobaShellPending[requestId] = {{ resolve: resolve, reject: reject }};
        setTimeout(function() {{
          if (kotobaShellPending[requestId]) {{
            delete kotobaShellPending[requestId];
            reject(new Error("kotoba-shell request timed out: " + command));
          }}
        }}, 10000);
      }});
    }}
    console.log("kotoba-shell bridge unavailable", message);
    return Promise.reject(new Error("kotoba-shell bridge unavailable"));
  }}
}};
window.addEventListener("kotoba-shell-message", function(event) {{
  document.getElementById("bridge-status").textContent = "bridge replied: " + JSON.stringify(event.detail);
  var detail = event.detail || {{}};
  if (detail.requestId && kotobaShellPending[detail.requestId]) {{
    var pending = kotobaShellPending[detail.requestId];
    delete kotobaShellPending[detail.requestId];
    if (detail.ok) pending.resolve(detail);
    else pending.reject(new Error(detail.error || "kotoba-shell command failed"));
  }}
}});
document.getElementById("bridge-ping").addEventListener("click", function() {{
  window.kotobaShell.invoke("shell/ping", {{ app: {app_id_js} }})
    .then(function() {{ document.getElementById("bridge-status").textContent = "bridge ping ok"; }})
    .catch(function(err) {{ document.getElementById("bridge-status").textContent = err.message; }});
}});
var fsOutput = document.getElementById("fs-output");
if (fsOutput) {{
  document.getElementById("fs-write").addEventListener("click", function() {{
    window.kotobaShell.invoke("fs/write-text", {{ path: "notes/hello.txt", text: "hello from kotoba-shell\n" }})
      .then(function(res) {{ fsOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ fsOutput.textContent = err.message; }});
  }});
  document.getElementById("fs-append").addEventListener("click", function() {{
    window.kotobaShell.invoke("fs/append-text", {{ path: "notes/hello.txt", text: "appended line\n" }})
      .then(function(res) {{ fsOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ fsOutput.textContent = err.message; }});
  }});
  document.getElementById("fs-read").addEventListener("click", function() {{
    window.kotobaShell.invoke("fs/read-text", {{ path: "notes/hello.txt" }})
      .then(function(res) {{ fsOutput.textContent = res.value || ""; }})
      .catch(function(err) {{ fsOutput.textContent = err.message; }});
  }});
}}
var notifyOutput = document.getElementById("notify-output");
if (notifyOutput) {{
  document.getElementById("notify-show").addEventListener("click", function() {{
    window.kotobaShell.invoke("notify/show", {{ title: "kotoba-shell", body: "notification from native provider" }})
      .then(function(res) {{ notifyOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ notifyOutput.textContent = err.message; }});
  }});
}}
var clipboardOutput = document.getElementById("clipboard-output");
if (clipboardOutput) {{
  document.getElementById("clipboard-write").addEventListener("click", function() {{
    window.kotobaShell.invoke("clipboard/write-text", {{ text: "hello from kotoba-shell clipboard" }})
      .then(function(res) {{ clipboardOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ clipboardOutput.textContent = err.message; }});
  }});
  document.getElementById("clipboard-read").addEventListener("click", function() {{
    window.kotobaShell.invoke("clipboard/read-text", {{}})
      .then(function(res) {{ clipboardOutput.textContent = res.value || ""; }})
      .catch(function(err) {{ clipboardOutput.textContent = err.message; }});
  }});
}}
var httpOutput = document.getElementById("http-output");
if (httpOutput) {{
  document.getElementById("http-fetch").addEventListener("click", function() {{
    window.kotobaShell.invoke("http/fetch", {{ url: "https://example.com/", method: "GET" }})
      .then(function(res) {{ httpOutput.textContent = JSON.stringify(res, null, 2).slice(0, 4000); }})
      .catch(function(err) {{ httpOutput.textContent = err.message; }});
  }});
}}
var keychainOutput = document.getElementById("keychain-output");
if (keychainOutput) {{
  document.getElementById("keychain-write").addEventListener("click", function() {{
    window.kotobaShell.invoke("keychain/write-text", {{ key: "demo-token", text: "secret from kotoba-shell" }})
      .then(function(res) {{ keychainOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ keychainOutput.textContent = err.message; }});
  }});
  document.getElementById("keychain-read").addEventListener("click", function() {{
    window.kotobaShell.invoke("keychain/read-text", {{ key: "demo-token" }})
      .then(function(res) {{ keychainOutput.textContent = res.value || ""; }})
      .catch(function(err) {{ keychainOutput.textContent = err.message; }});
  }});
  document.getElementById("keychain-delete").addEventListener("click", function() {{
    window.kotobaShell.invoke("keychain/delete", {{ key: "demo-token" }})
      .then(function(res) {{ keychainOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ keychainOutput.textContent = err.message; }});
  }});
}}
var contactsOutput = document.getElementById("contacts-output");
if (contactsOutput) {{
  document.getElementById("contacts-list").addEventListener("click", function() {{
    window.kotobaShell.invoke("contacts/list", {{ limit: 20 }})
      .then(function(res) {{ contactsOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ contactsOutput.textContent = err.message; }});
  }});
}}
var calendarOutput = document.getElementById("calendar-output");
if (calendarOutput) {{
  document.getElementById("calendar-list").addEventListener("click", function() {{
    window.kotobaShell.invoke("calendar/list-events", {{ limit: 20 }})
      .then(function(res) {{ calendarOutput.textContent = JSON.stringify(res, null, 2); }})
      .catch(function(err) {{ calendarOutput.textContent = err.message; }});
  }});
}}
var auditOutput = document.getElementById("audit-output");
document.getElementById("audit-read").addEventListener("click", function() {{
  window.kotobaShell.invoke("audit/read", {{ limit: 20 }})
    .then(function(res) {{ auditOutput.textContent = res.value || ""; }})
    .catch(function(err) {{ auditOutput.textContent = err.message; }});
}});
</script>
</body>
</html>
"#,
        title = html_escape(&plan.app_name),
        app_id = html_escape(&plan.app_id),
        app_id_js = js_string(&plan.app_id),
        ui_entry = html_escape(plan.ui_entry.as_deref().unwrap_or("-")),
        targets = html_escape(&targets),
        caps = html_escape(&caps),
        components = components,
        ui_frame = ui_frame,
        fs_controls = fs_controls,
        notify_controls = notify_controls,
        clipboard_controls = clipboard_controls,
        http_controls = http_controls,
        keychain_controls = keychain_controls,
        contacts_controls = contacts_controls,
        calendar_controls = calendar_controls,
        audit_controls = audit_controls
    )
}

fn macos_swift_runner(plan: &ShellPlan) -> String {
    let app_id = swift_string(&plan.app_id);
    let allow_fs = plan.native_capabilities.iter().any(|c| c == "fs/app-data");
    let allow_notify = plan.native_capabilities.iter().any(|c| c == "notify/show");
    let allow_clipboard = plan
        .native_capabilities
        .iter()
        .any(|c| is_clipboard_capability(c));
    let allow_http_fetch = plan
        .native_capabilities
        .iter()
        .any(|c| is_http_fetch_capability(c));
    let allow_keychain = plan
        .native_capabilities
        .iter()
        .any(|c| is_keychain_capability(c));
    let allow_contacts = plan
        .native_capabilities
        .iter()
        .any(|c| is_contacts_capability(c));
    let allow_calendar = plan
        .native_capabilities
        .iter()
        .any(|c| is_calendar_capability(c));
    let template = r#"import Cocoa
import WebKit
import Foundation
import UserNotifications
import Security
import Contacts
import EventKit

final class Bridge: NSObject, WKScriptMessageHandler {
  weak var webView: WKWebView?
  let appId: String
  let allowFsAppData: Bool
  let allowNotifyShow: Bool
  let allowClipboard: Bool
  let allowHttpFetch: Bool
  let allowKeychain: Bool
  let allowContacts: Bool
  let allowCalendar: Bool
  let appDataRoot: URL
  let auditPath: URL

  init(appId: String, allowFsAppData: Bool, allowNotifyShow: Bool, allowClipboard: Bool, allowHttpFetch: Bool, allowKeychain: Bool, allowContacts: Bool, allowCalendar: Bool) {
    self.appId = appId
    self.allowFsAppData = allowFsAppData
    self.allowNotifyShow = allowNotifyShow
    self.allowClipboard = allowClipboard
    self.allowHttpFetch = allowHttpFetch
    self.allowKeychain = allowKeychain
    self.allowContacts = allowContacts
    self.allowCalendar = allowCalendar
    let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
    self.appDataRoot = support.appendingPathComponent("kotoba-shell-dev", isDirectory: true).appendingPathComponent(appId, isDirectory: true)
    self.auditPath = self.appDataRoot.appendingPathComponent("audit", isDirectory: true).appendingPathComponent("commands.jsonl", isDirectory: false)
    try? FileManager.default.createDirectory(at: self.appDataRoot, withIntermediateDirectories: true)
    try? FileManager.default.createDirectory(at: self.auditPath.deletingLastPathComponent(), withIntermediateDirectories: true)
    super.init()
  }

  func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
    print("[kotoba-shell] bridge message: \(message.body)")
    guard let msg = message.body as? [String: Any] else {
      reply(requestId: nil, command: "unknown", ok: false, value: nil, error: "message must be an object")
      return
    }
    let requestId = msg["requestId"] as? String
    let command = msg["command"] as? String ?? "unknown"
    let payload = msg["payload"] as? [String: Any] ?? [:]
    appendAudit(command: command, requestId: requestId, ok: true, phase: "request", value: sanitizeForAudit(payload), error: nil)

    do {
      switch command {
      case "shell/ping":
        reply(requestId: requestId, command: command, ok: true, value: ["app": appId, "appDataRoot": appDataRoot.path], error: nil)
      case "audit/read":
        let limit = payload["limit"] as? Int ?? 50
        let text = readAudit(limit: max(1, min(limit, 200)))
        reply(requestId: requestId, command: command, ok: true, value: text, error: nil)
      case "fs/read-text":
        try requireFs()
        let path = try resolveAppDataPath(payload)
        let text = try String(contentsOf: path, encoding: .utf8)
        reply(requestId: requestId, command: command, ok: true, value: text, error: nil)
      case "fs/write-text":
        try requireFs()
        let path = try resolveAppDataPath(payload)
        let text = payload["text"] as? String ?? ""
        try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
        try text.write(to: path, atomically: true, encoding: .utf8)
        reply(requestId: requestId, command: command, ok: true, value: ["path": path.path, "bytes": text.utf8.count], error: nil)
      case "fs/append-text":
        try requireFs()
        let path = try resolveAppDataPath(payload)
        let text = payload["text"] as? String ?? ""
        try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
        if FileManager.default.fileExists(atPath: path.path) {
          let handle = try FileHandle(forWritingTo: path)
          try handle.seekToEnd()
          try handle.write(contentsOf: Data(text.utf8))
          try handle.close()
        } else {
          try text.write(to: path, atomically: true, encoding: .utf8)
        }
        reply(requestId: requestId, command: command, ok: true, value: ["path": path.path, "bytes": text.utf8.count], error: nil)
      case "notify/show":
        try requireNotify()
        let title = payload["title"] as? String ?? appId
        let body = payload["body"] as? String ?? ""
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        let notificationId = "kotoba-shell-\(UUID().uuidString)"
        let request = UNNotificationRequest(identifier: notificationId, content: content, trigger: nil)
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { granted, authError in
          if let authError = authError {
            self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(authError)")
            return
          }
          if !granted {
            self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "notification authorization was not granted")
            return
          }
          UNUserNotificationCenter.current().add(request) { addError in
            if let addError = addError {
              self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(addError)")
            } else {
              self.reply(requestId: requestId, command: command, ok: true, value: ["delivered": true, "title": title], error: nil)
            }
          }
        }
      case "clipboard/read-text":
        try requireClipboard()
        let text = NSPasteboard.general.string(forType: .string) ?? ""
        reply(requestId: requestId, command: command, ok: true, value: text, error: nil)
      case "clipboard/write-text":
        try requireClipboard()
        let text = payload["text"] as? String ?? ""
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        reply(requestId: requestId, command: command, ok: true, value: ["bytes": text.utf8.count], error: nil)
      case "http/fetch":
        try requireHttpFetch()
        let url = try resolveHttpUrl(payload)
        let method = (payload["method"] as? String ?? "GET").uppercased()
        if !["GET", "POST", "PUT", "PATCH", "DELETE"].contains(method) {
          throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "unsupported HTTP method: \(method)"])
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let headers = payload["headers"] as? [String: String] {
          for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
          }
        }
        if let body = payload["body"] as? String {
          request.httpBody = Data(body.utf8)
        }
        URLSession.shared.dataTask(with: request) { data, response, err in
          if let err = err {
            self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(err)")
            return
          }
          let status = (response as? HTTPURLResponse)?.statusCode ?? 0
          let text = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
          self.reply(requestId: requestId, command: command, ok: true, value: ["status": status, "body": String(text.prefix(32768))], error: nil)
        }.resume()
      case "keychain/read-text":
        try requireKeychain()
        let key = try keychainKey(payload)
        let text = try keychainRead(key)
        reply(requestId: requestId, command: command, ok: true, value: text, error: nil)
      case "keychain/write-text":
        try requireKeychain()
        let key = try keychainKey(payload)
        let text = payload["text"] as? String ?? ""
        try keychainWrite(key, text: text)
        reply(requestId: requestId, command: command, ok: true, value: ["key": key, "bytes": text.utf8.count], error: nil)
      case "keychain/delete":
        try requireKeychain()
        let key = try keychainKey(payload)
        keychainDelete(key)
        reply(requestId: requestId, command: command, ok: true, value: ["key": key, "deleted": true], error: nil)
      case "contacts/list":
        try requireContacts()
        listContacts(payload: payload, requestId: requestId, command: command)
      case "calendar/list-events":
        try requireCalendar()
        listCalendarEvents(payload: payload, requestId: requestId, command: command)
      default:
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "unknown command: \(command)")
      }
    } catch {
      reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
    }
  }

  func requireFs() throws {
    if !allowFsAppData {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "fs/app-data capability is not granted"])
    }
  }

  func requireNotify() throws {
    if !allowNotifyShow {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "notify/show capability is not granted"])
    }
  }

  func requireClipboard() throws {
    if !allowClipboard {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "clipboard capability is not granted"])
    }
  }

  func requireHttpFetch() throws {
    if !allowHttpFetch {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "http/fetch capability is not granted"])
    }
  }

  func requireKeychain() throws {
    if !allowKeychain {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "keychain capability is not granted"])
    }
  }

  func requireContacts() throws {
    if !allowContacts {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "contacts capability is not granted"])
    }
  }

  func requireCalendar() throws {
    if !allowCalendar {
      throw NSError(domain: "kotoba-shell", code: 403, userInfo: [NSLocalizedDescriptionKey: "calendar capability is not granted"])
    }
  }

  func keychainKey(_ payload: [String: Any]) throws -> String {
    guard let key = payload["key"] as? String, !key.isEmpty, !key.contains("/") && !key.contains("\\") else {
      throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "payload.key is required and must be a simple key"])
    }
    return key
  }

  func keychainQuery(_ key: String) -> [String: Any] {
    [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrService as String: appId,
      kSecAttrAccount as String: key
    ]
  }

  func keychainRead(_ key: String) throws -> String {
    var query = keychainQuery(key)
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)
    if status == errSecItemNotFound {
      throw NSError(domain: "kotoba-shell", code: 404, userInfo: [NSLocalizedDescriptionKey: "keychain item not found"])
    }
    if status != errSecSuccess {
      throw NSError(domain: "kotoba-shell", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "keychain read failed: \(status)"])
    }
    guard let data = item as? Data, let text = String(data: data, encoding: .utf8) else {
      throw NSError(domain: "kotoba-shell", code: 500, userInfo: [NSLocalizedDescriptionKey: "keychain item is not utf8 text"])
    }
    return text
  }

  func keychainWrite(_ key: String, text: String) throws {
    let data = Data(text.utf8)
    var query = keychainQuery(key)
    let update: [String: Any] = [kSecValueData as String: data]
    let updateStatus = SecItemUpdate(query as CFDictionary, update as CFDictionary)
    if updateStatus == errSecSuccess {
      return
    }
    if updateStatus != errSecItemNotFound {
      throw NSError(domain: "kotoba-shell", code: Int(updateStatus), userInfo: [NSLocalizedDescriptionKey: "keychain update failed: \(updateStatus)"])
    }
    query[kSecValueData as String] = data
    let addStatus = SecItemAdd(query as CFDictionary, nil)
    if addStatus != errSecSuccess {
      throw NSError(domain: "kotoba-shell", code: Int(addStatus), userInfo: [NSLocalizedDescriptionKey: "keychain add failed: \(addStatus)"])
    }
  }

  func keychainDelete(_ key: String) {
    SecItemDelete(keychainQuery(key) as CFDictionary)
  }

  func listContacts(payload: [String: Any], requestId: String?, command: String) {
    let limit = max(1, min(payload["limit"] as? Int ?? 50, 200))
    let store = CNContactStore()
    store.requestAccess(for: .contacts) { granted, accessError in
      if let accessError = accessError {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(accessError)")
        return
      }
      if !granted {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "contacts authorization was not granted")
        return
      }
      let keys: [CNKeyDescriptor] = [
        CNContactIdentifierKey as CNKeyDescriptor,
        CNContactGivenNameKey as CNKeyDescriptor,
        CNContactFamilyNameKey as CNKeyDescriptor,
        CNContactOrganizationNameKey as CNKeyDescriptor,
        CNContactEmailAddressesKey as CNKeyDescriptor,
        CNContactPhoneNumbersKey as CNKeyDescriptor
      ]
      let request = CNContactFetchRequest(keysToFetch: keys)
      request.sortOrder = .userDefault
      var contacts: [[String: Any]] = []
      do {
        try store.enumerateContacts(with: request) { contact, stop in
          var row: [String: Any] = [
            "id": contact.identifier,
            "givenName": contact.givenName,
            "familyName": contact.familyName,
            "organizationName": contact.organizationName
          ]
          let displayName = [contact.givenName, contact.familyName].filter { !$0.isEmpty }.joined(separator: " ")
          row["displayName"] = displayName.isEmpty ? contact.organizationName : displayName
          row["emails"] = contact.emailAddresses.map { $0.value as String }
          row["phones"] = contact.phoneNumbers.map { $0.value.stringValue }
          contacts.append(row)
          if contacts.count >= limit {
            stop.pointee = true
          }
        }
        self.reply(requestId: requestId, command: command, ok: true, value: ["contacts": contacts, "count": contacts.count], error: nil)
      } catch {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
      }
    }
  }

  func listCalendarEvents(payload: [String: Any], requestId: String?, command: String) {
    let store = EKEventStore()
    let finish: (Bool, Error?) -> Void = { granted, accessError in
      if let accessError = accessError {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(accessError)")
        return
      }
      if !granted {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "calendar authorization was not granted")
        return
      }
      self.fetchCalendarEvents(store: store, payload: payload, requestId: requestId, command: command)
    }
    if #available(macOS 14.0, *) {
      store.requestFullAccessToEvents(completion: finish)
    } else {
      store.requestAccess(to: .event, completion: finish)
    }
  }

  func fetchCalendarEvents(store: EKEventStore, payload: [String: Any], requestId: String?, command: String) {
    let limit = max(1, min(payload["limit"] as? Int ?? 50, 200))
    let days = max(1, min(payload["days"] as? Int ?? 30, 366))
    let start = Date()
    let end = Calendar.current.date(byAdding: .day, value: days, to: start) ?? start
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let formatter = ISO8601DateFormatter()
    let events = store.events(matching: predicate)
      .sorted { $0.startDate < $1.startDate }
      .prefix(limit)
      .map { event -> [String: Any] in
        var row: [String: Any] = [
          "id": event.eventIdentifier ?? "",
          "title": event.title ?? "",
          "start": formatter.string(from: event.startDate),
          "end": formatter.string(from: event.endDate),
          "calendar": event.calendar.title,
          "isAllDay": event.isAllDay
        ]
        if let location = event.location, !location.isEmpty {
          row["location"] = location
        }
        return row
      }
    reply(requestId: requestId, command: command, ok: true, value: ["events": Array(events), "count": events.count, "days": days], error: nil)
  }

  func resolveHttpUrl(_ payload: [String: Any]) throws -> URL {
    guard let raw = payload["url"] as? String, let url = URL(string: raw), let scheme = url.scheme?.lowercased(), scheme == "https" || scheme == "http" else {
      throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "payload.url must be an http or https URL"])
    }
    return url
  }

  func resolveAppDataPath(_ payload: [String: Any]) throws -> URL {
    guard let rel = payload["path"] as? String, !rel.isEmpty else {
      throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "payload.path is required"])
    }
    if rel.hasPrefix("/") || rel.contains("..") || rel.contains("\\") {
      throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "path must be relative and stay inside app data"])
    }
    return appDataRoot.appendingPathComponent(rel, isDirectory: false)
  }

  func reply(requestId: String?, command: String, ok: Bool, value: Any?, error: String?) {
    appendAudit(command: command, requestId: requestId, ok: ok, phase: "reply", value: sanitizeForAudit(value), error: error)
    var detail: [String: Any] = ["command": command, "ok": ok]
    if let requestId = requestId { detail["requestId"] = requestId }
    if let value = value { detail["value"] = value }
    if let error = error { detail["error"] = error }
    let data = try! JSONSerialization.data(withJSONObject: detail)
    let json = String(data: data, encoding: .utf8)!
    DispatchQueue.main.async {
      self.webView?.evaluateJavaScript("window.dispatchEvent(new CustomEvent('kotoba-shell-message', { detail: \(json) }));", completionHandler: nil)
    }
  }

  func appendAudit(command: String, requestId: String?, ok: Bool, phase: String, value: Any?, error: String?) {
    var entry: [String: Any] = [
      "ts": isoNow(),
      "app": appId,
      "command": command,
      "ok": ok,
      "phase": phase
    ]
    if let requestId = requestId { entry["requestId"] = requestId }
    if let value = value { entry["value"] = value }
    if let error = error { entry["error"] = error }
    guard JSONSerialization.isValidJSONObject(entry),
          let data = try? JSONSerialization.data(withJSONObject: entry),
          let line = String(data: data, encoding: .utf8) else {
      return
    }
    if FileManager.default.fileExists(atPath: auditPath.path) {
      do {
        let handle = try FileHandle(forWritingTo: auditPath)
        try handle.seekToEnd()
        try handle.write(contentsOf: Data((line + "\n").utf8))
        try handle.close()
      } catch {}
    } else {
      try? (line + "\n").write(to: auditPath, atomically: true, encoding: .utf8)
    }
  }

  func readAudit(limit: Int) -> String {
    guard let text = try? String(contentsOf: auditPath, encoding: .utf8) else {
      return ""
    }
    let lines = text.split(separator: "\n", omittingEmptySubsequences: true)
    return lines.suffix(limit).joined(separator: "\n")
  }

  func sanitizeForAudit(_ value: Any?) -> Any? {
    guard let value = value else { return nil }
    if let dict = value as? [String: Any] {
      var out: [String: Any] = [:]
      for (k, v) in dict {
        if k.lowercased().contains("text") {
          if let s = v as? String {
            out[k] = ["bytes": s.utf8.count]
          } else {
            out[k] = "[redacted]"
          }
        } else {
          out[k] = sanitizeForAudit(v)
        }
      }
      return out
    }
    if let arr = value as? [Any] {
      return arr.map { sanitizeForAudit($0) ?? NSNull() }
    }
    if let s = value as? String {
      return s.count > 512 ? String(s.prefix(512)) + "…" : s
    }
    if value is NSNull || value is NSNumber {
      return value
    }
    return "\(value)"
  }

  func isoNow() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter.string(from: Date())
  }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
  var window: NSWindow!
  let bridge = Bridge(appId: __APP_ID__, allowFsAppData: __ALLOW_FS__, allowNotifyShow: __ALLOW_NOTIFY__, allowClipboard: __ALLOW_CLIPBOARD__, allowHttpFetch: __ALLOW_HTTP_FETCH__, allowKeychain: __ALLOW_KEYCHAIN__, allowContacts: __ALLOW_CONTACTS__, allowCalendar: __ALLOW_CALENDAR__)

  func applicationDidFinishLaunching(_ notification: Notification) {
    let url: URL
    if CommandLine.arguments.count >= 2 {
      url = URL(fileURLWithPath: CommandLine.arguments[1])
    } else if let resourceUrl = Bundle.main.resourceURL?.appendingPathComponent("index.html") {
      url = resourceUrl
    } else {
      fputs("kotoba-shell: index.html not found\n", stderr)
      NSApp.terminate(nil)
      return
    }
    let config = WKWebViewConfiguration()
    config.userContentController.add(bridge, name: "kotoba")
    let webView = WKWebView(frame: .zero, configuration: config)
    bridge.webView = webView

    window = NSWindow(
      contentRect: NSRect(x: 0, y: 0, width: 1024, height: 720),
      styleMask: [.titled, .closable, .miniaturizable, .resizable],
      backing: .buffered,
      defer: false
    )
    window.center()
    window.title = "kotoba-shell dev"
    window.contentView = webView
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
  }

  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    true
  }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
"#;
    template
        .replace("__APP_ID__", &app_id)
        .replace("__ALLOW_FS__", if allow_fs { "true" } else { "false" })
        .replace(
            "__ALLOW_NOTIFY__",
            if allow_notify { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CLIPBOARD__",
            if allow_clipboard { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_HTTP_FETCH__",
            if allow_http_fetch { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_KEYCHAIN__",
            if allow_keychain { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CONTACTS__",
            if allow_contacts { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CALENDAR__",
            if allow_calendar { "true" } else { "false" },
        )
}

fn ios_swift_runner(plan: &ShellPlan) -> String {
    let app_id = swift_string(&plan.app_id);
    let caps = target_capabilities(plan, Target::Ios);
    let allow_fs = caps.iter().any(|c| c == "fs/app-data");
    let allow_notify = caps.iter().any(|c| c == "notify/show");
    let allow_clipboard = caps.iter().any(|c| is_clipboard_capability(c));
    let allow_http_fetch = caps.iter().any(|c| is_http_fetch_capability(c));
    let allow_keychain = caps.iter().any(|c| is_keychain_capability(c));
    let allow_contacts = caps.iter().any(|c| is_contacts_capability(c));
    let allow_calendar = caps.iter().any(|c| is_calendar_capability(c));
    let template = r#"import UIKit
import WebKit
import Contacts
import EventKit
import UserNotifications
import Security

final class KotobaShellViewController: UIViewController, WKScriptMessageHandler, WKNavigationDelegate {
  private var webView: WKWebView!
  private let appId = __APP_ID__
  private let allowFsAppData = __ALLOW_FS__
  private let allowNotifyShow = __ALLOW_NOTIFY__
  private let allowClipboard = __ALLOW_CLIPBOARD__
  private let allowHttpFetch = __ALLOW_HTTP_FETCH__
  private let allowKeychain = __ALLOW_KEYCHAIN__
  private let allowContacts = __ALLOW_CONTACTS__
  private let allowCalendar = __ALLOW_CALENDAR__

  override func viewDidLoad() {
    super.viewDidLoad()
    let config = WKWebViewConfiguration()
    config.userContentController.add(self, name: "kotoba")
    webView = WKWebView(frame: view.bounds, configuration: config)
    webView.navigationDelegate = self
    webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    view.addSubview(webView)
    guard let url = Bundle.main.url(forResource: "index", withExtension: "html") else {
      return
    }
    webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
  }

  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
    NSLog("KOTOBA_SHELL_READY ios %@", appId)
  }

  func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
    guard let msg = message.body as? [String: Any] else {
      reply(requestId: nil, command: "unknown", ok: false, value: nil, error: "message must be an object")
      return
    }
    let requestId = msg["requestId"] as? String
    let command = msg["command"] as? String ?? "unknown"
    let payload = msg["payload"] as? [String: Any] ?? [:]
    switch command {
    case "shell/ping":
      reply(requestId: requestId, command: command, ok: true, value: ["app": appId, "target": "ios"], error: nil)
    case "fs/read-text", "fs/write-text", "fs/append-text":
      if allowFsAppData {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "fs/app-data provider scaffolded; durable iOS implementation pending")
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "fs/app-data capability is not granted")
      }
    case "notify/show":
      if allowNotifyShow {
        showNotification(payload: payload, requestId: requestId, command: command)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "notify/show capability is not granted")
      }
    case "clipboard/read-text":
      if allowClipboard {
        reply(requestId: requestId, command: command, ok: true, value: UIPasteboard.general.string ?? "", error: nil)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "clipboard capability is not granted")
      }
    case "clipboard/write-text":
      if allowClipboard {
        let text = payload["text"] as? String ?? ""
        UIPasteboard.general.string = text
        reply(requestId: requestId, command: command, ok: true, value: ["bytes": text.utf8.count], error: nil)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "clipboard capability is not granted")
      }
    case "http/fetch":
      if allowHttpFetch {
        fetchHttp(payload: payload, requestId: requestId, command: command)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "http/fetch capability is not granted")
      }
    case "keychain/read-text":
      if allowKeychain {
        do {
          let key = try keychainKey(payload)
          let text = try keychainRead(key)
          reply(requestId: requestId, command: command, ok: true, value: text, error: nil)
        } catch {
          reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
        }
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "keychain capability is not granted")
      }
    case "keychain/write-text":
      if allowKeychain {
        do {
          let key = try keychainKey(payload)
          let text = payload["text"] as? String ?? ""
          try keychainWrite(key, text: text)
          reply(requestId: requestId, command: command, ok: true, value: ["key": key, "bytes": text.utf8.count], error: nil)
        } catch {
          reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
        }
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "keychain capability is not granted")
      }
    case "keychain/delete":
      if allowKeychain {
        do {
          let key = try keychainKey(payload)
          keychainDelete(key)
          reply(requestId: requestId, command: command, ok: true, value: ["key": key, "deleted": true], error: nil)
        } catch {
          reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
        }
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "keychain capability is not granted")
      }
    case "contacts/list":
      if allowContacts {
        listContacts(payload: payload, requestId: requestId, command: command)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "contacts capability is not granted")
      }
    case "calendar/list-events":
      if allowCalendar {
        listCalendarEvents(payload: payload, requestId: requestId, command: command)
      } else {
        reply(requestId: requestId, command: command, ok: false, value: nil, error: "calendar capability is not granted")
      }
    default:
      reply(requestId: requestId, command: command, ok: false, value: nil, error: "unknown command: \(command)")
    }
  }

  private func showNotification(payload: [String: Any], requestId: String?, command: String) {
    let title = payload["title"] as? String ?? appId
    let body = payload["body"] as? String ?? ""
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    let notificationId = "kotoba-shell-\(UUID().uuidString)"
    let request = UNNotificationRequest(identifier: notificationId, content: content, trigger: nil)
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { granted, authError in
      if let authError = authError {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(authError)")
        return
      }
      if !granted {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "notification authorization was not granted")
        return
      }
      UNUserNotificationCenter.current().add(request) { addError in
        if let addError = addError {
          self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(addError)")
        } else {
          self.reply(requestId: requestId, command: command, ok: true, value: ["delivered": true, "title": title], error: nil)
        }
      }
    }
  }

  private func fetchHttp(payload: [String: Any], requestId: String?, command: String) {
    guard let raw = payload["url"] as? String,
          let url = URL(string: raw),
          let scheme = url.scheme?.lowercased(),
          scheme == "https" || scheme == "http" else {
      reply(requestId: requestId, command: command, ok: false, value: nil, error: "payload.url must be an http or https URL")
      return
    }
    let method = (payload["method"] as? String ?? "GET").uppercased()
    if !["GET", "POST", "PUT", "PATCH", "DELETE"].contains(method) {
      reply(requestId: requestId, command: command, ok: false, value: nil, error: "unsupported HTTP method: \(method)")
      return
    }
    var request = URLRequest(url: url)
    request.httpMethod = method
    if let headers = payload["headers"] as? [String: String] {
      for (key, value) in headers {
        request.setValue(value, forHTTPHeaderField: key)
      }
    }
    if let body = payload["body"] as? String {
      request.httpBody = Data(body.utf8)
    }
    URLSession.shared.dataTask(with: request) { data, response, err in
      if let err = err {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(err)")
        return
      }
      let status = (response as? HTTPURLResponse)?.statusCode ?? 0
      let text = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
      self.reply(requestId: requestId, command: command, ok: true, value: ["status": status, "body": String(text.prefix(32768))], error: nil)
    }.resume()
  }

  private func keychainKey(_ payload: [String: Any]) throws -> String {
    guard let key = payload["key"] as? String, !key.isEmpty, !key.contains("/") && !key.contains("\\") else {
      throw NSError(domain: "kotoba-shell", code: 400, userInfo: [NSLocalizedDescriptionKey: "payload.key is required and must be a simple key"])
    }
    return key
  }

  private func keychainQuery(_ key: String) -> [String: Any] {
    [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrService as String: appId,
      kSecAttrAccount as String: key
    ]
  }

  private func keychainRead(_ key: String) throws -> String {
    var query = keychainQuery(key)
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)
    if status == errSecItemNotFound {
      throw NSError(domain: "kotoba-shell", code: 404, userInfo: [NSLocalizedDescriptionKey: "keychain item not found"])
    }
    if status != errSecSuccess {
      throw NSError(domain: "kotoba-shell", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "keychain read failed: \(status)"])
    }
    guard let data = item as? Data, let text = String(data: data, encoding: .utf8) else {
      throw NSError(domain: "kotoba-shell", code: 500, userInfo: [NSLocalizedDescriptionKey: "keychain item is not utf8 text"])
    }
    return text
  }

  private func keychainWrite(_ key: String, text: String) throws {
    let data = Data(text.utf8)
    var query = keychainQuery(key)
    let update: [String: Any] = [kSecValueData as String: data]
    let updateStatus = SecItemUpdate(query as CFDictionary, update as CFDictionary)
    if updateStatus == errSecSuccess {
      return
    }
    if updateStatus != errSecItemNotFound {
      throw NSError(domain: "kotoba-shell", code: Int(updateStatus), userInfo: [NSLocalizedDescriptionKey: "keychain update failed: \(updateStatus)"])
    }
    query[kSecValueData as String] = data
    let addStatus = SecItemAdd(query as CFDictionary, nil)
    if addStatus != errSecSuccess {
      throw NSError(domain: "kotoba-shell", code: Int(addStatus), userInfo: [NSLocalizedDescriptionKey: "keychain add failed: \(addStatus)"])
    }
  }

  private func keychainDelete(_ key: String) {
    SecItemDelete(keychainQuery(key) as CFDictionary)
  }

  private func listContacts(payload: [String: Any], requestId: String?, command: String) {
    let limit = max(1, min(payload["limit"] as? Int ?? 50, 200))
    let store = CNContactStore()
    store.requestAccess(for: .contacts) { granted, accessError in
      if let accessError = accessError {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(accessError)")
        return
      }
      if !granted {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "contacts authorization was not granted")
        return
      }
      let keys: [CNKeyDescriptor] = [
        CNContactIdentifierKey as CNKeyDescriptor,
        CNContactGivenNameKey as CNKeyDescriptor,
        CNContactFamilyNameKey as CNKeyDescriptor,
        CNContactOrganizationNameKey as CNKeyDescriptor,
        CNContactEmailAddressesKey as CNKeyDescriptor,
        CNContactPhoneNumbersKey as CNKeyDescriptor
      ]
      let request = CNContactFetchRequest(keysToFetch: keys)
      request.sortOrder = .userDefault
      var contacts: [[String: Any]] = []
      do {
        try store.enumerateContacts(with: request) { contact, stop in
          var row: [String: Any] = [
            "id": contact.identifier,
            "givenName": contact.givenName,
            "familyName": contact.familyName,
            "organizationName": contact.organizationName
          ]
          let displayName = [contact.givenName, contact.familyName].filter { !$0.isEmpty }.joined(separator: " ")
          row["displayName"] = displayName.isEmpty ? contact.organizationName : displayName
          row["emails"] = contact.emailAddresses.map { $0.value as String }
          row["phones"] = contact.phoneNumbers.map { $0.value.stringValue }
          contacts.append(row)
          if contacts.count >= limit {
            stop.pointee = true
          }
        }
        self.reply(requestId: requestId, command: command, ok: true, value: ["contacts": contacts, "count": contacts.count], error: nil)
      } catch {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(error)")
      }
    }
  }

  private func listCalendarEvents(payload: [String: Any], requestId: String?, command: String) {
    let store = EKEventStore()
    let finish: (Bool, Error?) -> Void = { granted, accessError in
      if let accessError = accessError {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "\(accessError)")
        return
      }
      if !granted {
        self.reply(requestId: requestId, command: command, ok: false, value: nil, error: "calendar authorization was not granted")
        return
      }
      self.fetchCalendarEvents(store: store, payload: payload, requestId: requestId, command: command)
    }
    if #available(iOS 17.0, *) {
      store.requestFullAccessToEvents(completion: finish)
    } else {
      store.requestAccess(to: .event, completion: finish)
    }
  }

  private func fetchCalendarEvents(store: EKEventStore, payload: [String: Any], requestId: String?, command: String) {
    let limit = max(1, min(payload["limit"] as? Int ?? 50, 200))
    let days = max(1, min(payload["days"] as? Int ?? 30, 366))
    let start = Date()
    let end = Calendar.current.date(byAdding: .day, value: days, to: start) ?? start
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let formatter = ISO8601DateFormatter()
    let events = store.events(matching: predicate)
      .sorted { $0.startDate < $1.startDate }
      .prefix(limit)
      .map { event -> [String: Any] in
        var row: [String: Any] = [
          "id": event.eventIdentifier ?? "",
          "title": event.title ?? "",
          "start": formatter.string(from: event.startDate),
          "end": formatter.string(from: event.endDate),
          "calendar": event.calendar.title,
          "isAllDay": event.isAllDay
        ]
        if let location = event.location, !location.isEmpty {
          row["location"] = location
        }
        return row
      }
    reply(requestId: requestId, command: command, ok: true, value: ["events": Array(events), "count": events.count, "days": days], error: nil)
  }

  private func reply(requestId: String?, command: String, ok: Bool, value: Any?, error: String?) {
    var detail: [String: Any] = ["command": command, "ok": ok]
    if let requestId = requestId { detail["requestId"] = requestId }
    if let value = value { detail["value"] = value }
    if let error = error { detail["error"] = error }
    guard let data = try? JSONSerialization.data(withJSONObject: detail),
          let json = String(data: data, encoding: .utf8) else {
      return
    }
    webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('kotoba-shell-message', { detail: \(json) }));")
  }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
  var window: UIWindow?

  func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    window = UIWindow(frame: UIScreen.main.bounds)
    window?.rootViewController = KotobaShellViewController()
    window?.makeKeyAndVisible()
    return true
  }
}
"#;
    template
        .replace("__APP_ID__", &app_id)
        .replace("__ALLOW_FS__", if allow_fs { "true" } else { "false" })
        .replace(
            "__ALLOW_NOTIFY__",
            if allow_notify { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CLIPBOARD__",
            if allow_clipboard { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_HTTP_FETCH__",
            if allow_http_fetch { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_KEYCHAIN__",
            if allow_keychain { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CONTACTS__",
            if allow_contacts { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CALENDAR__",
            if allow_calendar { "true" } else { "false" },
        )
}

fn ios_scaffold_readme(plan: &ShellPlan) -> String {
    format!(
        r#"# {name} iOS scaffold

Generated by `kotoba shell build --target ios`.

This is a WKWebView shell scaffold with a generated Xcode project for local
simulator SDK build checks. It is not a complete signed App Store build. The
generated `Resources/kotoba-shell-permissions.json` is the shell permission
contract derived from `app.kotoba.edn`.
"#,
        name = plan.app_name
    )
}

fn android_package_path(app_id: &str) -> PathBuf {
    app_id
        .split('.')
        .filter(|part| !part.is_empty())
        .fold(PathBuf::new(), |path, part| {
            path.join(android_identifier_segment(part))
        })
}

fn android_package_name(app_id: &str) -> String {
    app_id
        .split('.')
        .filter(|part| !part.is_empty())
        .map(android_identifier_segment)
        .collect::<Vec<_>>()
        .join(".")
}

fn android_identifier_segment(s: &str) -> String {
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        let mut c = if c.is_ascii_alphanumeric() || c == '_' {
            c
        } else {
            '_'
        };
        if i == 0 && c.is_ascii_digit() {
            out.push('_');
        }
        if !c.is_ascii() {
            c = '_';
        }
        out.push(c);
    }
    if out.is_empty() {
        "_".to_string()
    } else {
        out
    }
}

fn android_settings(plan: &ShellPlan) -> String {
    format!(
        r#"pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = "{}"
include(":app")
"#,
        plan.app_name
    )
}

fn android_root_gradle() -> &'static str {
    r#"plugins {
    id("com.android.application") version "8.5.2" apply false
}
"#
}

fn android_gradlew_script() -> &'static str {
    r#"#!/bin/sh
set -eu

if [ -z "${JAVA_HOME:-}" ] && [ -x /usr/libexec/java_home ]; then
  JAVA_HOME="$(/usr/libexec/java_home -v 21 2>/dev/null || true)"
  if [ -n "$JAVA_HOME" ]; then
    export JAVA_HOME
  fi
fi

if [ -n "${KOTOBA_GRADLE:-}" ]; then
  exec "$KOTOBA_GRADLE" "$@"
fi

for gradle in "$HOME"/.gradle/wrapper/dists/gradle-8.14.3-bin/*/gradle-8.14.3/bin/gradle; do
  if [ -x "$gradle" ]; then
    exec "$gradle" "$@"
  fi
done

if command -v gradle >/dev/null 2>&1; then
  exec gradle "$@"
fi

echo "kotoba-shell: Gradle 8.14.3 cache, KOTOBA_GRADLE, or system gradle is required" >&2
exit 127
"#
}

fn android_gradlew_bat() -> &'static str {
    r#"@echo off
if not "%KOTOBA_GRADLE%"=="" (
  "%KOTOBA_GRADLE%" %*
  exit /b %ERRORLEVEL%
)
gradle %*
"#
}

fn make_executable(path: &Path) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut permissions = std::fs::metadata(path)
            .with_context(|| format!("metadata {}", path.display()))?
            .permissions();
        permissions.set_mode(0o755);
        std::fs::set_permissions(path, permissions)
            .with_context(|| format!("chmod +x {}", path.display()))?;
    }
    Ok(())
}

fn android_gradle_properties() -> &'static str {
    r#"# Generated by kotoba shell.
org.gradle.daemon=false
org.gradle.parallel=false
org.gradle.configureondemand=false
android.nonTransitiveRClass=true
android.suppressUnsupportedCompileSdk=35
"#
}

fn android_local_properties() -> String {
    let sdk_dir = find_android_sdk_dir()
        .map(|path| path.display().to_string())
        .unwrap_or_default();
    format!("sdk.dir={}\n", escape_android_properties_path(&sdk_dir))
}

fn find_android_sdk_dir() -> Option<PathBuf> {
    for key in ["ANDROID_HOME", "ANDROID_SDK_ROOT"] {
        if let Some(path) = std::env::var_os(key).map(PathBuf::from) {
            if path.join("platforms").is_dir() {
                return Some(path);
            }
        }
    }
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    let path = home.join("Library/Android/sdk");
    if path.join("platforms").is_dir() {
        Some(path)
    } else {
        None
    }
}

fn escape_android_properties_path(path: &str) -> String {
    path.replace('\\', "\\\\").replace(':', "\\:")
}

fn android_app_gradle(plan: &ShellPlan) -> String {
    format!(
        r#"plugins {{
    id("com.android.application")
}}

android {{
    namespace = "{package}"
    compileSdk = 35

    defaultConfig {{
        applicationId = "{package}"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}
}}
"#,
        package = android_package_name(&plan.app_id)
    )
}

fn android_manifest(plan: &ShellPlan) -> String {
    let caps = target_capabilities(plan, Target::Android);
    let permissions = android_permission_lines(&caps);
    format!(
        r#"<manifest xmlns:android="http://schemas.android.com/apk/res/android">
{permissions}
  <application
      android:label="{name}"
      android:theme="@android:style/Theme.Material.Light.NoActionBar"
      android:usesCleartextTraffic="false">
    <activity
        android:name=".MainActivity"
        android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
"#,
        permissions = permissions,
        name = html_escape(&plan.app_name)
    )
}

fn android_main_activity(plan: &ShellPlan) -> String {
    let package = android_package_name(&plan.app_id);
    let caps = target_capabilities(plan, Target::Android);
    let allow_fs = caps.iter().any(|c| c == "fs/app-data");
    let allow_notify = caps.iter().any(|c| c == "notify/show");
    let allow_clipboard = caps.iter().any(|c| is_clipboard_capability(c));
    let allow_http_fetch = caps.iter().any(|c| is_http_fetch_capability(c));
    let allow_keychain = caps.iter().any(|c| is_keychain_capability(c));
    let allow_contacts = caps.iter().any(|c| is_contacts_capability(c));
    let allow_calendar = caps.iter().any(|c| is_calendar_capability(c));
    let template = r#"package __PACKAGE__;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.os.Build;
import android.os.Bundle;
import android.provider.CalendarContract;
import android.provider.ContactsContract;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Iterator;
import java.util.Locale;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

import org.json.JSONArray;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    private WebView webView;
    private final KotobaBridge bridge = new KotobaBridge();
    private static final int NOTIFICATION_PERMISSION_REQUEST = 7300;
    private static final int CONTACTS_PERMISSION_REQUEST = 7301;
    private static final int CALENDAR_PERMISSION_REQUEST = 7302;
    private static final String NOTIFICATION_CHANNEL_ID = "kotoba-shell";
    private static final String KEYCHAIN_ALIAS = "kotoba-shell-keychain";
    private String pendingPermissionRaw;
    private String pendingPermissionRequestId = "";
    private String pendingPermissionCommand = "";
    private int pendingPermissionCode = 0;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                Log.i("KotobaShell", "KOTOBA_SHELL_READY android " + getPackageName());
            }
        });
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(bridge, "kotobaAndroid");
        setContentView(webView);
        ensureNotificationChannel();
        webView.loadUrl("file:///android_asset/index.html");
    }

    private void ensureNotificationChannel() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        NotificationChannel channel = new NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            "kotoba-shell",
            NotificationManager.IMPORTANCE_DEFAULT
        );
        manager.createNotificationChannel(channel);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != pendingPermissionCode) {
            return;
        }
        String raw = pendingPermissionRaw;
        String requestId = pendingPermissionRequestId;
        String command = pendingPermissionCommand;
        pendingPermissionRaw = null;
        pendingPermissionRequestId = "";
        pendingPermissionCommand = "";
        pendingPermissionCode = 0;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED && raw != null) {
            bridge.postMessage(raw);
        } else {
            bridge.reply(requestId, command, false, null, "Android runtime permission was not granted");
        }
    }

    private void requestShellPermission(final String permission, final int requestCode, String raw, String requestId, String command) {
        if (pendingPermissionRaw != null) {
            bridge.reply(requestId, command, false, null, "another Android runtime permission request is already pending");
            return;
        }
        pendingPermissionRaw = raw;
        pendingPermissionRequestId = requestId;
        pendingPermissionCommand = command;
        pendingPermissionCode = requestCode;
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                requestPermissions(new String[] { permission }, requestCode);
            }
        });
    }

    public final class KotobaBridge {
        @JavascriptInterface
        public void postMessage(String raw) {
            try {
                JSONObject msg = new JSONObject(raw);
                String requestId = msg.optString("requestId", "");
                String command = msg.optString("command", "unknown");
                JSONObject payload = msg.optJSONObject("payload");
                if (payload == null) {
                    payload = new JSONObject();
                }

                if ("shell/ping".equals(command)) {
                    JSONObject value = new JSONObject();
                    put(value, "app", "__APP_ID__");
                    put(value, "target", "android");
                    reply(requestId, command, true, value, null);
                } else if ("fs/read-text".equals(command) || "fs/write-text".equals(command) || "fs/append-text".equals(command)) {
                    if (__ALLOW_FS__) {
                        reply(requestId, command, false, null, "fs/app-data provider scaffolded; durable Android implementation pending");
                    } else {
                        reply(requestId, command, false, null, "fs/app-data capability is not granted");
                    }
                } else if ("notify/show".equals(command)) {
                    if (__ALLOW_NOTIFY__) {
                        showNotification(requestId, command, raw, payload);
                    } else {
                        reply(requestId, command, false, null, "notify/show capability is not granted");
                    }
                } else if ("clipboard/read-text".equals(command)) {
                    if (__ALLOW_CLIPBOARD__) {
                        readClipboard(requestId, command);
                    } else {
                        reply(requestId, command, false, null, "clipboard capability is not granted");
                    }
                } else if ("clipboard/write-text".equals(command)) {
                    if (__ALLOW_CLIPBOARD__) {
                        writeClipboard(requestId, command, payload);
                    } else {
                        reply(requestId, command, false, null, "clipboard capability is not granted");
                    }
                } else if ("http/fetch".equals(command)) {
                    if (__ALLOW_HTTP_FETCH__) {
                        fetchHttp(requestId, command, payload);
                    } else {
                        reply(requestId, command, false, null, "http/fetch capability is not granted");
                    }
                } else if ("keychain/read-text".equals(command)) {
                    if (__ALLOW_KEYCHAIN__) {
                        readKeychain(requestId, command, payload);
                    } else {
                        reply(requestId, command, false, null, "keychain capability is not granted");
                    }
                } else if ("keychain/write-text".equals(command)) {
                    if (__ALLOW_KEYCHAIN__) {
                        writeKeychain(requestId, command, payload);
                    } else {
                        reply(requestId, command, false, null, "keychain capability is not granted");
                    }
                } else if ("keychain/delete".equals(command)) {
                    if (__ALLOW_KEYCHAIN__) {
                        deleteKeychain(requestId, command, payload);
                    } else {
                        reply(requestId, command, false, null, "keychain capability is not granted");
                    }
                } else if ("contacts/list".equals(command)) {
                    if (__ALLOW_CONTACTS__) {
                        listContacts(requestId, command, raw, payload);
                    } else {
                        reply(requestId, command, false, null, "contacts capability is not granted");
                    }
                } else if ("calendar/list-events".equals(command)) {
                    if (__ALLOW_CALENDAR__) {
                        listCalendarEvents(requestId, command, raw, payload);
                    } else {
                        reply(requestId, command, false, null, "calendar capability is not granted");
                    }
                } else {
                    reply(requestId, command, false, null, "unknown command: " + command);
                }
            } catch (Exception err) {
                reply("", "unknown", false, null, err.toString());
            }
        }

        private void showNotification(String requestId, String command, String raw, JSONObject payload) {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestShellPermission(Manifest.permission.POST_NOTIFICATIONS, NOTIFICATION_PERMISSION_REQUEST, raw, requestId, command);
                return;
            }
            String title = payload.optString("title", "kotoba-shell");
            String body = payload.optString("body", "");
            Notification notification = new Notification.Builder(MainActivity.this, NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(body)
                .setAutoCancel(true)
                .build();
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            manager.notify((int) (System.currentTimeMillis() & 0x7fffffff), notification);
            JSONObject value = new JSONObject();
            put(value, "delivered", true);
            put(value, "title", title);
            reply(requestId, command, true, value, null);
        }

        private void readClipboard(String requestId, String command) {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            String text = "";
            if (clipboard.getPrimaryClip() != null && clipboard.getPrimaryClip().getItemCount() > 0) {
                CharSequence value = clipboard.getPrimaryClip().getItemAt(0).coerceToText(MainActivity.this);
                if (value != null) {
                    text = value.toString();
                }
            }
            reply(requestId, command, true, text, null);
        }

        private void writeClipboard(String requestId, String command, JSONObject payload) {
            String text = payload.optString("text", "");
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("kotoba-shell", text));
            JSONObject value = new JSONObject();
            put(value, "bytes", text.getBytes(StandardCharsets.UTF_8).length);
            reply(requestId, command, true, value, null);
        }

        private void fetchHttp(final String requestId, final String command, final JSONObject payload) {
            new Thread(new Runnable() {
                @Override
                public void run() {
                    HttpURLConnection connection = null;
                    try {
                        URL url = new URL(payload.optString("url", ""));
                        String scheme = url.getProtocol().toLowerCase(Locale.ROOT);
                        if (!"http".equals(scheme) && !"https".equals(scheme)) {
                            reply(requestId, command, false, null, "payload.url must be an http or https URL");
                            return;
                        }
                        String method = payload.optString("method", "GET").toUpperCase(Locale.ROOT);
                        if (!"GET".equals(method) && !"POST".equals(method) && !"PUT".equals(method) && !"PATCH".equals(method) && !"DELETE".equals(method)) {
                            reply(requestId, command, false, null, "unsupported HTTP method: " + method);
                            return;
                        }
                        connection = (HttpURLConnection) url.openConnection();
                        connection.setRequestMethod(method);
                        connection.setConnectTimeout(15000);
                        connection.setReadTimeout(15000);
                        JSONObject headers = payload.optJSONObject("headers");
                        if (headers != null) {
                            Iterator<String> keys = headers.keys();
                            while (keys.hasNext()) {
                                String key = keys.next();
                                connection.setRequestProperty(key, headers.optString(key));
                            }
                        }
                        if (payload.has("body")) {
                            byte[] body = payload.optString("body", "").getBytes(StandardCharsets.UTF_8);
                            connection.setDoOutput(true);
                            connection.getOutputStream().write(body);
                            connection.getOutputStream().close();
                        }
                        int status = connection.getResponseCode();
                        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
                        String body = stream == null ? "" : readUtf8(stream);
                        if (body.length() > 32768) {
                            body = body.substring(0, 32768);
                        }
                        JSONObject value = new JSONObject();
                        put(value, "status", status);
                        put(value, "body", body);
                        reply(requestId, command, true, value, null);
                    } catch (Exception err) {
                        reply(requestId, command, false, null, err.toString());
                    } finally {
                        if (connection != null) {
                            connection.disconnect();
                        }
                    }
                }
            }).start();
        }

        private String keychainKey(JSONObject payload) {
            String key = payload.optString("key", "");
            if (key.isEmpty() || key.contains("/") || key.contains("\\")) {
                throw new IllegalArgumentException("payload.key is required and must be a simple key");
            }
            return key;
        }

        private SharedPreferences keychainPrefs() {
            return getSharedPreferences("kotoba-shell-keychain", Context.MODE_PRIVATE);
        }

        private SecretKey keychainSecretKey() throws Exception {
            KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
            keyStore.load(null);
            KeyStore.Entry existing = keyStore.getEntry(KEYCHAIN_ALIAS, null);
            if (existing instanceof KeyStore.SecretKeyEntry) {
                return ((KeyStore.SecretKeyEntry) existing).getSecretKey();
            }
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(
                KEYCHAIN_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build();
            generator.init(spec);
            return generator.generateKey();
        }

        private String encryptKeychainText(String text) throws Exception {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, keychainSecretKey());
            String iv = Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP);
            String encrypted = Base64.encodeToString(cipher.doFinal(text.getBytes(StandardCharsets.UTF_8)), Base64.NO_WRAP);
            return iv + ":" + encrypted;
        }

        private String decryptKeychainText(String encoded) throws Exception {
            String[] parts = encoded.split(":", 2);
            if (parts.length != 2) {
                throw new IllegalArgumentException("stored keychain item is malformed");
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, keychainSecretKey(), new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
            return new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
        }

        private void readKeychain(String requestId, String command, JSONObject payload) {
            try {
                String key = keychainKey(payload);
                String stored = keychainPrefs().getString(key, null);
                if (stored == null) {
                    reply(requestId, command, false, null, "keychain item not found");
                } else {
                    reply(requestId, command, true, decryptKeychainText(stored), null);
                }
            } catch (Exception err) {
                reply(requestId, command, false, null, err.toString());
            }
        }

        private void writeKeychain(String requestId, String command, JSONObject payload) {
            try {
                String key = keychainKey(payload);
                String text = payload.optString("text", "");
                keychainPrefs().edit().putString(key, encryptKeychainText(text)).apply();
                JSONObject value = new JSONObject();
                put(value, "key", key);
                put(value, "bytes", text.getBytes(StandardCharsets.UTF_8).length);
                reply(requestId, command, true, value, null);
            } catch (Exception err) {
                reply(requestId, command, false, null, err.toString());
            }
        }

        private void deleteKeychain(String requestId, String command, JSONObject payload) {
            try {
                String key = keychainKey(payload);
                keychainPrefs().edit().remove(key).apply();
                JSONObject value = new JSONObject();
                put(value, "key", key);
                put(value, "deleted", true);
                reply(requestId, command, true, value, null);
            } catch (Exception err) {
                reply(requestId, command, false, null, err.toString());
            }
        }

        private void listContacts(String requestId, String command, String raw, JSONObject payload) {
            if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
                requestShellPermission(Manifest.permission.READ_CONTACTS, CONTACTS_PERMISSION_REQUEST, raw, requestId, command);
                return;
            }
            int limit = clamp(payload.optInt("limit", 50), 1, 200);
            JSONArray rows = new JSONArray();
            Cursor cursor = contentResolverQueryContacts();
            try {
                if (cursor != null) {
                    int idCol = cursor.getColumnIndexOrThrow(ContactsContract.Contacts._ID);
                    int nameCol = cursor.getColumnIndexOrThrow(ContactsContract.Contacts.DISPLAY_NAME_PRIMARY);
                    int phoneFlagCol = cursor.getColumnIndexOrThrow(ContactsContract.Contacts.HAS_PHONE_NUMBER);
                    while (cursor.moveToNext() && rows.length() < limit) {
                        String id = cursor.getString(idCol);
                        JSONObject row = new JSONObject();
                        put(row, "id", id);
                        put(row, "displayName", nonNull(cursor.getString(nameCol)));
                        put(row, "phones", readContactPhones(id));
                        put(row, "emails", readContactEmails(id));
                        put(row, "hasPhoneNumber", cursor.getInt(phoneFlagCol) > 0);
                        rows.put(row);
                    }
                }
            } finally {
                if (cursor != null) {
                    cursor.close();
                }
            }
            JSONObject value = new JSONObject();
            put(value, "contacts", rows);
            put(value, "count", rows.length());
            reply(requestId, command, true, value, null);
        }

        private Cursor contentResolverQueryContacts() {
            return getContentResolver().query(
                ContactsContract.Contacts.CONTENT_URI,
                new String[] {
                    ContactsContract.Contacts._ID,
                    ContactsContract.Contacts.DISPLAY_NAME_PRIMARY,
                    ContactsContract.Contacts.HAS_PHONE_NUMBER
                },
                null,
                null,
                ContactsContract.Contacts.DISPLAY_NAME_PRIMARY + " ASC"
            );
        }

        private JSONArray readContactPhones(String contactId) {
            JSONArray rows = new JSONArray();
            Cursor cursor = getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                new String[] { ContactsContract.CommonDataKinds.Phone.NUMBER },
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID + "=?",
                new String[] { contactId },
                null
            );
            try {
                if (cursor != null) {
                    int numberCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER);
                    while (cursor.moveToNext()) {
                        rows.put(nonNull(cursor.getString(numberCol)));
                    }
                }
            } finally {
                if (cursor != null) {
                    cursor.close();
                }
            }
            return rows;
        }

        private JSONArray readContactEmails(String contactId) {
            JSONArray rows = new JSONArray();
            Cursor cursor = getContentResolver().query(
                ContactsContract.CommonDataKinds.Email.CONTENT_URI,
                new String[] { ContactsContract.CommonDataKinds.Email.ADDRESS },
                ContactsContract.CommonDataKinds.Email.CONTACT_ID + "=?",
                new String[] { contactId },
                null
            );
            try {
                if (cursor != null) {
                    int emailCol = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.ADDRESS);
                    while (cursor.moveToNext()) {
                        rows.put(nonNull(cursor.getString(emailCol)));
                    }
                }
            } finally {
                if (cursor != null) {
                    cursor.close();
                }
            }
            return rows;
        }

        private void listCalendarEvents(String requestId, String command, String raw, JSONObject payload) {
            if (checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED) {
                requestShellPermission(Manifest.permission.READ_CALENDAR, CALENDAR_PERMISSION_REQUEST, raw, requestId, command);
                return;
            }
            int limit = clamp(payload.optInt("limit", 50), 1, 200);
            int days = clamp(payload.optInt("days", 30), 1, 366);
            long now = System.currentTimeMillis();
            long end = now + days * 24L * 60L * 60L * 1000L;
            JSONArray rows = new JSONArray();
            Cursor cursor = getContentResolver().query(
                CalendarContract.Events.CONTENT_URI,
                new String[] {
                    CalendarContract.Events._ID,
                    CalendarContract.Events.TITLE,
                    CalendarContract.Events.DTSTART,
                    CalendarContract.Events.DTEND,
                    CalendarContract.Events.CALENDAR_DISPLAY_NAME,
                    CalendarContract.Events.EVENT_LOCATION,
                    CalendarContract.Events.ALL_DAY
                },
                CalendarContract.Events.DTSTART + ">=? AND " + CalendarContract.Events.DTSTART + "<=?",
                new String[] { Long.toString(now), Long.toString(end) },
                CalendarContract.Events.DTSTART + " ASC"
            );
            try {
                if (cursor != null) {
                    int idCol = cursor.getColumnIndexOrThrow(CalendarContract.Events._ID);
                    int titleCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.TITLE);
                    int startCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.DTSTART);
                    int endCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.DTEND);
                    int calendarCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.CALENDAR_DISPLAY_NAME);
                    int locationCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.EVENT_LOCATION);
                    int allDayCol = cursor.getColumnIndexOrThrow(CalendarContract.Events.ALL_DAY);
                    while (cursor.moveToNext() && rows.length() < limit) {
                        JSONObject row = new JSONObject();
                        put(row, "id", nonNull(cursor.getString(idCol)));
                        put(row, "title", nonNull(cursor.getString(titleCol)));
                        put(row, "startMillis", cursor.getLong(startCol));
                        put(row, "endMillis", cursor.getLong(endCol));
                        put(row, "calendar", nonNull(cursor.getString(calendarCol)));
                        put(row, "location", nonNull(cursor.getString(locationCol)));
                        put(row, "isAllDay", cursor.getInt(allDayCol) != 0);
                        rows.put(row);
                    }
                }
            } finally {
                if (cursor != null) {
                    cursor.close();
                }
            }
            JSONObject value = new JSONObject();
            put(value, "events", rows);
            put(value, "count", rows.length());
            put(value, "days", days);
            reply(requestId, command, true, value, null);
        }

        public void reply(final String requestId, final String command, final boolean ok, final Object value, final String error) {
            final JSONObject detail = new JSONObject();
            put(detail, "requestId", requestId);
            put(detail, "command", command);
            put(detail, "ok", ok);
            if (value != null) {
                put(detail, "value", value);
            }
            if (error != null) {
                put(detail, "error", error);
            }
            final String script = "window.dispatchEvent(new CustomEvent('kotoba-shell-message', { detail: " + detail.toString() + " }));";
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    webView.evaluateJavascript(script, null);
                }
            });
        }
    }

    private static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (Exception ignored) {
        }
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private static String nonNull(String value) {
        return value == null ? "" : value;
    }

    private static String readUtf8(InputStream stream) throws Exception {
        byte[] buffer = new byte[8192];
        StringBuilder out = new StringBuilder();
        int read;
        while ((read = stream.read(buffer)) != -1) {
            out.append(new String(buffer, 0, read, StandardCharsets.UTF_8));
        }
        stream.close();
        return out.toString();
    }
}
"#;
    template
        .replace("__PACKAGE__", &package)
        .replace("__APP_ID__", &plan.app_id)
        .replace("__ALLOW_FS__", if allow_fs { "true" } else { "false" })
        .replace(
            "__ALLOW_NOTIFY__",
            if allow_notify { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CLIPBOARD__",
            if allow_clipboard { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_HTTP_FETCH__",
            if allow_http_fetch { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_KEYCHAIN__",
            if allow_keychain { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CONTACTS__",
            if allow_contacts { "true" } else { "false" },
        )
        .replace(
            "__ALLOW_CALENDAR__",
            if allow_calendar { "true" } else { "false" },
        )
}

fn android_scaffold_readme(plan: &ShellPlan) -> String {
    format!(
        r#"# {name} Android scaffold

Generated by `kotoba shell build --target android`.

This is a Gradle/WebView scaffold, not a complete Play Store release build. Run
`kotoba shell sdk-check --target android <project-dir>` after installing the
Android SDK and a compatible Gradle/JDK toolchain, or import the directory into
Android Studio. The generated `local.properties` points at the detected Android
SDK when available, and `gradle.properties` disables daemon/parallel behavior for
more deterministic agent builds. The generated
`app/src/main/assets/kotoba-shell-permissions.json` is the shell permission
contract derived from `app.kotoba.edn`.
"#,
        name = plan.app_name
    )
}

fn windows_scaffold_readme(plan: &ShellPlan) -> String {
    format!(
        r#"# {name} Windows scaffold

Generated by `kotoba shell build --target windows`.

This is the Windows target boundary for kotoba-shell. It stages UI assets,
release metadata, and aiueos shell surface contracts, while leaving the final
native host choice explicit: WebView2 host, MSIX/installer wrapper, or a
portable aiueos runner flavor.

Security gates:

```powershell
kotoba shell check app.kotoba.edn
kotoba shell build app.kotoba.edn --target windows
kotoba shell export app.kotoba.edn --target windows
kotoba shell release-check --target windows target/kotoba-shell/release/windows/{safe}
kotoba shell signing-check --target windows --execute --artifact <exe> target/kotoba-shell/release/windows/{safe}
kotoba shell submission-check --target windows --execute --artifact <zip> target/kotoba-shell/release/windows/{safe}
```
"#,
        name = plan.app_name,
        safe = safe_path_segment(&plan.app_name)
    )
}

fn windows_run_script(plan: &ShellPlan) -> String {
    format!(
        r#"$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Index = Join-Path $Root "app/index.html"
Write-Host "kotoba-shell Windows scaffold: {name}"
Write-Host "UI: $Index"
Write-Host "Open this file in a WebView2/native host or browser for local UI inspection."
Start-Process $Index
"#,
        name = plan.app_name
    )
}

fn windows_security_review(plan: &ShellPlan) -> String {
    let caps = target_capabilities(plan, Target::Windows)
        .iter()
        .map(|cap| format!("- `{cap}`"))
        .collect::<Vec<_>>()
        .join("\n");
    format!(
        r#"# {name} Windows Security Review

## Gatekeeper equivalent

Windows does not have Apple notarization. The release gate is Authenticode code
signing plus Microsoft Defender SmartScreen download reputation.

## Required release posture

- Sign `.exe`, `.msix`, or installer artifacts with Authenticode.
- Timestamp signatures with a public timestamp service.
- Keep the same publisher identity across releases.
- Publish from a stable HTTPS origin.
- Do not rotate unsigned mirrors or per-build publisher identities.
- Treat SmartScreen warnings as release evidence until reputation is established.

## Credential environment

- `KOTOBA_WINDOWS_CERT_PATH`: PFX/P12 Authenticode certificate path.
- `KOTOBA_WINDOWS_CERT_PASS`: certificate password.
- `KOTOBA_WINDOWS_TIMESTAMP_URL`: timestamp URL; default helper value is Digicert.
- `KOTOBA_WINDOWS_DOWNLOAD_URL`: stable HTTPS release URL for reputation review.

## Target capabilities

{caps}

## Generated helpers

- `sign-windows.sh`: signs an executable with `signtool` or `osslsigncode`.
- `smartscreen-windows.sh`: verifies HTTPS download URL and records reputation
  evidence that must be monitored after first public distribution.
"#,
        name = plan.app_name,
        caps = if caps.is_empty() {
            "- none".to_string()
        } else {
            caps
        }
    )
}

fn optional_ui(v: Option<&EdnValue>) -> Result<Option<UiSpec>> {
    let Some(v) = v else { return Ok(None) };
    let map = v.as_map().ok_or_else(|| anyhow!(":ui must be a map"))?;
    Ok(Some(UiSpec {
        kind: optional_string(map, &["kind"])?.unwrap_or_else(|| "cljs".to_string()),
        entry: required_string(map, &["entry"])?,
        build: optional_string(map, &["build"])?,
        dist: optional_string(map, &["dist"])?.map(PathBuf::from),
        index: optional_string(map, &["index"])?,
        build_command: optional_string_vec(map_get(map, &["build-command", "build_command"]))?,
    }))
}

fn optional_components(v: Option<&EdnValue>) -> Result<Vec<ComponentSpec>> {
    let Some(v) = v else { return Ok(Vec::new()) };
    let seq = v
        .as_seq()
        .ok_or_else(|| anyhow!(":components must be a vector/list"))?;
    let mut out = Vec::new();
    for (i, item) in seq.iter().enumerate() {
        let map = item
            .as_map()
            .ok_or_else(|| anyhow!(":components item {i} must be a map"))?;
        out.push(ComponentSpec {
            id: required_ident(map, &["id"])?,
            source: PathBuf::from(required_string(map, &["source", "src"])?),
            safe: optional_bool(map, &["safe"])?.unwrap_or(false),
            exports: optional_idents(map_get(map, &["exports"]))?,
            imports: optional_idents(map_get(map, &["imports"]))?,
        });
    }
    Ok(out)
}

fn optional_capabilities(v: Option<&EdnValue>) -> Result<BTreeMap<String, CapabilitySpec>> {
    let Some(v) = v else {
        return Ok(BTreeMap::new());
    };
    let map = v
        .as_map()
        .ok_or_else(|| anyhow!(":capabilities must be a map"))?;
    let mut out = BTreeMap::new();
    for (key, val) in map {
        let name = key_name(key).ok_or_else(|| anyhow!("capability keys must be keywords"))?;
        let platforms = val
            .as_map()
            .and_then(|m| map_get(m, &["platforms"]))
            .map(targets_from_value)
            .transpose()?
            .unwrap_or_default();
        out.insert(name.clone(), CapabilitySpec { name, platforms });
    }
    Ok(out)
}

fn optional_storage(v: Option<&EdnValue>) -> Result<Option<StorageSpec>> {
    let Some(v) = v else { return Ok(None) };
    let map = v
        .as_map()
        .ok_or_else(|| anyhow!(":storage must be a map"))?;
    Ok(Some(StorageSpec {
        kind: optional_string(map, &["kind"])?,
        encrypted: optional_bool(map, &["encrypted"])?.unwrap_or(false),
        sync: optional_string(map, &["sync"])?,
    }))
}

fn optional_targets(v: Option<&EdnValue>) -> Result<BTreeSet<Target>> {
    match v {
        Some(v) => targets_from_value(v),
        None => Ok(BTreeSet::new()),
    }
}

fn targets_from_value(v: &EdnValue) -> Result<BTreeSet<Target>> {
    let iter: Box<dyn Iterator<Item = &EdnValue> + '_> = match v {
        EdnValue::Vector(xs) | EdnValue::List(xs) => Box::new(xs.iter()),
        EdnValue::Set(xs) => Box::new(xs.iter()),
        _ => bail!("target set must be a vector/list/set"),
    };
    iter.map(|x| {
        let s =
            ident(x).ok_or_else(|| anyhow!("target entries must be keywords/strings/symbols"))?;
        Target::parse(&s)
    })
    .collect()
}

fn required_string(map: &BTreeMap<EdnValue, EdnValue>, keys: &[&str]) -> Result<String> {
    optional_string(map, keys)?.ok_or_else(|| anyhow!("missing required key {}", keys[0]))
}

fn optional_string(map: &BTreeMap<EdnValue, EdnValue>, keys: &[&str]) -> Result<Option<String>> {
    match map_get(map, keys) {
        Some(v) => ident(v)
            .or_else(|| v.as_string().map(str::to_string))
            .map(Some)
            .ok_or_else(|| anyhow!("{} must be a string/keyword/symbol", keys[0])),
        None => Ok(None),
    }
}

fn required_ident(map: &BTreeMap<EdnValue, EdnValue>, keys: &[&str]) -> Result<String> {
    map_get(map, keys)
        .and_then(ident)
        .ok_or_else(|| anyhow!("missing or invalid required key {}", keys[0]))
}

fn optional_bool(map: &BTreeMap<EdnValue, EdnValue>, keys: &[&str]) -> Result<Option<bool>> {
    match map_get(map, keys) {
        Some(v) => v
            .as_bool()
            .map(Some)
            .ok_or_else(|| anyhow!("{} must be a boolean", keys[0])),
        None => Ok(None),
    }
}

fn optional_idents(v: Option<&EdnValue>) -> Result<Vec<String>> {
    let Some(v) = v else { return Ok(Vec::new()) };
    let seq = v
        .as_seq()
        .ok_or_else(|| anyhow!("identifier list must be a vector/list"))?;
    seq.iter()
        .map(|x| ident(x).ok_or_else(|| anyhow!("identifier list entries must be identifiers")))
        .collect()
}

fn optional_string_vec(v: Option<&EdnValue>) -> Result<Vec<String>> {
    let Some(v) = v else { return Ok(Vec::new()) };
    let seq = v
        .as_seq()
        .ok_or_else(|| anyhow!("string list must be a vector/list"))?;
    seq.iter()
        .map(|x| {
            x.as_string()
                .map(str::to_string)
                .or_else(|| ident(x))
                .ok_or_else(|| anyhow!("string list entries must be strings/keywords/symbols"))
        })
        .collect()
}

fn map_get<'a>(map: &'a BTreeMap<EdnValue, EdnValue>, keys: &[&str]) -> Option<&'a EdnValue> {
    keys.iter().find_map(|key| {
        map.iter()
            .find(|(k, _)| key_name(k).as_deref() == Some(*key))
            .map(|(_, v)| v)
    })
}

fn key_name(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::Keyword(k) => Some(k.to_qualified()),
        EdnValue::String(s) => Some(s.clone()),
        EdnValue::Symbol(s) => Some(s.to_qualified()),
        _ => None,
    }
}

fn ident(v: &EdnValue) -> Option<String> {
    match v {
        EdnValue::Keyword(k) => Some(strip_keyword_ns(k)),
        EdnValue::Symbol(s) => Some(s.to_qualified()),
        EdnValue::String(s) => Some(s.clone()),
        _ => None,
    }
}

fn strip_keyword_ns(k: &Keyword) -> String {
    k.to_qualified()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn coverage_assessment_is_machine_readable_and_honest_about_release_gaps() {
        let assessment = coverage_assessment();
        assert_eq!(assessment.schema, "kotoba-shell.coverage.v0");
        assert_eq!(assessment.status, SdkCheckStatus::Passed);
        assert_eq!(assessment.baseline, "Tauri v2 application shell baseline");
        assert!(assessment.functional_coverage_percent < 80);
        assert!(assessment.release_maturity_percent < assessment.functional_coverage_percent);
        assert!(assessment.categories.len() >= 6);
        assert!(assessment
            .categories
            .iter()
            .any(|category| category.id == "ci-runtime"
                && category
                    .gaps
                    .iter()
                    .any(|gap| gap.contains("dry-run evidence"))));
        assert!(assessment
            .missing
            .iter()
            .any(|item| item.contains("store upload evidence")));

        let json = serde_json::to_string(&assessment).unwrap();
        assert!(json.contains("\"schema\":\"kotoba-shell.coverage.v0\""));
        assert!(json.contains("\"status\":\"Passed\""));
        assert!(coverage_report().contains("Estimated release maturity"));
    }

    #[test]
    fn parses_shell_manifest() {
        let m = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :ui {:kind :cljs :entry "src/app.cljs" :build :shadow-cljs}
             :components [{:id :policy :source "src/policy.clj" :safe true :exports [run]}]
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}}
             :storage {:kind :append-edn :encrypted true :sync :kotobase}
             :targets #{:macos :android}}
            "#,
        )
        .unwrap();
        assert_eq!(m.id, "jp.co.gftd.demo");
        assert_eq!(m.components[0].id, "policy");
        assert_eq!(m.components[0].source, PathBuf::from("src/policy.clj"));
        assert!(m.targets.contains(&Target::Macos));
        assert!(m.capabilities.contains_key("ledger/append"));
    }

    #[test]
    fn filters_capabilities_by_target() {
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}
                            :fs/app-data {:platforms #{:macos}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan =
            plan_manifest(PathBuf::from("app.kotoba.edn"), Path::new("."), manifest).unwrap();
        assert!(target_capabilities(&plan, Target::Macos).contains(&"fs/app-data".to_string()));
        assert!(!target_capabilities(&plan, Target::Ios).contains(&"fs/app-data".to_string()));
        assert!(target_capabilities(&plan, Target::Android).contains(&"ledger/append".to_string()));
    }

    #[test]
    fn generates_mobile_scaffolds_with_permission_metadata() {
        let root = unique_test_dir("mobile-scaffold");
        let manifest_dir = root.join("manifest");
        let dist = manifest_dir.join("dist");
        std::fs::create_dir_all(&dist).unwrap();
        std::fs::write(
            dist.join("index.html"),
            "<!doctype html><title>demo</title>",
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :ui {:kind :cljs :entry "src/app.cljs" :dist "dist" :index "index.html"}
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}
                            :fs/app-data {:platforms #{:macos}}}
             :targets #{:ios :android}}
            "#,
        )
        .unwrap();
        let plan =
            plan_manifest(manifest_dir.join("app.kotoba.edn"), &manifest_dir, manifest).unwrap();
        let out = root.join("out");

        let ios = build_ios_scaffold(&plan, &out).unwrap();
        assert_eq!(ios.target, Target::Ios);
        assert!(ios.executable.ends_with("Sources/KotobaShellApp.swift"));
        let ios_permissions = std::fs::read_to_string(
            ios.project_dir
                .join("Resources/kotoba-shell-permissions.json"),
        )
        .unwrap();
        assert!(ios_permissions.contains("\"target\": \"ios\""));
        assert!(ios_permissions.contains("ledger/append"));
        assert!(!ios_permissions.contains("fs/app-data"));
        let ios_index =
            std::fs::read_to_string(ios.project_dir.join("Resources/index.html")).unwrap();
        assert!(!ios_index.contains("<h2>fs/app-data</h2>"));
        let ios_verify = verify_generated_project(Target::Ios, &ios.project_dir).unwrap();
        assert!(ios_verify.checks.len() >= 9);
        assert!(ios
            .project_dir
            .join("demo.xcodeproj/project.pbxproj")
            .exists());
        let ios_sdk = sdk_check_project(Target::Ios, &ios.project_dir, Duration::ZERO).unwrap();
        assert_eq!(ios_sdk.target, Target::Ios);
        assert_eq!(ios_sdk.status, SdkCheckStatus::Skipped);
        assert!(ios_sdk.detail.contains("dry-run"));
        let ios_runtime =
            runtime_check_project(Target::Ios, &ios.project_dir, Duration::ZERO).unwrap();
        assert_eq!(ios_runtime.status, SdkCheckStatus::Skipped);
        assert!(ios_runtime.detail.contains("dry-run"));

        let android = build_android_scaffold(&plan, &out).unwrap();
        assert_eq!(android.target, Target::Android);
        assert!(android.executable.ends_with("MainActivity.java"));
        assert!(android
            .project_dir
            .join("app/src/main/assets/app/index.html")
            .exists());
        assert!(android
            .project_dir
            .join("app/src/main/assets/kotoba-shell-capabilities.edn")
            .exists());
        assert!(android
            .project_dir
            .join("app/src/main/assets/kotoba-shell-release.json")
            .exists());
        assert!(android
            .project_dir
            .join("app/src/main/assets/kotoba-shell-android-permissions.xml")
            .exists());
        assert!(android.project_dir.join("gradlew").exists());
        assert!(android.project_dir.join("gradlew.bat").exists());
        let gradle_properties =
            std::fs::read_to_string(android.project_dir.join("gradle.properties")).unwrap();
        assert!(gradle_properties.contains("org.gradle.daemon=false"));
        assert!(gradle_properties.contains("android.nonTransitiveRClass=true"));
        let local_properties =
            std::fs::read_to_string(android.project_dir.join("local.properties")).unwrap();
        assert!(local_properties.contains("sdk.dir="));
        let android_index =
            std::fs::read_to_string(android.project_dir.join("app/src/main/assets/index.html"))
                .unwrap();
        assert!(!android_index.contains("<h2>fs/app-data</h2>"));
        let android_verify =
            verify_generated_project(Target::Android, &android.project_dir).unwrap();
        assert!(android_verify.checks.len() >= 10);
        let macos_sdk =
            sdk_check_project(Target::Macos, &android.project_dir, Duration::from_secs(1)).unwrap();
        assert_eq!(macos_sdk.status, SdkCheckStatus::Skipped);
        let android_runtime =
            runtime_check_project(Target::Android, &android.project_dir, Duration::ZERO).unwrap();
        assert_eq!(android_runtime.status, SdkCheckStatus::Skipped);
        assert!(android_runtime.detail.contains("dry-run"));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn exports_release_artifacts_for_store_review() {
        let root = unique_test_dir("release-export");
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}
                            :notify/show {:platforms #{:ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        let out = root.join("release");

        let macos = export_release_artifacts(&plan, Target::Macos, &out).unwrap();
        assert!(macos.dir.join("kotoba-shell.entitlements").exists());
        assert!(macos.dir.join("notarize-macos.sh").exists());
        assert!(macos.dir.join("sign-macos.sh").exists());
        assert!(macos.dir.join("kotoba-shell-release-checklist.md").exists());
        assert!(macos
            .dir
            .join("kotoba-shell-updater-manifest.json")
            .exists());
        assert!(macos.dir.join("kotoba-shell-host-adapters.json").exists());
        assert!(macos
            .dir
            .join("kotoba-shell-evidence-profile.json")
            .exists());
        let macos_adapter_manifest =
            std::fs::read_to_string(macos.dir.join("kotoba-shell-host-adapters.json")).unwrap();
        assert!(macos_adapter_manifest.contains("kotoba-shell.host-adapters.v0"));
        assert!(macos_adapter_manifest.contains("KOTOBA_LLM_ADAPTER_URL"));
        let macos_evidence_profile =
            std::fs::read_to_string(macos.dir.join("kotoba-shell-evidence-profile.json")).unwrap();
        assert!(macos_evidence_profile.contains("kotoba-shell.evidence-profile.v0"));
        assert!(macos_evidence_profile.contains("store-release"));
        assert!(macos_evidence_profile.contains("coverage-evidence.json"));
        assert!(macos_evidence_profile.contains("macos-runtime-doctor-evidence.json"));
        assert!(!macos_evidence_profile.contains("android-runtime-evidence.json"));
        let macos_adapter_check = adapter_check_manifest(
            Target::Macos,
            macos.dir.join("kotoba-shell-host-adapters.json"),
            false,
            false,
            false,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(macos_adapter_check.status, SdkCheckStatus::Passed);
        let macos_checklist =
            std::fs::read_to_string(macos.dir.join("kotoba-shell-release-checklist.md")).unwrap();
        assert!(macos_checklist.contains("kotoba shell sdk-check"));
        assert!(macos_checklist.contains("kotoba shell adapter-check"));
        let macos_signing_plan =
            std::fs::read_to_string(macos.dir.join("kotoba-shell-signing-plan.json")).unwrap();
        assert!(macos_signing_plan.contains("kotoba-shell.signing-plan.v0"));
        assert!(macos_signing_plan.contains("\"target\": \"macos\""));
        assert!(macos.dir.join("app-store-connect-macos.json").exists());
        let macos_release = std::fs::read_to_string(&macos.release_manifest).unwrap();
        assert!(macos_release.contains("\"target\": \"macos\""));
        let macos_release_check = release_check_artifacts(Target::Macos, &macos.dir).unwrap();
        assert!(macos_release_check.checks.len() >= 12);
        let macos_updater_check = updater_check_manifest(
            Target::Macos,
            macos.dir.join("kotoba-shell-updater-manifest.json"),
        )
        .unwrap();
        assert_eq!(macos_updater_check.status, SdkCheckStatus::Skipped);

        let ios = export_release_artifacts(&plan, Target::Ios, &out).unwrap();
        assert!(ios.dir.join("xcode-export-options.plist").exists());
        assert!(ios.dir.join("sign-ios.sh").exists());
        assert!(ios.dir.join("submit-ios.sh").exists());
        assert!(ios.dir.join("kotoba-shell-release-checklist.md").exists());
        assert!(ios.dir.join("kotoba-shell-updater-manifest.json").exists());
        let ios_signing_plan =
            std::fs::read_to_string(ios.dir.join("kotoba-shell-signing-plan.json")).unwrap();
        assert!(ios_signing_plan.contains("kotoba-shell.signing-plan.v0"));
        assert!(ios_signing_plan.contains("\"target\": \"ios\""));
        assert!(ios.dir.join("app-store-connect-ios.json").exists());
        let ios_entitlements =
            std::fs::read_to_string(ios.dir.join("kotoba-shell.entitlements")).unwrap();
        assert!(ios_entitlements.contains("com.apple.security.app-sandbox"));
        let ios_release_check = release_check_artifacts(Target::Ios, &ios.dir).unwrap();
        assert!(ios_release_check.checks.len() >= 12);
        let ios_updater_check = updater_check_manifest(
            Target::Ios,
            ios.dir.join("kotoba-shell-updater-manifest.json"),
        )
        .unwrap();
        assert_eq!(ios_updater_check.status, SdkCheckStatus::Skipped);
        let ios_evidence_profile =
            std::fs::read_to_string(ios.dir.join("kotoba-shell-evidence-profile.json")).unwrap();
        assert!(ios_evidence_profile.contains("coverage-evidence.json"));
        assert!(ios_evidence_profile.contains("ios-runtime-doctor-evidence.json"));
        assert!(ios_evidence_profile.contains("ios-sdk-evidence.json"));
        assert!(ios_evidence_profile.contains("ios-runtime-evidence.json"));
        assert!(!ios_evidence_profile.contains("android-runtime-evidence.json"));

        let android = export_release_artifacts(&plan, Target::Android, &out).unwrap();
        assert!(android.dir.join("sign-android.sh").exists());
        assert!(android.dir.join("submit-android.sh").exists());
        let android_evidence_profile =
            std::fs::read_to_string(android.dir.join("kotoba-shell-evidence-profile.json"))
                .unwrap();
        assert!(android_evidence_profile.contains("android-release"));
        assert!(android_evidence_profile.contains("coverage-evidence.json"));
        assert!(android_evidence_profile.contains("android-runtime-doctor-evidence.json"));
        assert!(android_evidence_profile.contains("android-runtime-evidence.json"));
        let android_signing_plan =
            std::fs::read_to_string(android.dir.join("kotoba-shell-signing-plan.json")).unwrap();
        assert!(android_signing_plan.contains("kotoba-shell.signing-plan.v0"));
        assert!(android_signing_plan.contains("\"target\": \"android\""));
        let android_permissions =
            std::fs::read_to_string(android.dir.join("kotoba-shell-android-permissions.xml"))
                .unwrap();
        assert!(android_permissions.contains("android.permission.POST_NOTIFICATIONS"));
        assert!(android_permissions.contains("android.permission.INTERNET"));
        assert!(android.dir.join("play-store-review.md").exists());
        assert!(android.dir.join("play-store-data-safety.json").exists());
        let android_updater =
            std::fs::read_to_string(android.dir.join("kotoba-shell-updater-manifest.json"))
                .unwrap();
        assert!(android_updater.contains("kotoba-shell.updater.v0"));
        let data_safety =
            std::fs::read_to_string(android.dir.join("play-store-data-safety.json")).unwrap();
        assert!(data_safety.contains("kotoba-shell.play-store-data-safety.v0"));
        let android_release_check = release_check_artifacts(Target::Android, &android.dir).unwrap();
        assert!(android_release_check.checks.len() >= 12);
        if !android_release_check.missing_credentials.is_empty() {
            assert_eq!(android_release_check.status, SdkCheckStatus::Skipped);
        }
        std::env::remove_var("KOTOBA_ANDROID_KEYSTORE");
        std::env::remove_var("KOTOBA_ANDROID_KEY_ALIAS");
        std::env::remove_var("KOTOBA_ANDROID_KEYSTORE_PASS");
        std::env::remove_var("KOTOBA_ANDROID_KEY_PASS");
        let signing_missing = signing_check_artifacts(
            Target::Android,
            &android.dir,
            false,
            None,
            None,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(signing_missing.status, SdkCheckStatus::Skipped);
        assert!(signing_missing.command.is_empty());
        assert!(signing_missing
            .missing_credentials
            .contains(&"KOTOBA_ANDROID_KEYSTORE".to_string()));
        std::env::set_var("KOTOBA_ANDROID_KEYSTORE", "/tmp/kotoba-upload.keystore");
        std::env::set_var("KOTOBA_ANDROID_KEY_ALIAS", "upload");
        std::env::set_var("KOTOBA_ANDROID_KEYSTORE_PASS", "storepass");
        std::env::set_var("KOTOBA_ANDROID_KEY_PASS", "keypass");
        let signing_ready = signing_check_artifacts(
            Target::Android,
            &android.dir,
            false,
            None,
            None,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(signing_ready.status, SdkCheckStatus::Passed);
        assert!(signing_ready
            .checks
            .iter()
            .any(|check| check.contains("kotoba-shell-signing-plan.json")));
        std::env::remove_var("KOTOBA_ANDROID_KEYSTORE");
        std::env::remove_var("KOTOBA_ANDROID_KEY_ALIAS");
        std::env::remove_var("KOTOBA_ANDROID_KEYSTORE_PASS");
        std::env::remove_var("KOTOBA_ANDROID_KEY_PASS");
        std::env::remove_var("KOTOBA_PLAY_SERVICE_ACCOUNT_JSON");
        let submission_missing = submission_check_artifacts(
            Target::Android,
            &android.dir,
            false,
            None,
            None,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(submission_missing.status, SdkCheckStatus::Skipped);
        assert!(submission_missing
            .missing_credentials
            .contains(&"KOTOBA_PLAY_SERVICE_ACCOUNT_JSON".to_string()));
        std::env::set_var(
            "KOTOBA_PLAY_SERVICE_ACCOUNT_JSON",
            "/tmp/kotoba-play-service-account.json",
        );
        let submission_ready = submission_check_artifacts(
            Target::Android,
            &android.dir,
            false,
            None,
            None,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(submission_ready.status, SdkCheckStatus::Passed);
        assert!(submission_ready
            .checks
            .iter()
            .any(|check| check.contains("play-store-data-safety.json")));
        let submission_execute = submission_check_artifacts(
            Target::Android,
            &android.dir,
            true,
            None,
            None,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(submission_execute.status, SdkCheckStatus::Skipped);
        assert!(submission_execute.detail.contains("dry-run"));
        assert!(submission_execute
            .checks
            .iter()
            .any(|check| check.contains("submit-android.sh")));
        std::env::remove_var("KOTOBA_PLAY_SERVICE_ACCOUNT_JSON");
        let android_updater_check = updater_check_manifest(
            Target::Android,
            android.dir.join("kotoba-shell-updater-manifest.json"),
        )
        .unwrap();
        assert_eq!(android_updater_check.status, SdkCheckStatus::Skipped);
        let dummy_aab = android.dir.join("dummy-release.aab");
        std::fs::write(&dummy_aab, b"dummy signed artifact").unwrap();
        let finalized = finalize_updater_manifest(
            Target::Android,
            android.dir.join("kotoba-shell-updater-manifest.json"),
            &dummy_aab,
            "https://updates.example.invalid/dummy-release.aab",
            "base64-signature",
        )
        .unwrap();
        assert_eq!(finalized.sha256, sha256_hex(&dummy_aab).unwrap());
        let finalized_check = updater_check_manifest(
            Target::Android,
            android.dir.join("kotoba-shell-updater-manifest.json"),
        )
        .unwrap();
        assert_eq!(finalized_check.status, SdkCheckStatus::Passed);

        let android_manifest = android_manifest(&plan);
        assert!(android_manifest.contains("android.permission.POST_NOTIFICATIONS"));
        assert!(android_manifest.contains("android.permission.INTERNET"));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn adapter_check_requires_env_for_host_bound_components() {
        let root = unique_test_dir("adapter-check");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(
            root.join("agent.clj"),
            r#"(defn run [] (llm-infer "modelA" "ping"))"#,
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :agent
                           :source "agent.clj"
                           :safe true
                           :exports [run]
                           :imports []}]
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        let export =
            export_release_artifacts(&plan, Target::Android, root.join("release")).unwrap();
        let adapters = export.dir.join("kotoba-shell-host-adapters.json");
        let manifest = std::fs::read_to_string(&adapters).unwrap();
        assert!(manifest.contains("\"id\": \"llm\""));
        assert!(manifest.contains("\"required\": true"));
        assert!(manifest.contains("\"response\""));
        assert!(manifest.contains("\"output\": \"string\""));

        std::env::remove_var("KOTOBA_LLM_ADAPTER_URL");
        let missing = adapter_check_manifest(
            Target::Android,
            &adapters,
            false,
            false,
            false,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(missing.status, SdkCheckStatus::Skipped);
        assert!(missing
            .missing
            .contains(&"llm:KOTOBA_LLM_ADAPTER_URL".to_string()));

        std::env::set_var("KOTOBA_LLM_ADAPTER_URL", "https://llm.example.invalid");
        let ready = adapter_check_manifest(
            Target::Android,
            &adapters,
            false,
            false,
            false,
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(ready.status, SdkCheckStatus::Passed);
        std::env::set_var("KOTOBA_LLM_ADAPTER_URL", "not-a-url");
        let probe_invalid = adapter_check_manifest(
            Target::Android,
            &adapters,
            true,
            false,
            false,
            Duration::from_secs(1),
        )
        .unwrap();
        assert_eq!(probe_invalid.status, SdkCheckStatus::Skipped);
        assert!(probe_invalid
            .missing
            .iter()
            .any(|missing| missing.contains("adapter URL must start")));
        let smoke_invalid = adapter_check_manifest(
            Target::Android,
            &adapters,
            false,
            true,
            false,
            Duration::from_secs(1),
        )
        .unwrap();
        assert_eq!(smoke_invalid.status, SdkCheckStatus::Skipped);
        assert!(smoke_invalid
            .missing
            .iter()
            .any(|missing| missing.contains("adapter URL must start")));
        std::env::set_var("KOTOBA_LLM_ADAPTER_URL", "https://llm.prod.example.com");
        let hosted_ready = adapter_check_manifest(
            Target::Android,
            &adapters,
            false,
            false,
            true,
            Duration::from_secs(1),
        )
        .unwrap();
        assert_eq!(hosted_ready.status, SdkCheckStatus::Passed);
        assert!(hosted_ready
            .checks
            .iter()
            .any(|check| check.contains("adapter:llm:hosted:https:")));
        std::env::set_var("KOTOBA_LLM_ADAPTER_URL", "https://127.0.0.1:39819");
        let hosted_local = adapter_check_manifest(
            Target::Android,
            &adapters,
            false,
            false,
            true,
            Duration::from_secs(1),
        )
        .unwrap();
        assert_eq!(hosted_local.status, SdkCheckStatus::Skipped);
        assert!(hosted_local
            .missing
            .iter()
            .any(|missing| missing.contains("private/local IP")));
        std::env::remove_var("KOTOBA_LLM_ADAPTER_URL");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn adapter_smoke_response_contract_accepts_minimal_shapes() {
        validate_adapter_smoke_response("auth", br#"{"allowed":true}"#).unwrap();
        validate_adapter_smoke_response("auth", br#"{"result":{"allowed":false}}"#).unwrap();
        validate_adapter_smoke_response("kqe", br#"{"quads":[]}"#).unwrap();
        validate_adapter_smoke_response("kqe", br#"{"result":{"quads":[]}}"#).unwrap();
        validate_adapter_smoke_response("llm", br#"{"output":"echo:ping"}"#).unwrap();
        validate_adapter_smoke_response("llm", br#"{"result":{"output":"echo:ping"}}"#).unwrap();
        assert!(validate_adapter_smoke_response("llm", br#"{"ok":true}"#).is_err());
        assert!(validate_adapter_smoke_response("auth", br#"{"allowed":"yes"}"#).is_err());
        assert!(validate_adapter_smoke_response("kqe", br#"not-json"#).is_err());
    }

    #[test]
    fn evidence_check_aggregates_required_reports() {
        let root = unique_test_dir("evidence-check");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(
            root.join("live-adapter.json"),
            r#"{"status":"Passed","detail":"live adapter passed"}"#,
        )
        .unwrap();
        std::fs::write(
            root.join("coverage-evidence.json"),
            r#"{"schema":"kotoba-shell.coverage.v0","status":"Passed","detail":"coverage assessed"}"#,
        )
        .unwrap();
        std::fs::write(
            root.join("runtime.json"),
            r#"{"status":"Skipped","detail":"no device"}"#,
        )
        .unwrap();

        let skipped =
            evidence_check_dir(&root, &["live-adapter.json".to_string()], &[], None).unwrap();
        assert_eq!(skipped.status, SdkCheckStatus::Skipped);
        assert_eq!(skipped.entries.len(), 3);
        assert!(skipped
            .checks
            .contains(&"required:live-adapter.json:Passed".to_string()));

        let failed = evidence_check_dir(&root, &["runtime.json".to_string()], &[], None).unwrap();
        assert_eq!(failed.status, SdkCheckStatus::Failed);
        assert!(failed
            .missing
            .contains(&"runtime.json is Skipped, expected Passed".to_string()));

        let profile_failed = evidence_check_dir(&root, &[], &["ci".to_string()], None).unwrap();
        assert_eq!(profile_failed.status, SdkCheckStatus::Failed);
        assert!(profile_failed
            .missing
            .contains(&"live-adapter-supervisor-evidence.json is missing".to_string()));
        assert!(!profile_failed
            .missing
            .contains(&"coverage-evidence.json is missing".to_string()));
        std::fs::write(
            root.join("kotoba-shell-evidence-profile.json"),
            r#"{"schema":"kotoba-shell.evidence-profile.v0","profiles":{"android-release":["live-adapter.json","runtime.json"]}}"#,
        )
        .unwrap();
        let release_profile = evidence_check_dir(
            &root,
            &[],
            &["release".to_string()],
            Some(&root.join("kotoba-shell-evidence-profile.json")),
        )
        .unwrap();
        assert_eq!(release_profile.status, SdkCheckStatus::Failed);
        assert!(release_profile
            .missing
            .contains(&"runtime.json is Skipped, expected Passed".to_string()));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn provider_catalog_maps_capabilities_to_bridge_commands() {
        let root = unique_test_dir("provider-catalog");
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :capabilities {:fs/app-data {:platforms #{:macos}}
                            :notify/show {:platforms #{:macos :ios :android}}
                            :clipboard/read-text {:platforms #{:macos :ios :android}}
                            :clipboard/write-text {:platforms #{:macos :ios :android}}
                            :http/fetch {:platforms #{:macos :ios :android}}
                            :keychain/read-text {:platforms #{:macos :ios :android}}
                            :keychain/write-text {:platforms #{:macos :ios :android}}
                            :contacts/read {:platforms #{:macos :ios :android}}
                            :calendar/read {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        let macos_html = shell_html(&plan, Some(Target::Macos));
        assert!(macos_html.contains("<h2>notify/show</h2>"));
        assert!(macos_html.contains("<h2>clipboard/text</h2>"));
        assert!(macos_html.contains("clipboard/write-text"));
        assert!(macos_html.contains("<h2>http/fetch</h2>"));
        assert!(macos_html.contains("window.kotobaShell.invoke(\"http/fetch\""));
        assert!(macos_html.contains("<h2>keychain/text</h2>"));
        assert!(macos_html.contains("keychain/write-text"));
        assert!(macos_html.contains("<h2>contacts/read</h2>"));
        assert!(macos_html.contains("<h2>calendar/read</h2>"));

        let ios_html = shell_html(&plan, Some(Target::Ios));
        assert!(!ios_html.contains("<h2>fs/app-data</h2>"));
        assert!(ios_html.contains("<h2>notify/show</h2>"));
        assert!(ios_html.contains("<h2>clipboard/text</h2>"));
        assert!(ios_html.contains("<h2>http/fetch</h2>"));
        assert!(ios_html.contains("<h2>keychain/text</h2>"));
        assert!(ios_html.contains("<h2>contacts/read</h2>"));
        assert!(ios_html.contains("<h2>calendar/read</h2>"));

        let release = release_manifest_json(&plan, Target::Android).unwrap();
        assert!(release.contains("\"id\": \"shell/notification\""));
        assert!(release.contains("\"id\": \"shell/clipboard\""));
        assert!(release.contains("\"id\": \"shell/http-fetch\""));
        assert!(release.contains("\"id\": \"shell/keychain\""));
        assert!(release.contains("\"id\": \"shell/contacts\""));
        assert!(release.contains("\"id\": \"shell/calendar\""));
        assert!(release.contains("clipboard/read-text"));
        assert!(release.contains("\"http/fetch\""));
        assert!(release.contains("keychain/read-text"));
        assert!(release.contains("\"requiresClipboard\": true"));
        assert!(release.contains("\"requiresNetworkClient\": true"));
        assert!(release.contains("\"requiresContacts\": true"));
        assert!(release.contains("\"requiresCalendar\": true"));

        let ios_plist = ios_info_plist(&plan);
        assert!(ios_plist.contains("NSContactsUsageDescription"));
        assert!(ios_plist.contains("NSCalendarsUsageDescription"));

        let macos_plist = info_plist(&plan, Path::new("demo"));
        assert!(macos_plist.contains("NSContactsUsageDescription"));
        assert!(macos_plist.contains("NSCalendarsUsageDescription"));

        let android_manifest = android_manifest(&plan);
        assert!(android_manifest.contains("android.permission.READ_CONTACTS"));
        assert!(android_manifest.contains("android.permission.READ_CALENDAR"));

        let runner = macos_swift_runner(&plan);
        assert!(runner.contains("case \"notify/show\""));
        assert!(runner.contains("case \"clipboard/read-text\""));
        assert!(runner.contains("case \"http/fetch\""));
        assert!(runner.contains("case \"keychain/read-text\""));
        assert!(runner.contains("case \"contacts/list\""));
        assert!(runner.contains("case \"calendar/list-events\""));
        assert!(runner.contains("import Contacts"));
        assert!(runner.contains("import EventKit"));
        assert!(runner.contains("allowClipboard: true"));
        assert!(runner.contains("allowHttpFetch: true"));
        assert!(runner.contains("allowKeychain: true"));
        assert!(runner.contains("allowContacts: true"));
        assert!(runner.contains("allowCalendar: true"));
        assert!(runner.contains("URLSession.shared.dataTask"));
        assert!(runner.contains("SecItemCopyMatching"));
        assert!(runner.contains("CNContactStore"));
        assert!(runner.contains("EKEventStore"));
        assert!(runner.contains("UNUserNotificationCenter"));
        assert!(!runner.contains("NSUserNotification"));

        let ios_runner = ios_swift_runner(&plan);
        assert!(ios_runner.contains("import Contacts"));
        assert!(ios_runner.contains("import EventKit"));
        assert!(ios_runner.contains("CNContactStore"));
        assert!(ios_runner.contains("EKEventStore"));
        assert!(ios_runner.contains("requestFullAccessToEvents"));
        assert!(ios_runner.contains("UNUserNotificationCenter"));
        assert!(ios_runner.contains("UIPasteboard.general"));
        assert!(ios_runner.contains("URLSession.shared.dataTask"));
        assert!(ios_runner.contains("SecItemCopyMatching"));
        assert!(!ios_runner
            .contains("notify/show provider scaffolded; durable iOS implementation pending"));
        assert!(!ios_runner
            .contains("clipboard provider scaffolded; durable iOS implementation pending"));
        assert!(!ios_runner
            .contains("http/fetch provider scaffolded; durable iOS implementation pending"));
        assert!(!ios_runner
            .contains("keychain provider scaffolded; durable iOS implementation pending"));
        assert!(!ios_runner
            .contains("contacts provider scaffolded; durable iOS implementation pending"));
        assert!(!ios_runner
            .contains("calendar provider scaffolded; durable iOS implementation pending"));

        let android_runner = android_main_activity(&plan);
        assert!(android_runner.contains("NotificationManager"));
        assert!(android_runner.contains("ClipboardManager"));
        assert!(android_runner.contains("HttpURLConnection"));
        assert!(android_runner.contains("AndroidKeyStore"));
        assert!(android_runner.contains("AES/GCM/NoPadding"));
        assert!(android_runner.contains("KeyGenParameterSpec"));
        assert!(android_runner.contains("getSharedPreferences(\"kotoba-shell-keychain\""));
        assert!(android_runner.contains("ContactsContract"));
        assert!(android_runner.contains("CalendarContract"));
        assert!(
            android_runner.contains("requestPermissions(new String[] { permission }, requestCode)")
        );
        assert!(android_runner.contains("onRequestPermissionsResult"));
        assert!(android_runner.contains("pendingPermissionRaw"));
        assert!(android_runner.contains("POST_NOTIFICATIONS"));
        assert!(android_runner.contains("READ_CONTACTS"));
        assert!(android_runner.contains("READ_CALENDAR"));
        assert!(!android_runner
            .contains("notify/show provider scaffolded; durable Android implementation pending"));
        assert!(!android_runner
            .contains("clipboard provider scaffolded; durable Android implementation pending"));
        assert!(!android_runner
            .contains("http/fetch provider scaffolded; durable Android implementation pending"));
        assert!(!android_runner
            .contains("keychain provider scaffolded; durable Android implementation pending"));
        assert!(!android_runner
            .contains("contacts provider scaffolded; durable Android implementation pending"));
        assert!(!android_runner
            .contains("calendar provider scaffolded; durable Android implementation pending"));

        let allowed_broker =
            broker_check_plan(&plan, Target::Android, Some("clipboard/read-text")).unwrap();
        assert_eq!(allowed_broker.status, SdkCheckStatus::Passed);
        let allowed_dry_run = allowed_broker.dry_run.unwrap();
        assert!(allowed_dry_run.allowed);
        assert_eq!(
            allowed_dry_run.capability.as_deref(),
            Some("clipboard/text")
        );
        assert_eq!(
            allowed_dry_run.audit_event["schema"],
            "aiueos.shell.audit.v0"
        );
        let audit_path = root.join("broker-audit.jsonl");
        append_broker_audit(&audit_path, &allowed_dry_run.audit_event).unwrap();
        append_broker_audit(&audit_path, &allowed_dry_run.audit_event).unwrap();
        let audit_log = std::fs::read_to_string(&audit_path).unwrap();
        assert_eq!(audit_log.lines().count(), 2);
        assert!(audit_log.contains("\"schema\":\"aiueos.shell.audit.v0\""));
        assert!(audit_log.contains("\"phase\":\"broker-dry-run\""));

        let denied_broker =
            broker_check_plan(&plan, Target::Android, Some("fs/read-text")).unwrap();
        assert_eq!(denied_broker.status, SdkCheckStatus::Failed);
        assert!(!denied_broker.dry_run.unwrap().allowed);

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_check_runs_pure_safe_component_under_fuel() {
        let root = unique_test_dir("supervisor-check");
        std::fs::create_dir_all(root.join("src")).unwrap();
        std::fs::write(root.join("src/policy.clj"), "(defn run [n] (+ n 1))").unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :policy
                           :source "src/policy.clj"
                           :safe true
                           :exports [run]
                           :imports []}]
             :capabilities {:notify/show {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        let report = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("policy".to_string()),
                function: Some("run".to_string()),
                args: vec![41],
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: Vec::new(),
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        assert_eq!(report.status, SdkCheckStatus::Passed);
        assert!(report
            .checks
            .contains(&"component:policy:policy-minimal".to_string()));
        let dry_run = report.dry_run.unwrap();
        assert_eq!(dry_run.status, SdkCheckStatus::Passed);
        assert_eq!(dry_run.result, Some(42));
        assert_eq!(report.components[0].exports, vec!["run"]);

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_check_runs_auth_host_bound_safe_component() {
        let root = unique_test_dir("supervisor-auth");
        std::fs::create_dir_all(root.join("src")).unwrap();
        std::fs::write(
            root.join("src/auth.clj"),
            r#"(defn run [n] (if (has-capability? "graph/x" "read") (+ n 1) 0))"#,
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :auth-check
                           :source "src/auth.clj"
                           :safe true
                           :exports [run]
                           :imports []}]
             :capabilities {:notify/show {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        assert_eq!(
            plan.components[0].capability_surface,
            vec!["kotoba:kais/auth@0.1.0"]
        );

        let granted = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("auth-check".to_string()),
                function: Some("run".to_string()),
                args: vec![41],
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: vec!["graph/x:read".to_string()],
                kqe_snapshot: Vec::new(),
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        assert_eq!(granted.status, SdkCheckStatus::Passed);
        assert_eq!(granted.dry_run.unwrap().result, Some(42));

        let denied = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("auth-check".to_string()),
                function: Some("run".to_string()),
                args: vec![41],
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: Vec::new(),
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        assert_eq!(denied.status, SdkCheckStatus::Passed);
        assert_eq!(denied.dry_run.unwrap().result, Some(0));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_check_runs_kqe_write_host_bound_safe_component() {
        let root = unique_test_dir("supervisor-kqe");
        std::fs::create_dir_all(root.join("src")).unwrap();
        std::fs::write(
            root.join("src/kqe.clj"),
            r#"(defn run [] (kqe-assert! "graphA" "alice" "kg/name" "Ada"))"#,
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :kqe-writer
                           :source "src/kqe.clj"
                           :safe true
                           :exports [run]
                           :imports []}]
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        assert_eq!(
            plan.components[0].capability_surface,
            vec!["kotoba:kais/kqe@0.1.0"]
        );

        let report = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("kqe-writer".to_string()),
                function: Some("run".to_string()),
                args: Vec::new(),
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: Vec::new(),
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        assert_eq!(report.status, SdkCheckStatus::Passed);
        let dry_run = report.dry_run.unwrap();
        assert_eq!(dry_run.result, Some(1));
        assert_eq!(dry_run.host_events.len(), 1);
        assert_eq!(dry_run.host_events[0].operation, "assert-quad");
        assert_eq!(dry_run.host_events[0].graph, "graphA");
        assert_eq!(dry_run.host_events[0].subject, "alice");
        assert_eq!(dry_run.host_events[0].predicate, "kg/name");
        assert_eq!(dry_run.host_events[0].object, "Ada");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_check_runs_kqe_read_query_host_bound_safe_component() {
        let root = unique_test_dir("supervisor-kqe-read");
        std::fs::create_dir_all(root.join("src")).unwrap();
        std::fs::write(
            root.join("src/kqe_read.clj"),
            r#"
            (defn read-count []
              (kqe-count (kqe-get-objects "graphA" "alice" "kg/name")))
            (defn query-count []
              (kqe-count (kqe-query "")))
            "#,
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :kqe-reader
                           :source "src/kqe_read.clj"
                           :safe true
                           :exports [read-count query-count]
                           :imports []}]
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        let snapshot = vec![
            ComponentKqeQuad {
                graph: "graphA".to_string(),
                subject: "alice".to_string(),
                predicate: "kg/name".to_string(),
                object: "Ada".to_string(),
            },
            ComponentKqeQuad {
                graph: "graphA".to_string(),
                subject: "alice".to_string(),
                predicate: "kg/role".to_string(),
                object: "admin".to_string(),
            },
        ];

        let read = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("kqe-reader".to_string()),
                function: Some("read-count".to_string()),
                args: Vec::new(),
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: snapshot.clone(),
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        let read_dry_run = read.dry_run.unwrap();
        assert_eq!(read_dry_run.result, Some(1));
        assert_eq!(read_dry_run.host_events[0].operation, "get-objects");

        let query = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("kqe-reader".to_string()),
                function: Some("query-count".to_string()),
                args: Vec::new(),
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: snapshot,
                llm_echo: false,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        let query_dry_run = query.dry_run.unwrap();
        assert_eq!(query_dry_run.result, Some(2));
        assert_eq!(query_dry_run.host_events[0].operation, "query");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_check_runs_llm_host_bound_safe_component() {
        let root = unique_test_dir("supervisor-llm");
        std::fs::create_dir_all(root.join("src")).unwrap();
        std::fs::write(
            root.join("src/llm.clj"),
            r#"(defn reply-len [] (str-len (llm-infer "modelA" "ping")))"#,
        )
        .unwrap();
        let manifest = parse_manifest(
            r#"
            {:kotoba.app/id "jp.co.gftd.demo"
             :kotoba.app/name "demo"
             :components [{:id :llm-agent
                           :source "src/llm.clj"
                           :safe true
                           :exports [reply-len]
                           :imports []}]
             :capabilities {:ledger/append {:platforms #{:macos :ios :android}}}
             :targets #{:macos :ios :android}}
            "#,
        )
        .unwrap();
        let plan = plan_manifest(root.join("app.kotoba.edn"), &root, manifest).unwrap();
        assert_eq!(
            plan.components[0].capability_surface,
            vec!["kotoba:kais/llm@0.1.0"]
        );
        let report = supervisor_check_plan(
            &plan,
            Target::Android,
            Some(ComponentDryRunRequest {
                component: Some("llm-agent".to_string()),
                function: Some("reply-len".to_string()),
                args: Vec::new(),
                fuel: 1_000_000,
                host_adapter_manifest: None,
                adapter_timeout_seconds: 10,
                auth_grants: Vec::new(),
                kqe_snapshot: Vec::new(),
                llm_echo: true,
                llm_responses: Vec::new(),
            }),
        )
        .unwrap();
        let dry_run = report.dry_run.unwrap();
        assert_eq!(dry_run.result, Some(9));
        assert_eq!(dry_run.host_events.len(), 1);
        assert_eq!(dry_run.host_events[0].operation, "infer");
        assert_eq!(dry_run.host_events[0].graph, "modelA");
        assert_eq!(dry_run.host_events[0].subject, "ping");
        assert_eq!(dry_run.host_events[0].object, "echo:ping");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn supervisor_host_can_call_live_llm_adapter() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}", listener.local_addr().unwrap());
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut buf = [0; 4096];
            let n = stream.read(&mut buf).unwrap();
            let request = String::from_utf8_lossy(&buf[..n]);
            assert!(request.contains("llm.infer"));
            let body = br#"{"output":"live:pong"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: {}\r\n\r\n",
                body.len()
            )
            .unwrap();
            stream.write_all(body).unwrap();
        });
        let body = r#"(defn reply-len [] (str-len (llm-infer "modelA" "ping")))"#;
        let policy = kotoba_clj::minimal_policy(body).unwrap();
        let wasm = kotoba_clj::compile_safe_clj_with_prelude(body, &policy).unwrap();
        let live_adapters = SupervisorLiveAdapters {
            urls: BTreeMap::from([("llm".to_string(), url)]),
            timeout: Duration::from_secs(2),
        };

        let (result, events) = run_with_supervisor_hosts(
            &wasm,
            "reply-len",
            &[],
            1_000_000,
            Some(live_adapters),
            &[],
            &[],
            false,
            &[],
        )
        .unwrap();

        assert_eq!(result, 9);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].operation, "infer");
        assert_eq!(events[0].graph, "live-adapter");
        assert_eq!(events[0].object, "live:pong");
        server.join().unwrap();
    }

    #[test]
    fn android_package_name_is_java_identifier_safe() {
        assert_eq!(
            android_package_name("jp.co.gftd.kotoba-shell.hello"),
            "jp.co.gftd.kotoba_shell.hello"
        );
        assert_eq!(android_package_name("1.demo"), "_1.demo");
    }

    #[test]
    fn parses_first_ios_simulator_udid_from_simctl_output() {
        let output = r#"
== Devices ==
-- iOS 26.2 --
    iPhone 17 Pro (7B36C133-5F7C-4042-90C0-11B286BE692C) (Shutdown)
    iPad mini (A17 Pro) (9C162460-7344-4DFD-B833-8CADF6DD251A) (Shutdown)
-- visionOS 26.2 --
    Apple Vision Pro (76537197-99D9-4458-8D9D-3FCEF839BF8A) (Shutdown)
"#;
        assert_eq!(
            parse_first_ios_simulator_udid(output).as_deref(),
            Some("7B36C133-5F7C-4042-90C0-11B286BE692C")
        );
    }

    #[test]
    fn parses_ios_runtime_and_device_type_ids() {
        let runtimes = r#"
== Runtimes ==
iOS 26.2 (26.2 - 23C54) - com.apple.CoreSimulator.SimRuntime.iOS-26-2
visionOS 26.2 (26.2 - 23N301) - com.apple.CoreSimulator.SimRuntime.xrOS-26-2
"#;
        let device_types = r#"
== Device Types ==
iPhone 17 Pro (com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro)
iPad Pro 13-inch (M5) (com.apple.CoreSimulator.SimDeviceType.iPad-Pro-13-inch-M5-12GB)
"#;
        assert_eq!(
            parse_first_ios_runtime_id(runtimes).as_deref(),
            Some("com.apple.CoreSimulator.SimRuntime.iOS-26-2")
        );
        assert_eq!(
            parse_first_iphone_device_type_id(device_types).as_deref(),
            Some("com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro")
        );
    }

    #[test]
    fn parses_first_android_avd_name() {
        assert_eq!(
            parse_first_android_avd("\nMedium_Phone_API_36.1\nPixel_API_35\n").as_deref(),
            Some("Medium_Phone_API_36.1")
        );
        assert_eq!(parse_first_android_avd("\n\n"), None);
    }

    #[test]
    fn parses_only_valid_avdmanager_entries() {
        let valid = r#"
Available Android Virtual Devices:
    Name: Pixel_API_35
    Path: /Users/demo/.android/avd/Pixel_API_35.avd
  Target: Google APIs (Google Inc.)
          Based on: Android 35.0

The following Android Virtual Devices could not be loaded:
    Name: Broken_API_36
    Path: /Users/demo/.android/avd/Broken_API_36.avd
   Error: Missing system image.
"#;
        let invalid_only = r#"
Available Android Virtual Devices:

The following Android Virtual Devices could not be loaded:
    Name: Broken_API_36
    Path: /Users/demo/.android/avd/Broken_API_36.avd
   Error: Missing system image.
"#;
        assert_eq!(
            parse_first_valid_android_avd_from_avdmanager(valid).as_deref(),
            Some("Pixel_API_35")
        );
        assert_eq!(
            parse_first_valid_android_avd_from_avdmanager(invalid_only),
            None
        );
        assert_eq!(
            parse_first_invalid_android_avd_reason(invalid_only).as_deref(),
            Some("Broken_API_36: Missing system image.")
        );
    }

    #[test]
    fn parses_android_system_image_package_from_avd_config() {
        let config = r#"
AvdId=Medium_Phone_API_36.1
image.sysdir.1=system-images/android-36.1/google_apis_playstore/arm64-v8a/
"#;
        assert_eq!(
            android_system_image_package_from_config(config).as_deref(),
            Some("system-images;android-36.1;google_apis_playstore;arm64-v8a")
        );
    }

    #[test]
    fn runtime_doctor_remediation_mentions_android_system_image_repair() {
        let remediation = runtime_doctor_remediation(
            Target::Android,
            &["Medium_Phone_API_36.1: Missing system image for Google Play arm64-v8a Medium Phone API 36.1.; install with `sdkmanager \"system-images;android-36.1;google_apis_playstore;arm64-v8a\"`".to_string()],
        );
        assert!(remediation.iter().any(|item| item.contains(
            "sdkmanager \"system-images;android-36.1;google_apis_playstore;arm64-v8a\""
        )));
        assert!(remediation
            .iter()
            .any(|item| item.contains("avdmanager list avd")));
        let commands = runtime_doctor_remediation_commands(
            Target::Android,
            &["Medium_Phone_API_36.1: Missing system image for Google Play arm64-v8a Medium Phone API 36.1.; install with `sdkmanager \"system-images;android-36.1;google_apis_playstore;arm64-v8a\"`".to_string()],
        );
        assert!(commands.contains(&vec![
            "sdkmanager".to_string(),
            "system-images;android-36.1;google_apis_playstore;arm64-v8a".to_string()
        ]));
        assert!(commands.contains(&vec![
            "avdmanager".to_string(),
            "list".to_string(),
            "avd".to_string()
        ]));

        let boot_probe_commands = runtime_doctor_remediation_commands(
            Target::Android,
            &["Android AVD boot probe failed for Medium_Phone_API_36.1: ERROR | No initial system image for this configuration!; reinstall with `sdkmanager --uninstall \"system-images;android-36.1;google_apis_playstore;arm64-v8a\"` then `sdkmanager \"system-images;android-36.1;google_apis_playstore;arm64-v8a\"`, or recreate the AVD".to_string()],
        );
        assert!(boot_probe_commands.contains(&vec![
            "sdkmanager".to_string(),
            "--uninstall".to_string(),
            "system-images;android-36.1;google_apis_playstore;arm64-v8a".to_string()
        ]));
        assert!(boot_probe_commands.contains(&vec![
            "sdkmanager".to_string(),
            "system-images;android-36.1;google_apis_playstore;arm64-v8a".to_string()
        ]));
    }

    fn unique_test_dir(name: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!(
            "kotoba-shell-{name}-{}-{nanos}",
            std::process::id()
        ))
    }
}
