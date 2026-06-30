//! `kotoba shell` — kotoba-shell app manifest checks and native build planning.

use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result};
use clap::Subcommand;

#[derive(Subcommand)]
pub enum ShellCmd {
    /// Print kotoba-shell maturity and Tauri-baseline coverage.
    Coverage {
        /// Print the coverage assessment as JSON.
        #[arg(long)]
        json: bool,
        /// Print the coverage assessment as EDN.
        #[arg(long)]
        edn: bool,
        /// Write the coverage assessment as JSON or EDN evidence, based on extension.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify kotoba-shell coverage against minimum promotion thresholds.
    CoverageCheck {
        /// Minimum Tauri-baseline functional coverage percentage.
        #[arg(long, default_value_t = 70)]
        min_functional: u8,
        /// Minimum release maturity percentage.
        #[arg(long, default_value_t = 45)]
        min_release_maturity: u8,
        /// Write the coverage threshold report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Parse a kotoba-shell manifest and run safe component admission.
    Check {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
    },

    /// Print the resolved kotoba-shell plan, including minimal safe Kotoba policy.
    Plan {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
    },

    /// Launch a local macOS WKWebView dev shell after safe component admission.
    Dev {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform. Only macos is implemented for dev.
        #[arg(long, default_value = "macos")]
        target: String,
        /// Generate dev runtime files but do not launch the native window.
        #[arg(long)]
        dry_run: bool,
        /// Output directory for generated dev runtime files.
        #[arg(long, default_value = "target/kotoba-shell/dev")]
        out_dir: PathBuf,
    },

    /// Native packaging entry point. Currently records the target boundary.
    Build {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Codesign the macOS app bundle after building.
        #[arg(long)]
        sign: bool,
        /// Codesign identity. Use "-" for ad-hoc local signing.
        #[arg(long, default_value = "-")]
        sign_identity: String,
    },

    /// Export release review/notarization metadata for a target.
    Export {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Output directory for release metadata.
        #[arg(long, default_value = "target/kotoba-shell/release")]
        out_dir: PathBuf,
    },

    /// Verify a built shell artifact or generated mobile project.
    Verify {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long, default_value = "macos")]
        target: String,
        /// Path to a built `.app` bundle or generated mobile project.
        path: PathBuf,
    },

    /// Run target SDK compiler checks when the native SDK toolchain is available.
    SdkCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to a generated mobile project.
        path: PathBuf,
        /// Maximum seconds to wait for the SDK compiler command.
        #[arg(long, default_value_t = 300)]
        timeout_seconds: u64,
        /// Write the SDK check report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Install and launch a generated app on a connected device/simulator when available.
    RuntimeCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to a generated mobile project.
        path: PathBuf,
        /// Android AVD name to boot when no device/emulator is already connected.
        #[arg(long)]
        avd: Option<String>,
        /// Maximum seconds to wait for the runtime smoke command.
        #[arg(long, default_value_t = 120)]
        timeout_seconds: u64,
        /// Write the runtime check report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Diagnose target runtime prerequisites without launching an app.
    DoctorCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Android AVD name to probe.
        #[arg(long)]
        avd: Option<String>,
        /// Start a short runtime boot probe when supported by the target.
        #[arg(long)]
        probe: bool,
        /// Maximum seconds to wait for the doctor probe.
        #[arg(long, default_value_t = 120)]
        timeout_seconds: u64,
        /// Write the doctor report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify runtime doctor and launch evidence as one release gate.
    RuntimeReleaseCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to `<target>-runtime-doctor-evidence.json`.
        #[arg(long)]
        doctor_evidence: PathBuf,
        /// Path to `<target>-runtime-evidence.json`.
        #[arg(long)]
        runtime_evidence: PathBuf,
        /// Write the combined runtime release report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify multiple runtime-ready evidence files as one device/runtime matrix gate.
    RuntimeMatrixCheck {
        /// Required target platform. Repeat for iOS + Android matrix checks.
        #[arg(long = "require-target")]
        require_targets: Vec<String>,
        /// Minimum number of distinct runtime environments required.
        #[arg(long, default_value_t = 1)]
        min_distinct_runtimes: usize,
        /// Write the runtime matrix report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Runtime release evidence files produced by runtime-release-check.
        runtime_ready_evidence: Vec<PathBuf>,
    },

    /// Verify hosted device-farm runtime evidence from a runtime matrix report.
    DeviceFarmCheck {
        /// Required target platform. Repeat for iOS + Android device-farm checks.
        #[arg(long = "require-target")]
        require_targets: Vec<String>,
        /// Minimum number of distinct runtime environments required.
        #[arg(long, default_value_t = 2)]
        min_distinct_runtimes: usize,
        /// Device-farm provider name.
        #[arg(long)]
        provider: String,
        /// Hosted HTTPS URL for the device-farm run/result page.
        #[arg(long)]
        run_url: String,
        /// Runtime matrix evidence produced by runtime-matrix-check.
        #[arg(long)]
        runtime_matrix_evidence: PathBuf,
        /// Write the device-farm report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify generated Windows WebView2 host runtime launch/readiness contract.
    WindowsRuntimeContractCheck {
        /// Generated Windows project directory.
        path: PathBuf,
        /// Write the Windows runtime contract report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify generated native host bridge contract against the shipped Kotoba oracle.
    NativeHostContractCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the native host contract report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Generated project, app bundle, or release artifact directory.
        path: PathBuf,
    },

    /// Verify exported release metadata, helper scripts, and signing credential readiness.
    ReleaseCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the release metadata report as JSON evidence for release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `target/kotoba-shell/release/<target>/<app-name>`.
        path: PathBuf,
    },

