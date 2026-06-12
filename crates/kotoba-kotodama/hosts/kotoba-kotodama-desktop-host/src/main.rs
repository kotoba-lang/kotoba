use anyhow::{Context, Result};
use kotoba_kotodama_desktop_host::DesktopHostConfig;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

fn main() {
    if let Err(err) = run() {
        eprintln!("kotodama-desktop-host: {err:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let exe = std::env::current_exe().context("resolve current executable")?;
    let resources_dir = resolve_resources_dir(&exe)?;
    let config_path = resources_dir.join("host-config.json");
    let config_data = fs::read_to_string(&config_path)
        .with_context(|| format!("read host config {}", config_path.display()))?;
    let config: DesktopHostConfig =
        serde_json::from_str(&config_data).context("parse host-config.json")?;

    let root = Arc::new(resources_dir.clone());
    let listener = TcpListener::bind(("127.0.0.1", 0)).context("bind local http server")?;
    let addr = listener
        .local_addr()
        .context("resolve local http server address")?;
    let startup = config
        .startup_relative_path
        .clone()
        .unwrap_or_else(|| "index.html".to_string());
    let url = format!(
        "http://127.0.0.1:{}/{}",
        addr.port(),
        startup.trim_start_matches('/')
    );

    eprintln!("kotodama-desktop-host: app={}", config.app_name);
    eprintln!("kotodama-desktop-host: runtime={}", config.runtime_mode);
    eprintln!(
        "kotodama-desktop-host: resources={}",
        resources_dir.display()
    );
    eprintln!(
        "kotodama-desktop-host: guest={}",
        config.guest_relative_path
    );
    eprintln!("kotodama-desktop-host: startup={url}");

    if cfg!(target_os = "macos") {
        let _ = Command::new("open").arg(&url).status();
    }

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let root = Arc::clone(&root);
                let config = config.clone();
                thread::spawn(move || {
                    if let Err(err) = handle_client(stream, &root, &config) {
                        eprintln!("kotodama-desktop-host: request error: {err:#}");
                    }
                });
            }
            Err(err) => {
                eprintln!("kotodama-desktop-host: accept error: {err}");
                thread::sleep(Duration::from_millis(50));
            }
        }
    }
    Ok(())
}

fn resolve_resources_dir(exe: &Path) -> Result<PathBuf> {
    let resources = exe
        .parent()
        .and_then(Path::parent)
        .map(|p| p.join("Resources"))
        .context("derive bundle resources dir from executable path")?;
    Ok(resources)
}

fn handle_client(
    mut stream: TcpStream,
    resources_dir: &Path,
    config: &DesktopHostConfig,
) -> Result<()> {
    let mut buf = [0_u8; 8192];
    let read = stream.read(&mut buf).context("read request")?;
    if read == 0 {
        return Ok(());
    }
    let req = String::from_utf8_lossy(&buf[..read]);
    let line = req.lines().next().unwrap_or_default();
    let path = line
        .split_whitespace()
        .nth(1)
        .map(str::to_string)
        .unwrap_or_else(|| "/".to_string());

    if path == "/" || path == "/index.html" {
        if let Some(startup) = &config.startup_relative_path {
            let file = resources_dir.join(startup);
            if file.exists() {
                return respond_file(&mut stream, &file);
            }
        }
        return respond_html(&mut stream, &render_index_html(config));
    }
    if path == "/health" {
        return respond_json(
            &mut stream,
            200,
            r#"{"status":"ok","host":"kotodama-desktop-host"}"#,
        );
    }
    if path == "/api/host-config" {
        let body = serde_json::to_string_pretty(config).context("serialize host config")?;
        return respond_json(&mut stream, 200, &body);
    }
    if path == "/api/guest-summary" {
        let summary_path = resources_dir.join("guest").join("sample-summary.json");
        if summary_path.is_file() {
            return respond_file(&mut stream, &summary_path);
        }
        return respond_json(
            &mut stream,
            404,
            r#"{"error":"guest summary not found","path":"guest/sample-summary.json"}"#,
        );
    }
    if path == "/api/guest-api" {
        let api_path = resources_dir.join("guest-api.json");
        if api_path.is_file() {
            return respond_file(&mut stream, &api_path);
        }
        return respond_json(
            &mut stream,
            404,
            r#"{"error":"guest api descriptor not found","path":"guest-api.json"}"#,
        );
    }

    let requested = sanitize_request_path(&path);
    let candidate_paths = resolve_candidate_paths(resources_dir, &requested);
    for file in candidate_paths {
        if file.is_file() {
            return respond_file(&mut stream, &file);
        }
    }
    respond_text(&mut stream, 404, "not found")
}

