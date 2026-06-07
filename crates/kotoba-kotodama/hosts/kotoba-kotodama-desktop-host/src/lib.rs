use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DesktopWindowConfig {
    pub title: Option<String>,
    pub width: Option<u32>,
    pub height: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DesktopBundleConfig {
    #[serde(rename = "bundleId")]
    pub bundle_id: Option<String>,
    pub category: Option<String>,
    #[serde(rename = "minMacOS")]
    pub min_macos: Option<String>,
    pub window: Option<DesktopWindowConfig>,
}

#[derive(Debug, Clone)]
pub struct GuestRuntime {
    pub mode: String,
    pub entry: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DesktopHostConfig {
    pub app_name: String,
    pub runtime_mode: String,
    pub guest_relative_path: String,
    pub startup_relative_path: Option<String>,
    pub bundle_id: Option<String>,
}

#[derive(Debug, Clone)]
pub struct DesktopHostPlan {
    pub app_name: String,
    pub app_root: PathBuf,
    pub runtime: GuestRuntime,
    pub bundle: DesktopBundleConfig,
}

impl DesktopHostPlan {
    pub fn bundle_identifier(&self) -> &str {
        self.bundle
            .bundle_id
            .as_deref()
            .unwrap_or("jp.co.etzhayyim.kotodama.app")
    }

    pub fn executable_name(&self) -> String {
        sanitize_app_name(&self.app_name)
    }
}

pub fn sanitize_app_name(name: &str) -> String {
    let mut out = String::new();
    for ch in name.chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch);
            continue;
        }
        if ch == ' ' || ch == '-' || ch == '_' {
            if !out.ends_with('_') {
                out.push('_');
            }
        }
    }
    let trimmed = out.trim_matches('_');
    if trimmed.is_empty() {
        "App".to_string()
    } else {
        trimmed.to_string()
    }
}

pub fn default_info_plist(plan: &DesktopHostPlan) -> String {
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>{exe}</string>
  <key>CFBundleIdentifier</key>
  <string>{bundle_id}</string>
  <key>CFBundleName</key>
  <string>{name}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>{min_macos}</string>
</dict>
</plist>
"#,
        exe = plan.executable_name(),
        bundle_id = plan.bundle_identifier(),
        name = plan.app_name,
        min_macos = plan.bundle.min_macos.as_deref().unwrap_or("14.0"),
    )
}

pub fn launcher_script(plan: &DesktopHostPlan) -> String {
    let runtime = plan.runtime.entry.display();
    format!(
        r#"#!/bin/sh
set -eu
APP_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
RESOURCES="$APP_ROOT/Resources"
echo "kotodama-desktop-host scaffold"
echo "app: {name}"
echo "runtime: {mode}"
echo "guest: $RESOURCES/{runtime}"
echo "Replace this launcher with the native desktop host binary."
"#,
        name = plan.app_name,
        mode = plan.runtime.mode,
        runtime = runtime,
    )
}

pub fn guest_resource_path(app_root: &Path, guest_name: &str) -> PathBuf {
    app_root.join("Contents").join("Resources").join(guest_name)
}

pub fn default_host_config(plan: &DesktopHostPlan) -> DesktopHostConfig {
    let guest_relative_path = plan.runtime.entry.to_string_lossy().to_string();
    let startup_relative_path = if plan.runtime.mode == "desktop-ts" {
        Some("web/index.html".to_string())
    } else {
        None
    };
    DesktopHostConfig {
        app_name: plan.app_name.clone(),
        runtime_mode: plan.runtime.mode.clone(),
        guest_relative_path,
        startup_relative_path,
        bundle_id: plan.bundle.bundle_id.clone(),
    }
}