    /// Verify and optionally execute target production signing helpers.
    SigningCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Execute the target signing helper script.
        #[arg(long)]
        execute: bool,
        /// App bundle or generated native project path passed to the signing helper.
        #[arg(long)]
        artifact: Option<PathBuf>,
        /// Optional signed output artifact path for iOS/Android helpers.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Maximum seconds to wait for signing helper execution.
        #[arg(long, default_value_t = 300)]
        timeout_seconds: u64,
        /// Write the signing report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `target/kotoba-shell/release/<target>/<app-name>`.
        path: PathBuf,
    },

    /// Verify and optionally execute notarization/store submission helpers.
    SubmissionCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Execute supported target submission helper scripts.
        #[arg(long)]
        execute: bool,
        /// App bundle or signed artifact path passed to supported helpers.
        #[arg(long)]
        artifact: Option<PathBuf>,
        /// Optional output path passed to supported helpers.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Maximum seconds to wait for submission helper execution.
        #[arg(long, default_value_t = 300)]
        timeout_seconds: u64,
        /// Write the submission report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `target/kotoba-shell/release/<target>/<app-name>`.
        path: PathBuf,
    },

    /// Verify credential-backed signing/submission evidence was actually executed.
    CredentialExecutionCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Execution kind: signing | submission.
        #[arg(long)]
        kind: String,
        /// Path to signing-check or submission-check evidence JSON.
        #[arg(long)]
        source_evidence: PathBuf,
        /// Artifact that the executed helper must reference.
        #[arg(long)]
        artifact: Option<PathBuf>,
        /// Output that the executed helper must reference.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Write the credential execution report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify capability declarations are linked to provider command contracts.
    ProviderContractCheck {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Use shipped provider/surface policy kototama oracle manifest instead of compiling it.
        #[arg(long = "provider-oracle-manifest")]
        provider_oracle_manifest: Option<PathBuf>,
        /// Write the provider contract report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify generated plugin registry contracts for provider plugins.
    PluginCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the plugin contract report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-plugins.json`.
        path: PathBuf,
    },

    /// Verify external plugin SDK compatibility metadata.
    PluginSdkCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the plugin SDK report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-plugin-sdk.json`.
        path: PathBuf,
    },

    /// Verify external plugin bundle loader admission metadata.
    PluginLoadCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the plugin load report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-plugin-bundles.json`.
        path: PathBuf,
    },

    /// Verify shell/plugin/schema compatibility policy metadata.
    CompatibilityCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the compatibility policy report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-compatibility.json`.
        path: PathBuf,
    },

    /// Verify old/new compatibility manifests preserve migration guarantees.
    CompatibilityMigrationCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Previous `kotoba-shell-compatibility.json`.
        #[arg(long)]
        previous: PathBuf,
        /// Current `kotoba-shell-compatibility.json`.
        #[arg(long)]
        current: PathBuf,
        /// Write the compatibility migration report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify the generated app surface contract for window/menu/tray/lifecycle coverage.
    SurfaceCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Use shipped provider/surface policy kototama oracle manifest for surface evidence.
        #[arg(long = "provider-oracle-manifest")]
        provider_oracle_manifest: Option<PathBuf>,
        /// Write the app surface report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-app-surface.json`.
        path: PathBuf,
    },

    /// Verify app surface bridge and provider command parity across targets.
    SurfaceParityCheck {
        /// Require specific targets to be present in the parity set.
        #[arg(long = "require-target")]
        require_targets: Vec<String>,
        /// Use shipped provider/surface policy kototama oracle manifest for parity evidence.
        #[arg(long = "provider-oracle-manifest")]
        provider_oracle_manifest: Option<PathBuf>,
        /// Write the app surface parity report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Paths to target `kotoba-shell-app-surface.json` manifests.
        paths: Vec<PathBuf>,
    },

    /// Aggregate EDN/JSON evidence reports and verify required pass evidence.
    EvidenceCheck {
        /// Evidence directory containing EDN/JSON reports.
        path: PathBuf,
        /// Require a named evidence EDN/JSON file to have status Passed.
        #[arg(long = "require-passed")]
        require_passed: Vec<String>,
        /// Apply a built-in required evidence profile: ci | android-release | store-release.
        #[arg(long = "profile")]
        profiles: Vec<String>,
        /// Read profile requirements from `kotoba-shell-evidence-profile.edn` or `.json`.
        #[arg(long)]
        profile_file: Option<PathBuf>,
        /// Write the evidence aggregation report as EDN or JSON, based on extension.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify generated evidence profile metadata against the Kotoba selfhost EDN seed.
    SelfhostProfileCheck {
        /// Path to `kotoba-shell-evidence-profile.edn` or `.json`.
        profile: PathBuf,
        /// Use shipped shell evidence profile Kototama oracle manifest.
        #[arg(long = "profile-oracle-manifest")]
        profile_oracle_manifest: Option<PathBuf>,
        /// Write the selfhost profile parity report as JSON or EDN evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify the safe Kotoba selfhost seed compiles and runs as confined Wasm.
    KototamaWasmCheck {
        /// Optional `kototama-selfhost-analyzer.edn` or `.json` release manifest to verify.
        manifest: Option<PathBuf>,
        /// Write the kototama Wasm readiness report as JSON or EDN evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify shipped app safe components were compiled to kototama Wasm artifacts.
    KototamaAppComponentsCheck {
        /// Path to `kototama-app-components.edn` or `.json`.
        manifest: PathBuf,
        /// Write the app component artifact report as JSON or EDN evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify production host service adapter manifest and environment readiness.
    AdapterCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Probe configured adapter endpoint URLs with curl.
        #[arg(long)]
        probe: bool,
        /// POST a contract smoke request to configured adapter endpoint URLs.
        #[arg(long)]
        smoke: bool,
        /// Require configured adapter URLs to be hosted public HTTPS endpoints.
        #[arg(long)]
        hosted: bool,
        /// Maximum seconds to wait for each adapter probe.
        #[arg(long, default_value_t = 10)]
        timeout_seconds: u64,
        /// Write the adapter check report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-host-adapters.json`.
        path: PathBuf,
    },

    /// Verify hosted adapter readiness and live supervisor evidence as one release gate.
    AdapterSupervisorCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to `hosted-adapter-ready-evidence.json`.
        #[arg(long)]
        adapter_evidence: PathBuf,
        /// Path to `live-adapter-supervisor-evidence.json`.
        #[arg(long)]
        supervisor_evidence: PathBuf,
        /// Write the combined adapter/supervisor report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify updater manifest integrity and publish readiness.
    UpdaterCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the updater check report as JSON evidence for release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-updater-manifest.json`.
        path: PathBuf,
    },

    /// Verify updater channel, rollback, rollout, and signature policy.
    UpdaterChannelCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the updater channel report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-updater-channel.json`.
        path: PathBuf,
    },

    /// Verify updater UI states, bridge events, and native binding contract.
    UpdaterUiCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Write the updater UI contract report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
        /// Path to `kotoba-shell-updater-ui.json`.
        path: PathBuf,
    },

    /// Verify updater artifact URL is public HTTPS and reachable.
    UpdaterPublicationCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to updater-ready-evidence.json.
        #[arg(long)]
        updater_evidence: PathBuf,
        /// Maximum seconds to wait for the publication probe.
        #[arg(long, default_value_t = 10)]
        timeout_seconds: u64,
        /// Write the updater publication report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify updater feed body matches the release updater manifest.
    UpdaterFeedCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to updater-ready-evidence.json.
        #[arg(long)]
        updater_evidence: PathBuf,
        /// Local feed manifest body to verify.
        #[arg(long)]
        feed_file: Option<PathBuf>,
        /// Hosted HTTPS feed URL to fetch and verify.
        #[arg(long)]
        feed_url: Option<String>,
        /// Maximum seconds to wait for the feed fetch.
        #[arg(long, default_value_t = 10)]
        timeout_seconds: u64,
        /// Write the updater feed report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify updater artifact hash, signature, and public HTTPS URL shape before publication probe.
    UpdaterBundleCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to updater-ready-evidence.json.
        #[arg(long)]
        updater_evidence: PathBuf,
        /// Write the updater bundle report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify updater artifact local download and install staging with sha256 checks.
    UpdaterInstallCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to updater-ready-evidence.json.
        #[arg(long)]
        updater_evidence: PathBuf,
        /// Directory used for download and install staging.
        #[arg(long)]
        staging_dir: PathBuf,
        /// Write the updater install report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Fill updater manifest artifact file, sha256, URL, and signature.
    UpdaterFinalize {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to `kotoba-shell-updater-manifest.json`.
        manifest: PathBuf,
        /// Path to the published artifact file.
        #[arg(long)]
        artifact: PathBuf,
        /// Public URL where the artifact will be fetched.
        #[arg(long)]
        url: String,
        /// Detached artifact signature text.
        #[arg(long, conflicts_with = "signature_file")]
        signature: Option<String>,
        /// File containing detached artifact signature text.
        #[arg(long)]
        signature_file: Option<PathBuf>,
    },

    /// Verify local aiueos ledger JSONL replay/replication evidence.
    LedgerReplayCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Source append-only ledger JSONL.
        #[arg(long)]
        source: PathBuf,
        /// Replica JSONL path to write and verify.
        #[arg(long)]
        replica: PathBuf,
        /// Write the ledger replay report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify hosted remote ledger replication endpoint readiness.
    LedgerRemoteCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Source append-only ledger JSONL.
        #[arg(long)]
        source: PathBuf,
        /// Remote ledger replication endpoint URL.
        #[arg(long)]
        endpoint: String,
        /// Require endpoint to be public HTTPS.
        #[arg(long)]
        hosted: bool,
        /// Probe endpoint with HEAD.
        #[arg(long)]
        probe: bool,
        /// Maximum seconds to wait for endpoint probe.
        #[arg(long, default_value_t = 10)]
        timeout_seconds: u64,
        /// Write the ledger remote report as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Verify aiueos shell broker admission and optionally dry-dispatch a command.
    BrokerCheck {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Optional shell command to dry-run through the broker.
        #[arg(long)]
        command: Option<String>,
        /// Append dry-run audit event to a JSONL file.
        #[arg(long)]
        audit_log: Option<PathBuf>,
    },

    /// Verify aiueos component supervisor plan and optionally run a pure safe component.
    SupervisorCheck {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Execute a pure safe Kotoba component export under fuel.
        #[arg(long)]
        run: bool,
        /// Component id to run. Defaults to the first safe component.
        #[arg(long)]
        component: Option<String>,
        /// Exported function to run. Defaults to the first declared export or `run`.
        #[arg(long)]
        function: Option<String>,
        /// i64 argument passed to the exported function. Repeat for multiple args.
        #[arg(long = "arg")]
        args: Vec<i64>,
        /// Wasmtime fuel budget for pure component dry-run.
        #[arg(long, default_value_t = 1_000_000)]
        fuel: u64,
        /// Use shipped kototama app component artifacts instead of recompiling source.
        #[arg(long = "kototama-app-components")]
        kototama_app_components: Option<PathBuf>,
        /// Use live production host adapters from `kotoba-shell-host-adapters.json`.
        #[arg(long)]
        adapter_manifest: Option<PathBuf>,
        /// Maximum seconds to wait for each live adapter call.
        #[arg(long, default_value_t = 10)]
        adapter_timeout_seconds: u64,
        /// Grant an auth capability to host-bound dry-run, formatted as resource:ability.
        #[arg(long = "auth-grant")]
        auth_grants: Vec<String>,
        /// Seed a kqe snapshot quad, formatted as graph,subject,predicate,object.
        #[arg(long = "kqe-quad")]
        kqe_quads: Vec<String>,
        /// Echo llm prompt as `echo:<prompt>` for host-bound dry-run.
        #[arg(long)]
        llm_echo: bool,
        /// Seed an llm response, formatted as model,response.
        #[arg(long = "llm-response")]
        llm_responses: Vec<String>,
        /// Write the supervisor report as JSON evidence for CI/release gates.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },
}

pub fn run(cmd: ShellCmd) -> Result<()> {
    match cmd {
        ShellCmd::Coverage {
            json,
            edn,
            evidence,
        } => {
            let assessment = kotoba_shell::coverage_assessment();
            write_json_evidence(evidence.as_ref(), &assessment)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&assessment)?);
            } else if edn {
                println!("{}", kotoba_shell::evidence_edn_string(&assessment)?);
            } else {
                print!("{}", kotoba_shell::coverage_report());
                if let Some(evidence) = &evidence {
                    println!("evidence: {}", evidence.display());
                }
            }
            Ok(())
        }
        ShellCmd::CoverageCheck {
            min_functional,
            min_release_maturity,
            evidence,
        } => {
            let report = kotoba_shell::coverage_check(min_functional, min_release_maturity);
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            println!(
                "functional coverage: {}% (min {}%)",
                report.functional_coverage_percent, report.min_functional_coverage_percent
            );
            println!(
                "release maturity: {}% (min {}%)",
                report.release_maturity_percent, report.min_release_maturity_percent
            );
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing:");
                for item in report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("coverage check failed"),
            }
        }
        ShellCmd::Check { manifest } => {
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("check {}", manifest.display()))?;
            println!(
                "ok: {} ({}) — {} component(s) admitted/declared",
                plan.app_name,
                plan.app_id,
                plan.components.len()
            );
            Ok(())
        }
        ShellCmd::Plan { manifest } => {
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("plan {}", manifest.display()))?;
            print!("{}", kotoba_shell::format_plan(&plan));
            Ok(())
        }
        ShellCmd::Dev {
            manifest,
            target,
            dry_run,
            out_dir,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            if target != kotoba_shell::Target::Macos {
                anyhow::bail!("kotoba shell dev currently supports only --target macos");
            }
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("dev {}", manifest.display()))?;
            let session = kotoba_shell::prepare_dev_session(&plan, out_dir)?;
            println!("dev runtime: {}", session.dir.display());
            println!("index: {}", session.index_html.display());
            println!("runner: {}", session.swift_runner.display());
            if dry_run {
                return Ok(());
            }
            kotoba_shell::run_macos_dev(&session)
        }
        ShellCmd::Build {
            manifest,
            target,
            sign,
            sign_identity,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("build {}", manifest.display()))?;
            let artifact = kotoba_shell::build_target(&plan, target)?;
            println!("target: {}", artifact.target.as_str());
            println!("project: {}", artifact.project_dir.display());
            println!("app bundle: {}", artifact.app_bundle.display());
            println!("executable: {}", artifact.executable.display());
            println!("release manifest: {}", artifact.release_manifest.display());
            if sign {
                if artifact.target != kotoba_shell::Target::Macos {
                    anyhow::bail!("--sign is currently supported only for --target macos");
                }
                let report = kotoba_shell::sign_macos_app(&artifact.app_bundle, &sign_identity)?;
                println!(
                    "codesign: {}",
                    if report.signed { "verified" } else { "failed" }
                );
            }
            Ok(())
        }
        ShellCmd::Export {
            manifest,
            target,
            out_dir,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("export {}", manifest.display()))?;
            let artifact = kotoba_shell::export_release_artifacts(&plan, target, out_dir)?;
            println!("target: {}", artifact.target.as_str());
            println!("export: {}", artifact.dir.display());
            println!("release manifest: {}", artifact.release_manifest.display());
            Ok(())
        }
        ShellCmd::Verify { target, path } => {
            let target = kotoba_shell::Target::parse(&target)?;
            match target {
                kotoba_shell::Target::Macos => {
                    let report = kotoba_shell::verify_macos_signature(&path)?;
                    if report.signed {
                        println!("codesign verified: {}", report.app_bundle.display());
                        Ok(())
                    } else {
                        anyhow::bail!(
                            "codesign verification failed: {}",
                            report.app_bundle.display()
                        )
                    }
                }
                kotoba_shell::Target::Ios
                | kotoba_shell::Target::Android
                | kotoba_shell::Target::Windows => {
                    let report = kotoba_shell::verify_generated_project(target, &path)?;
                    println!("target: {}", report.target.as_str());
                    println!("project verified: {}", report.project_dir.display());
                    for check in report.checks {
                        println!("  ok: {check}");
                    }
                    Ok(())
                }
            }
        }
        ShellCmd::SdkCheck {
            target,
            path,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::sdk_check_project(
                target,
                &path,
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("project: {}", report.project_dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            if !report.command.is_empty() {
                println!("command: {}", report.command.join(" "));
            }
            println!("detail: {}", report.detail);
            print_tail("stdout", &report.stdout);
            print_tail("stderr", &report.stderr);
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("SDK check failed"),
            }
        }
        ShellCmd::RuntimeCheck {
            target,
            path,
            avd,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::runtime_check_project_with_options(
                target,
                &path,
                Duration::from_secs(timeout_seconds),
                avd.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("project: {}", report.project_dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            if !report.command.is_empty() {
                println!("command: {}", report.command.join(" "));
            }
            println!("detail: {}", report.detail);
            print_tail("stdout", &report.stdout);
            print_tail("stderr", &report.stderr);
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("runtime check failed"),
            }
        }
        ShellCmd::RuntimeReleaseCheck {
            target,
            doctor_evidence,
            runtime_evidence,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::runtime_release_evidence_check(
                target,
                &doctor_evidence,
                &runtime_evidence,
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("doctor-evidence: {}", report.doctor_evidence.display());
            println!("runtime-evidence: {}", report.runtime_evidence.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing runtime release evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("runtime release check failed")
                }
            }
        }
        ShellCmd::RuntimeMatrixCheck {
            require_targets,
            min_distinct_runtimes,
            evidence,
            runtime_ready_evidence,
        } => {
            let required_targets = require_targets
                .iter()
                .map(|target| kotoba_shell::Target::parse(target))
                .collect::<Result<Vec<_>>>()?;
            let report = kotoba_shell::runtime_matrix_evidence_check(
                &required_targets,
                min_distinct_runtimes,
                &runtime_ready_evidence,
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for target in &report.targets {
                println!("target: {}", target.as_str());
            }
            for runtime in &report.runtimes {
                println!("runtime: {runtime}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing runtime matrix evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("runtime matrix check failed")
                }
            }
        }
        ShellCmd::DeviceFarmCheck {
            require_targets,
            min_distinct_runtimes,
            provider,
            run_url,
            runtime_matrix_evidence,
            evidence,
        } => {
            let required_targets = require_targets
                .iter()
                .map(|target| kotoba_shell::Target::parse(target))
                .collect::<Result<Vec<_>>>()?;
            let report = kotoba_shell::device_farm_evidence_check(
                &required_targets,
                min_distinct_runtimes,
                &provider,
                &run_url,
                &runtime_matrix_evidence,
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("provider: {}", report.provider);
            println!("run-url: {}", report.run_url);
            println!(
                "runtime-matrix-evidence: {}",
                report.runtime_matrix_evidence.display()
            );
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for target in &report.targets {
                println!("target: {}", target.as_str());
            }
            for runtime in &report.runtimes {
                println!("runtime: {runtime}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing device-farm evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("device-farm check failed")
                }
            }
        }
        ShellCmd::WindowsRuntimeContractCheck { path, evidence } => {
            let report = kotoba_shell::windows_runtime_contract_check(&path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("project: {}", report.project_dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing Windows runtime contract evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("Windows runtime contract check failed")
                }
            }
        }
        ShellCmd::NativeHostContractCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::native_host_contract_check(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("dir: {}", report.dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing native host contract evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("native host contract check failed")
                }
            }
        }
        ShellCmd::DoctorCheck {
            target,
            avd,
            probe,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::runtime_doctor_check_with_probe_and_options(
                target,
                probe,
                Duration::from_secs(timeout_seconds),
                avd.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing:");
                for item in report.missing {
                    println!("  - {item}");
                }
            }
            if !report.remediation.is_empty() {
                println!("remediation:");
                for item in report.remediation {
                    println!("  - {item}");
                }
            }
            if !report.remediation_commands.is_empty() {
                println!("remediation commands:");
                for command in report.remediation_commands {
                    println!("  - {}", command.join(" "));
                }
            }
            if !report.command.is_empty() {
                println!("command: {}", report.command.join(" "));
            }
            print_tail("stdout", &report.stdout);
            print_tail("stderr", &report.stderr);
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("doctor check failed"),
            }
        }
        ShellCmd::ReleaseCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::release_check_artifacts(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("release: {}", report.dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing_credentials.is_empty() {
                println!("missing credentials:");
                for env in report.missing_credentials {
                    println!("  - {env}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("release check failed"),
            }
        }
        ShellCmd::SigningCheck {
            target,
            execute,
            artifact,
            output,
            timeout_seconds,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::signing_check_artifacts(
                target,
                &path,
                execute,
                artifact.as_deref(),
                output.as_deref(),
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("release: {}", report.dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            if !report.command.is_empty() {
                println!("command: {}", report.command.join(" "));
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing_credentials.is_empty() {
                println!("missing credentials:");
                for env in report.missing_credentials {
                    println!("  - {env}");
                }
            }
            print_tail("stdout", &report.stdout);
            print_tail("stderr", &report.stderr);
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("signing check failed"),
            }
        }
        ShellCmd::SubmissionCheck {
            target,
            execute,
            artifact,
            output,
            timeout_seconds,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::submission_check_artifacts(
                target,
                &path,
                execute,
                artifact.as_deref(),
                output.as_deref(),
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("release: {}", report.dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            if !report.command.is_empty() {
                println!("command: {}", report.command.join(" "));
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing_credentials.is_empty() {
                println!("missing credentials:");
                for env in report.missing_credentials {
                    println!("  - {env}");
                }
            }
            print_tail("stdout", &report.stdout);
            print_tail("stderr", &report.stderr);
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("submission check failed"),
            }
        }
        ShellCmd::CredentialExecutionCheck {
            target,
            kind,
            source_evidence,
            artifact,
            output,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let kind = parse_credential_execution_kind(&kind)?;
            let report = kotoba_shell::credential_execution_evidence_check_with_artifacts(
                target,
                kind,
                &source_evidence,
                artifact.as_deref(),
                output.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("kind: {:?}", report.kind);
            println!("source-evidence: {}", report.source_evidence.display());
            if let Some(artifact) = &report.artifact {
                println!("artifact: {}", artifact.display());
            }
            if let Some(output) = &report.output {
                println!("output: {}", output.display());
            }
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing credential execution evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("credential execution check failed")
                }
            }
        }
        ShellCmd::ProviderContractCheck {
            manifest,
            target,
            provider_oracle_manifest,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            require_provider_oracle_manifest_for_evidence(
                "provider-contract-check",
                evidence.as_ref(),
                provider_oracle_manifest.as_deref(),
            )?;
            let report = kotoba_shell::provider_contract_check_manifest_with_oracle(
                &manifest,
                target,
                provider_oracle_manifest.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for provider in &report.providers {
                println!("provider: {provider}");
            }
            for command in &report.commands {
                println!("command: {command}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing provider contract evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("provider contract check failed")
                }
            }
        }
        ShellCmd::PluginCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::plugin_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for plugin in &report.plugins {
                println!("plugin: {plugin}");
            }
            for command in &report.commands {
                println!("command: {command}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing plugin contract evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("plugin check failed"),
            }
        }
        ShellCmd::PluginSdkCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::plugin_sdk_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("abi: {}", report.abi_version);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing plugin SDK evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("plugin SDK check failed"),
            }
        }
        ShellCmd::PluginLoadCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::plugin_load_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for bundle in &report.bundles {
                println!("bundle: {bundle}");
            }
            for command in &report.commands {
                println!("command: {command}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing plugin loader evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("plugin load check failed")
                }
            }
        }
        ShellCmd::CompatibilityCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::compatibility_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("policy: {}", report.policy_version);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing compatibility evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("compatibility check failed")
                }
            }
        }
        ShellCmd::CompatibilityMigrationCheck {
            target,
            previous,
            current,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::compatibility_migration_check(target, &previous, &current)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("previous: {}", report.previous.display());
            println!("current: {}", report.current.display());
            println!(
                "policy: {} -> {}",
                report.previous_policy_version, report.current_policy_version
            );
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing compatibility migration evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("compatibility migration check failed")
                }
            }
        }
        ShellCmd::SurfaceCheck {
            target,
            provider_oracle_manifest,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            require_provider_oracle_manifest_for_evidence(
                "surface-check",
                evidence.as_ref(),
                provider_oracle_manifest.as_deref(),
            )?;
            let report = kotoba_shell::app_surface_check_manifest_with_oracle(
                target,
                &path,
                provider_oracle_manifest.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing app surface evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("surface check failed"),
            }
        }
        ShellCmd::SurfaceParityCheck {
            require_targets,
            provider_oracle_manifest,
            evidence,
            paths,
        } => {
            require_provider_oracle_manifest_for_evidence(
                "surface-parity-check",
                evidence.as_ref(),
                provider_oracle_manifest.as_deref(),
            )?;
            let required_targets = require_targets
                .iter()
                .map(|target| kotoba_shell::Target::parse(target))
                .collect::<anyhow::Result<Vec<_>>>()?;
            let report = kotoba_shell::app_surface_parity_check_manifests_with_oracle(
                &paths,
                &required_targets,
                provider_oracle_manifest.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("bridge: {}", report.bridge);
            println!("commands: {}", report.commands.len());
            println!("detail: {}", report.detail);
            for target in &report.targets {
                println!("target: {}", target.as_str());
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing app surface parity evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("surface parity check failed")
                }
            }
        }
        ShellCmd::EvidenceCheck {
            path,
            require_passed,
            profiles,
            profile_file,
            evidence,
        } => {
            let report = kotoba_shell::evidence_check_dir(
                &path,
                &require_passed,
                &profiles,
                profile_file.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("evidence-dir: {}", report.dir.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for entry in &report.entries {
                let schema = entry.schema.as_deref().unwrap_or("-");
                println!(
                    "entry: {} {:?} schema={} {}",
                    entry.file.display(),
                    entry.status,
                    schema,
                    entry.detail
                );
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing evidence:");
                for item in &report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("evidence check failed"),
            }
        }
        ShellCmd::SelfhostProfileCheck {
            profile,
            profile_oracle_manifest,
            evidence,
        } => {
            require_manifest_for_evidence(
                "selfhost-profile-check",
                evidence.as_ref(),
                profile_oracle_manifest.as_deref(),
                "<release-dir>/kototama-shell-evidence-profile.edn",
            )?;
            let report = kotoba_shell::selfhost_profile_check_manifest_with_oracle(
                &profile,
                profile_oracle_manifest.as_deref(),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("profile: {}", report.profile.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            if let Some(schema) = &report.selfhost_schema {
                println!("selfhost-schema: {schema}");
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing selfhost profile requirements:");
                for item in &report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("selfhost profile check failed")
                }
            }
        }
        ShellCmd::KototamaWasmCheck { manifest, evidence } => {
            require_manifest_for_evidence(
                "kototama-wasm-check",
                evidence.as_ref(),
                manifest.as_deref(),
                "<release-dir>/kototama-selfhost-analyzer.edn",
            )?;
            let report = if let Some(manifest) = &manifest {
                kotoba_shell::kototama_wasm_check_manifest(manifest)?
            } else {
                kotoba_shell::kototama_wasm_check()?
            };
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("layer: {}", report.layer);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            if let Some(manifest) = &report.manifest {
                println!("manifest: {}", manifest.display());
            }
            if let Some(component_file) = &report.component_file {
                println!("component: {}", component_file.display());
            }
            println!("analyzer-abi: {}", report.analyzer_abi);
            println!("component-bytes: {}", report.component_bytes);
            if let Some(sha256) = &report.component_sha256 {
                println!("component-sha256: {sha256}");
            }
            if !report.capability_imports.is_empty() {
                println!("capability imports:");
                for import in &report.capability_imports {
                    println!("  - {import}");
                }
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing kototama wasm requirements:");
                for item in &report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("kototama wasm check failed"),
            }
        }
        ShellCmd::KototamaAppComponentsCheck { manifest, evidence } => {
            let report = kotoba_shell::kototama_app_components_check_manifest(&manifest)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            println!("admission-gate: {}", report.admission_gate);
            println!("analyzer-abi: {}", report.analyzer_abi);
            println!(
                "analyzer-component-sha256: {}",
                report.analyzer_component_sha256
            );
            println!("component-count: {}", report.component_count);
            println!(
                "component-contract-digest: {}",
                report.component_contract_digest
            );
            for component in &report.components {
                println!(
                    "component: {} {} bytes sha256={}",
                    component.id, component.bytes, component.sha256
                );
                println!("  source-sha256: {}", component.source_sha256);
                println!("  policy-sha256: {}", component.policy_sha256);
                println!("  artifact: {}", component.artifact.display());
                println!("  admission-gate: {}", component.admission_gate);
                println!("  analyzer-abi: {}", component.analyzer_abi);
                if !component.capability_imports.is_empty() {
                    println!(
                        "  capability imports: {}",
                        component.capability_imports.join(", ")
                    );
                }
            }
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing kototama app component requirements:");
                for item in &report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("kototama app components check failed")
                }
            }
        }
        ShellCmd::AdapterCheck {
            target,
            probe,
            smoke,
            hosted,
            timeout_seconds,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::adapter_check_manifest(
                target,
                &path,
                probe,
                smoke,
                hosted,
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing adapter env:");
                for missing in report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("adapter check failed"),
            }
        }
        ShellCmd::AdapterSupervisorCheck {
            target,
            adapter_evidence,
            supervisor_evidence,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::adapter_supervisor_evidence_check(
                target,
                &adapter_evidence,
                &supervisor_evidence,
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("adapter-evidence: {}", report.adapter_evidence.display());
            println!(
                "supervisor-evidence: {}",
                report.supervisor_evidence.display()
            );
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing adapter/supervisor evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("adapter/supervisor check failed")
                }
            }
        }
        ShellCmd::UpdaterCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater fields:");
                for item in report.missing {
                    println!("  - {item}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("updater check failed"),
            }
        }
        ShellCmd::UpdaterChannelCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_channel_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater channel evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater channel check failed")
                }
            }
        }
        ShellCmd::UpdaterUiCheck {
            target,
            evidence,
            path,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_ui_check_manifest(target, &path)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater UI evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater UI check failed")
                }
            }
        }
        ShellCmd::UpdaterPublicationCheck {
            target,
            updater_evidence,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_publication_evidence_check(
                target,
                &updater_evidence,
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("updater-evidence: {}", report.updater_evidence.display());
            println!("manifest: {}", report.manifest.display());
            println!("url: {}", report.url);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater publication evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater publication check failed")
                }
            }
        }
        ShellCmd::UpdaterFeedCheck {
            target,
            updater_evidence,
            feed_file,
            feed_url,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_feed_evidence_check(
                target,
                &updater_evidence,
                feed_file.as_deref(),
                feed_url.as_deref(),
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("updater-evidence: {}", report.updater_evidence.display());
            println!("manifest: {}", report.manifest.display());
            if let Some(feed_file) = &report.feed_file {
                println!("feed-file: {}", feed_file.display());
            }
            if let Some(feed_url) = &report.feed_url {
                println!("feed-url: {feed_url}");
            }
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater feed evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater feed check failed")
                }
            }
        }
        ShellCmd::UpdaterBundleCheck {
            target,
            updater_evidence,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_bundle_evidence_check(target, &updater_evidence)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("updater-evidence: {}", report.updater_evidence.display());
            println!("manifest: {}", report.manifest.display());
            println!("artifact: {}", report.artifact.display());
            println!("url: {}", report.url);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater bundle evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater bundle check failed")
                }
            }
        }
        ShellCmd::UpdaterInstallCheck {
            target,
            updater_evidence,
            staging_dir,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_install_evidence_check(
                target,
                &updater_evidence,
                &staging_dir,
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("updater-evidence: {}", report.updater_evidence.display());
            println!("manifest: {}", report.manifest.display());
            println!("artifact: {}", report.artifact.display());
            println!("download: {}", report.download.display());
            println!("staged-install: {}", report.staged_install.display());
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing updater install evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed => Ok(()),
                kotoba_shell::SdkCheckStatus::Skipped => Ok(()),
                kotoba_shell::SdkCheckStatus::Failed => {
                    anyhow::bail!("updater install check failed")
                }
            }
        }
        ShellCmd::UpdaterFinalize {
            target,
            manifest,
            artifact,
            url,
            signature,
            signature_file,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let signature = match (signature, signature_file) {
                (Some(signature), None) => signature,
                (None, Some(path)) => std::fs::read_to_string(&path)
                    .with_context(|| format!("read {}", path.display()))?
                    .trim()
                    .to_string(),
                (None, None) => anyhow::bail!("--signature or --signature-file is required"),
                (Some(_), Some(_)) => unreachable!("clap conflicts_with prevents this"),
            };
            let report = kotoba_shell::finalize_updater_manifest(
                target, &manifest, &artifact, &url, &signature,
            )?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("artifact: {}", report.artifact.display());
            println!("sha256: {}", report.sha256);
            println!("url: {}", report.url);
            println!("signature: {}", report.signature);
            Ok(())
        }
        ShellCmd::LedgerReplayCheck {
            target,
            source,
            replica,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::ledger_replay_check(target, &source, &replica)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("source: {}", report.source.display());
            println!("replica: {}", report.replica.display());
            println!("status: {:?}", report.status);
            println!("events: {}", report.event_count);
            println!("sha256: {}", report.replica_sha256);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing ledger replay evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("ledger replay check failed"),
            }
        }
        ShellCmd::LedgerRemoteCheck {
            target,
            source,
            endpoint,
            hosted,
            probe,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::ledger_remote_check(
                target,
                &source,
                &endpoint,
                hosted,
                probe,
                Duration::from_secs(timeout_seconds),
            )?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("source: {}", report.source.display());
            println!("endpoint: {}", report.endpoint);
            println!("status: {:?}", report.status);
            println!("events: {}", report.event_count);
            println!("sha256: {}", report.source_sha256);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for check in &report.checks {
                println!("  ok: {check}");
            }
            if !report.missing.is_empty() {
                println!("missing ledger remote evidence:");
                for missing in &report.missing {
                    println!("  - {missing}");
                }
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("ledger remote check failed"),
            }
        }
        ShellCmd::BrokerCheck {
            manifest,
            target,
            command,
            audit_log,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("broker-check {}", manifest.display()))?;
            let report = kotoba_shell::broker_check_plan(&plan, target, command.as_deref())?;
            println!("target: {}", report.target.as_str());
            println!("app: {}", report.app_id);
            println!("status: {:?}", report.status);
            println!("detail: {}", report.detail);
            for check in report.checks {
                println!("  ok: {check}");
            }
            if let Some(dry_run) = &report.dry_run {
                if let Some(audit_log) = &audit_log {
                    kotoba_shell::append_broker_audit(audit_log, &dry_run.audit_event)?;
                    println!("audit-log: {}", audit_log.display());
                }
                println!("dry-run command: {}", dry_run.command);
                println!("dry-run allowed: {}", dry_run.allowed);
                if let Some(provider) = &dry_run.provider {
                    println!("dry-run provider: {provider}");
                }
                if let Some(capability) = &dry_run.capability {
                    println!("dry-run capability: {capability}");
                }
                println!(
                    "dry-run audit: {}",
                    serde_json::to_string_pretty(&dry_run.audit_event)?
                );
            } else if let Some(audit_log) = &audit_log {
                println!(
                    "audit-log: skipped {} (no --command dry-run)",
                    audit_log.display()
                );
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("broker check failed"),
            }
        }
        ShellCmd::SupervisorCheck {
            manifest,
            target,
            run,
            component,
            function,
            args,
            fuel,
            kototama_app_components,
            adapter_manifest,
            adapter_timeout_seconds,
            auth_grants,
            kqe_quads,
            llm_echo,
            llm_responses,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            if run {
                require_manifest_for_evidence(
                    "supervisor-check --run",
                    evidence.as_ref(),
                    kototama_app_components.as_deref(),
                    "<release-dir>/kototama-app-components.edn",
                )?;
            }
            let plan = kotoba_shell::plan_manifest_file(&manifest)
                .with_context(|| format!("supervisor-check {}", manifest.display()))?;
            let kqe_snapshot = kqe_quads
                .iter()
                .map(|quad| parse_kqe_quad(quad))
                .collect::<Result<Vec<_>>>()?;
            let llm_responses = llm_responses
                .iter()
                .map(|response| parse_llm_response(response))
                .collect::<Result<Vec<_>>>()?;
            let dry_run = run.then_some(kotoba_shell::ComponentDryRunRequest {
                component,
                function,
                args,
                fuel,
                kototama_app_components_manifest: kototama_app_components,
                host_adapter_manifest: adapter_manifest,
                adapter_timeout_seconds,
                auth_grants,
                kqe_snapshot,
                llm_echo,
                llm_responses,
            });
            let report = kotoba_shell::supervisor_check_plan(&plan, target, dry_run)?;
            write_json_evidence(evidence.as_ref(), &report)?;
            println!("target: {}", report.target.as_str());
            println!("app: {}", report.app_id);
            println!("status: {:?}", report.status);
            if let Some(evidence) = &evidence {
                println!("evidence: {}", evidence.display());
            }
            println!("detail: {}", report.detail);
            for component in &report.components {
                println!(
                    "component: {} safe={} status={:?} wasm={}",
                    component.id,
                    component.safe,
                    component.status,
                    component
                        .wasm_bytes
                        .map(|bytes| bytes.to_string())
                        .unwrap_or_else(|| "-".to_string())
                );
                if !component.exports.is_empty() {
                    println!("  exports: {}", component.exports.join(", "));
                }
                if !component.imports.is_empty() {
                    println!("  imports: {}", component.imports.join(", "));
                }
            }
            for check in report.checks {
                println!("  ok: {check}");
            }
            if let Some(dry_run) = &report.dry_run {
                println!("dry-run component: {}", dry_run.component);
                println!("dry-run function: {}", dry_run.function);
                println!("dry-run status: {:?}", dry_run.status);
                println!("dry-run wasm-source: {}", dry_run.wasm_source);
                if let Some(gate) = &dry_run.admission_gate {
                    println!("dry-run admission-gate: {gate}");
                }
                if let Some(abi) = &dry_run.analyzer_abi {
                    println!("dry-run analyzer-abi: {abi}");
                }
                if let Some(sha256) = &dry_run.analyzer_component_sha256 {
                    println!("dry-run analyzer-component-sha256: {sha256}");
                }
                if let Some(sha256) = &dry_run.artifact_sha256 {
                    println!("dry-run artifact-sha256: {sha256}");
                }
                if let Some(sha256) = &dry_run.source_sha256 {
                    println!("dry-run source-sha256: {sha256}");
                }
                if let Some(sha256) = &dry_run.policy_sha256 {
                    println!("dry-run policy-sha256: {sha256}");
                }
                if let Some(result) = dry_run.result {
                    println!("dry-run result: {result}");
                }
                for event in &dry_run.host_events {
                    println!(
                        "dry-run host-event: {} {} {} {} {} {}",
                        event.provider,
                        event.operation,
                        event.graph,
                        event.subject,
                        event.predicate,
                        event.object
                    );
                }
                println!("dry-run detail: {}", dry_run.detail);
            }
            match report.status {
                kotoba_shell::SdkCheckStatus::Passed | kotoba_shell::SdkCheckStatus::Skipped => {
                    Ok(())
                }
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("supervisor check failed"),
            }
        }
    }
}

