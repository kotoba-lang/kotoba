//! `kotoba shell` — kotoba-shell app manifest checks and native build planning.

use std::path::PathBuf;
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
        /// Write the coverage assessment as JSON evidence.
        #[arg(long)]
        evidence: Option<PathBuf>,
    },

    /// Parse a kotoba-shell manifest and run safe component admission.
    Check {
        /// Path to `app.kotoba.edn`.
        manifest: PathBuf,
    },

    /// Print the resolved kotoba-shell plan, including minimal safe-clj policy.
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

    /// Verify exported release metadata, helper scripts, and signing credential readiness.
    ReleaseCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
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

    /// Aggregate JSON evidence reports and verify required pass evidence.
    EvidenceCheck {
        /// Evidence directory containing JSON reports.
        path: PathBuf,
        /// Require a named evidence JSON file to have status Passed.
        #[arg(long = "require-passed")]
        require_passed: Vec<String>,
        /// Apply a built-in required evidence profile: ci | android-release | store-release.
        #[arg(long = "profile")]
        profiles: Vec<String>,
        /// Read profile requirements from `kotoba-shell-evidence-profile.json`.
        #[arg(long)]
        profile_file: Option<PathBuf>,
        /// Write the evidence aggregation report as JSON.
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

    /// Verify updater manifest integrity and publish readiness.
    UpdaterCheck {
        /// Target platform: macos | ios | android | windows | windows.
        #[arg(long)]
        target: String,
        /// Path to `kotoba-shell-updater-manifest.json`.
        path: PathBuf,
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
        /// Execute a pure safe-clj component export under fuel.
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
        ShellCmd::Coverage { json, evidence } => {
            let assessment = kotoba_shell::coverage_assessment();
            write_json_evidence(evidence.as_ref(), &assessment)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&assessment)?);
            } else {
                print!("{}", kotoba_shell::coverage_report());
                if let Some(evidence) = &evidence {
                    println!("evidence: {}", evidence.display());
                }
            }
            Ok(())
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
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::runtime_check_project(
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
                kotoba_shell::SdkCheckStatus::Failed => anyhow::bail!("runtime check failed"),
            }
        }
        ShellCmd::DoctorCheck {
            target,
            probe,
            timeout_seconds,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::runtime_doctor_check_with_probe(
                target,
                probe,
                Duration::from_secs(timeout_seconds),
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
        ShellCmd::ReleaseCheck { target, path } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::release_check_artifacts(target, &path)?;
            println!("target: {}", report.target.as_str());
            println!("release: {}", report.dir.display());
            println!("status: {:?}", report.status);
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
                println!(
                    "entry: {} {:?} {}",
                    entry.file.display(),
                    entry.status,
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
        ShellCmd::UpdaterCheck { target, path } => {
            let target = kotoba_shell::Target::parse(&target)?;
            let report = kotoba_shell::updater_check_manifest(target, &path)?;
            println!("target: {}", report.target.as_str());
            println!("manifest: {}", report.manifest.display());
            println!("status: {:?}", report.status);
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
            adapter_manifest,
            adapter_timeout_seconds,
            auth_grants,
            kqe_quads,
            llm_echo,
            llm_responses,
            evidence,
        } => {
            let target = kotoba_shell::Target::parse(&target)?;
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

fn write_json_evidence<T: serde::Serialize>(path: Option<&PathBuf>, report: &T) -> Result<()> {
    let Some(path) = path else {
        return Ok(());
    };
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    std::fs::write(path, serde_json::to_string_pretty(report)?)
        .with_context(|| format!("write {}", path.display()))?;
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