fn sanitize_request_path(path: &str) -> String {
    let trimmed = path.trim_start_matches('/');
    let mut out = Vec::new();
    for segment in trimmed.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." {
            continue;
        }
        out.push(segment);
    }
    out.join("/")
}

fn resolve_candidate_paths(resources_dir: &Path, requested: &str) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if requested.is_empty() {
        return paths;
    }
    paths.push(resources_dir.join(requested));
    if requested.starts_with("assets/") {
        paths.push(resources_dir.join("web").join(requested));
    }
    paths
}

fn render_index_html(config: &DesktopHostConfig) -> String {
    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{name}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe6;
      --ink: #1b1b18;
      --panel: #fffaf1;
      --line: #d8ccb7;
      --accent: #0d6b5d;
    }}
    body {{
      margin: 0;
      font-family: ui-serif, Georgia, serif;
      background:
        radial-gradient(circle at top left, rgba(13,107,93,0.18), transparent 30%),
        linear-gradient(180deg, #fbf6ed, var(--bg));
      color: var(--ink);
    }}
    main {{
      max-width: 880px;
      margin: 48px auto;
      padding: 24px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 20px 60px rgba(27, 27, 24, 0.08);
    }}
    h1 {{
      margin-top: 0;
      font-size: 40px;
    }}
    code {{
      background: rgba(13,107,93,0.08);
      padding: 2px 6px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>{name}</h1>
      <p>Kotodama desktop host is running.</p>
      <p>Runtime mode: <code>{mode}</code></p>
      <p>Guest artifact: <code>{guest}</code></p>
      <p>This build uses a pure Rust host that serves bundled assets locally and opens them in the default browser.</p>
    </section>
  </main>
</body>
</html>
"#,
        name = config.app_name,
        mode = config.runtime_mode,
        guest = config.guest_relative_path,
    )
}

fn respond_file(stream: &mut TcpStream, path: &Path) -> Result<()> {
    let body = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    let mime = mime_for_path(path);
    respond_bytes(stream, 200, mime, &body)
}

fn respond_html(stream: &mut TcpStream, body: &str) -> Result<()> {
    respond_bytes(stream, 200, "text/html; charset=utf-8", body.as_bytes())
}

fn respond_json(stream: &mut TcpStream, status: u16, body: &str) -> Result<()> {
    respond_bytes(
        stream,
        status,
        "application/json; charset=utf-8",
        body.as_bytes(),
    )
}

fn respond_text(stream: &mut TcpStream, status: u16, body: &str) -> Result<()> {
    respond_bytes(stream, status, "text/plain; charset=utf-8", body.as_bytes())
}

fn respond_bytes(
    stream: &mut TcpStream,
    status: u16,
    content_type: &str,
    body: &[u8],
) -> Result<()> {
    let status_text = match status {
        200 => "OK",
        404 => "Not Found",
        _ => "OK",
    };
    let headers = format!(
        "HTTP/1.1 {status} {status_text}\r\nContent-Length: {}\r\nContent-Type: {content_type}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    stream
        .write_all(headers.as_bytes())
        .context("write headers")?;
    stream.write_all(body).context("write body")?;
    Ok(())
}

fn mime_for_path(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or_default()
    {
        "html" => "text/html; charset=utf-8",
        "js" => "application/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "json" => "application/json; charset=utf-8",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "wasm" => "application/wasm",
        _ => "application/octet-stream",
    }
}