fn parse_kqe_quad(src: &str) -> Result<kotoba_shell::ComponentKqeQuad> {
    let parts = src.splitn(4, ',').collect::<Vec<_>>();
    if parts.len() != 4 {
        anyhow::bail!("--kqe-quad must be formatted as graph,subject,predicate,object");
    }
    Ok(kotoba_shell::ComponentKqeQuad {
        graph: parts[0].to_string(),
        subject: parts[1].to_string(),
        predicate: parts[2].to_string(),
        object: parts[3].to_string(),
    })
}

fn parse_llm_response(src: &str) -> Result<kotoba_shell::ComponentLlmResponse> {
    let Some((model, response)) = src.split_once(',') else {
        anyhow::bail!("--llm-response must be formatted as model,response");
    };
    Ok(kotoba_shell::ComponentLlmResponse {
        model: model.to_string(),
        response: response.to_string(),
    })
}

fn parse_credential_execution_kind(src: &str) -> Result<kotoba_shell::CredentialExecutionKind> {
    match src {
        "signing" => Ok(kotoba_shell::CredentialExecutionKind::Signing),
        "submission" => Ok(kotoba_shell::CredentialExecutionKind::Submission),
        _ => anyhow::bail!("--kind must be signing or submission"),
    }
}

fn require_provider_oracle_manifest_for_evidence(
    command: &str,
    evidence: Option<&PathBuf>,
    provider_oracle_manifest: Option<&Path>,
) -> Result<()> {
    require_manifest_for_evidence(
        command,
        evidence,
        provider_oracle_manifest,
        "<release-dir>/kototama-provider-surface-policy.edn",
    )
}

fn require_manifest_for_evidence(
    command: &str,
    evidence: Option<&PathBuf>,
    manifest: Option<&Path>,
    expected: &str,
) -> Result<()> {
    if evidence.is_some() && manifest.is_none() {
        anyhow::bail!("{command} --evidence requires a shipped kototama manifest: {expected}");
    }
    Ok(())
}

fn write_json_evidence<T: serde::Serialize>(path: Option<&PathBuf>, report: &T) -> Result<()> {
    let Some(path) = path else {
        return Ok(());
    };
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    let text = if path.extension().and_then(|value| value.to_str()) == Some("edn") {
        kotoba_shell::evidence_edn_string(report)?
    } else {
        serde_json::to_string_pretty(report)?
    };
    std::fs::write(path, text).with_context(|| format!("write {}", path.display()))?;
    Ok(())
}

fn print_tail(label: &str, text: &str) {
    let lines = text
        .lines()
        .rev()
        .take(20)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect::<Vec<_>>();
    if lines.is_empty() {
        return;
    }
    println!("{label}:");
    for line in lines {
        println!("  {line}");
    }
}
