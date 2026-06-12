use std::path::PathBuf;
use std::process::{Command, Stdio};

fn main() {
    let mut headless = false;
    let mut serve = false;
    let mut artifact_dir: Option<PathBuf> = None;
    let mut verify_golden_dir: Option<PathBuf> = None;
    let mut update_golden_dir: Option<PathBuf> = None;
    let mut min_uiux_score: u8 = 85;
    let mut listen = "127.0.0.1:18080".to_string();
    let mut model = String::new();
    let mut guest: Option<PathBuf> = None;
    let mut inference_bin = "kotodama-inference".to_string();

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--headless" => headless = true,
            "--serve" => serve = true,
            "--artifact-dir" => {
                let Some(path) = args.next() else {
                    eprintln!("kotodama-kami-host: --artifact-dir requires a path");
                    std::process::exit(2);
                };
                artifact_dir = Some(PathBuf::from(path));
            }
            "--verify-golden" => {
                let Some(path) = args.next() else {
                    eprintln!("kotodama-kami-host: --verify-golden requires a path");
                    std::process::exit(2);
                };
                verify_golden_dir = Some(PathBuf::from(path));
            }
            "--update-golden" => {
                let Some(path) = args.next() else {
                    eprintln!("kotodama-kami-host: --update-golden requires a path");
                    std::process::exit(2);
                };
                update_golden_dir = Some(PathBuf::from(path));
            }
            "--min-uiux-score" => {
                let Some(value) = args.next() else {
                    eprintln!("kotodama-kami-host: --min-uiux-score requires a number");
                    std::process::exit(2);
                };
                min_uiux_score = value.parse().unwrap_or_else(|_| {
                    eprintln!("kotodama-kami-host: invalid --min-uiux-score {}", value);
                    std::process::exit(2);
                });
            }
            "--listen" => {
                let Some(addr) = args.next() else {
                    eprintln!("kotodama-kami-host: --listen requires an address");
                    std::process::exit(2);
                };
                listen = addr;
            }
            "--model" => {
                let Some(id) = args.next() else {
                    eprintln!("kotodama-kami-host: --model requires a model id");
                    std::process::exit(2);
                };
                model = id;
            }
            "--guest" => {
                let Some(path) = args.next() else {
                    eprintln!("kotodama-kami-host: --guest requires a path");
                    std::process::exit(2);
                };
                guest = Some(PathBuf::from(path));
            }
            "--inference-bin" => {
                let Some(path) = args.next() else {
                    eprintln!("kotodama-kami-host: --inference-bin requires a path");
                    std::process::exit(2);
                };
                inference_bin = path;
            }
            "--help" | "-h" => {
                eprintln!("usage: kotodama-kami-host [--headless] [--artifact-dir PATH]");
                eprintln!(
                    "       kotodama-kami-host --serve --model MODEL [--guest PATH] [--listen ADDR] [--inference-bin PATH]"
                );
                eprintln!(
                    "       kotodama-kami-host --verify-golden DIR [--artifact-dir PATH]"
                );
                eprintln!(
                    "       kotodama-kami-host --update-golden DIR [--artifact-dir PATH]"
                );
                eprintln!("  default: launch sample window");
                eprintln!("  --headless: run sample automation plan offscreen and write artifacts");
                eprintln!("  --min-uiux-score: fail golden verify if uiux-report score is below this");
                eprintln!("  --serve: run local Kotodama host with OpenAI-compatible endpoints");
                std::process::exit(0);
            }
            other => {
                eprintln!("kotodama-kami-host: unknown arg {other}");
                std::process::exit(2);
            }
        }
    }

    let result = if serve {
        if model.is_empty() {
            eprintln!("kotodama-kami-host: --serve requires --model");
            std::process::exit(2);
        }
        serve_local(&listen, &model, guest.as_deref(), &inference_bin)
    } else if let Some(golden_dir) = verify_golden_dir {
        let dir = artifact_dir.unwrap_or_else(|| {
            kotodama_kami_host::runtime::default_artifact_dir("kami-golden-verify")
                .expect("default artifact dir")
        });
        kotodama_kami_host::runtime::verify_sample_headless_golden(
            &golden_dir,
            &dir,
            min_uiux_score,
        )
    } else if let Some(golden_dir) = update_golden_dir {
        let dir = artifact_dir.unwrap_or_else(|| {
            kotodama_kami_host::runtime::default_artifact_dir("kami-golden-update")
                .expect("default artifact dir")
        });
        kotodama_kami_host::runtime::update_sample_headless_golden(&golden_dir, &dir)
    } else if headless {
        let dir = match artifact_dir {
            Some(dir) => dir,
            None => match kotodama_kami_host::runtime::default_artifact_dir("kami-headless") {
                Ok(dir) => dir,
                Err(err) => {
                    eprintln!("kotodama-kami-host: {err:#}");
                    std::process::exit(1);
                }
            },
        };
        match kotodama_kami_host::runtime::run_sample_headless(&dir) {
            Ok(path) => {
                eprintln!("kotodama-kami-host headless transcript: {}", path.display());
                Ok(())
            }
            Err(err) => Err(err),
        }
    } else {
        kotodama_kami_host::runtime::run_sample_window()
    };

    if let Err(err) = result {
        eprintln!("kotodama-kami-host: {err:#}");
        std::process::exit(1);
    }
}

fn serve_local(
    listen: &str,
    model: &str,
    guest: Option<&std::path::Path>,
    inference_bin: &str,
) -> anyhow::Result<()> {
    if let Some(path) = guest {
        if !path.exists() {
            anyhow::bail!("guest path does not exist: {}", path.display());
        }
    }

    let probe = Command::new(inference_bin)
        .arg("--probe")
        .env("KOTODAMA_INFERENCE_BACKEND", "wgpu")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()?;
    if !probe.status.success() {
        anyhow::bail!(
            "kotodama-inference probe failed: {}",
            String::from_utf8_lossy(&probe.stderr).trim()
        );
    }

    let listener = std::net::TcpListener::bind(listen)?;
    eprintln!("kotodama-kami-host: serve");
    eprintln!("kotodama-kami-host: model={model}");
    eprintln!(
        "kotodama-kami-host: guest={}",
        guest
            .map(|p| p.display().to_string())
            .unwrap_or_else(|| "-".to_string())
    );
    eprintln!("kotodama-kami-host: backend=webgpu");
    eprintln!("kotodama-kami-host: listen={listen}");

    loop {
        let (mut stream, _) = listener.accept()?;
        if let Err(err) = handle_client(&mut stream, model, guest, inference_bin) {
            eprintln!("kotodama-kami-host: request error: {err:#}");
        }
    }
}

fn handle_client(
    stream: &mut std::net::TcpStream,
    model: &str,
    guest: Option<&std::path::Path>,
    inference_bin: &str,
) -> anyhow::Result<()> {
    let req = read_http_request(stream)?;
    match (req.method.as_str(), req.path.as_str()) {
        ("GET", "/healthz") => {
            respond_json(
                stream,
                200,
                &serde_json::json!({
                    "ok": true,
                    "host": "kotodama-kami-host",
                    "model": model,
                    "backend": "webgpu",
                    "guest": guest.map(|p| p.display().to_string()),
                }),
            )?;
        }
        ("GET", "/models") => {
            respond_json(
                stream,
                200,
                &serde_json::json!({
                    "data": [{
                        "id": model,
                        "object": "model",
                        "owned_by": "kotodama-local"
                    }]
                }),
            )?;
        }
        ("POST", "/api/openai/v1/chat/completions") => {
            let chat_req: ChatRequest = serde_json::from_slice(&req.body)?;
            let prompt = build_prompt(&chat_req);
            let output = Command::new(inference_bin)
                .arg("--model")
                .arg(model)
                .arg("--prompt")
                .arg(prompt)
                .arg("--temperature")
                .arg(chat_req.temperature.to_string())
                .arg("--max-tokens")
                .arg(chat_req.max_tokens.to_string())
                .env("KOTODAMA_INFERENCE_BACKEND", "wgpu")
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .output()?;
            if !output.status.success() {
                respond_json(
                    stream,
                    500,
                    &serde_json::json!({
                        "error": {
                            "message": String::from_utf8_lossy(&output.stderr).trim(),
                            "type": "host_runtime_error"
                        }
                    }),
                )?;
                return Ok(());
            }
            let sse = String::from_utf8(output.stdout)?;
            if chat_req.stream {
                respond_bytes(
                    stream,
                    200,
                    "text/event-stream",
                    sse.as_bytes(),
                    &[("Cache-Control", "no-cache"), ("Connection", "close")],
                )?;
            } else {
                let content = collect_sse_content(&sse)?;
                respond_json(
                    stream,
                    200,
                    &serde_json::json!({
                        "id": format!("chatcmpl-{}", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)?.as_millis()),
                        "object": "chat.completion",
                        "created": std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)?.as_secs(),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content
                            },
                            "finish_reason": "stop"
                        }]
                    }),
                )?;
            }
        }
        _ => {
            respond_json(stream, 404, &serde_json::json!({"error": "not found"}))?;
        }
    }
    Ok(())
}

#[derive(Debug)]
struct HttpRequest {
    method: String,
    path: String,
    body: Vec<u8>,
}

#[derive(Debug, serde::Deserialize)]
struct ChatRequest {
    #[serde(default)]
    messages: Vec<ChatMessage>,
    #[serde(default = "default_temperature")]
    temperature: f32,
    #[serde(default = "default_max_tokens")]
    max_tokens: u32,
    #[serde(default)]
    stream: bool,
}

#[derive(Debug, serde::Deserialize)]
struct ChatMessage {
    #[serde(default)]
    role: String,
    #[serde(default)]
    content: serde_json::Value,
}

fn default_temperature() -> f32 {
    0.7
}

fn default_max_tokens() -> u32 {
    256
}

fn read_http_request(stream: &mut std::net::TcpStream) -> anyhow::Result<HttpRequest> {
    use std::io::{Read, Write};

    let mut buf = Vec::new();
    let mut tmp = [0_u8; 4096];
    let header_end;
    loop {
        let n = stream.read(&mut tmp)?;
        if n == 0 {
            anyhow::bail!("connection closed");
        }
        buf.extend_from_slice(&tmp[..n]);
        if let Some(idx) = find_header_end(&buf) {
            header_end = idx;
            break;
        }
        if buf.len() > 1024 * 1024 {
            anyhow::bail!("request headers too large");
        }
    }

    let header_text = String::from_utf8(buf[..header_end].to_vec())?;
    let mut lines = header_text.split("\r\n");
    let request_line = lines.next().unwrap_or_default();
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or_default().to_string();
    let path = parts.next().unwrap_or_default().to_string();
    let mut content_len = 0usize;
    for line in lines {
        if let Some((k, v)) = line.split_once(':') {
            if k.trim().eq_ignore_ascii_case("content-length") {
                content_len = v.trim().parse().unwrap_or(0);
            }
        }
    }
    let body_start = header_end + 4;
    let mut body = buf[body_start..].to_vec();
    while body.len() < content_len {
        let n = stream.read(&mut tmp)?;
        if n == 0 {
            break;
        }
        body.extend_from_slice(&tmp[..n]);
    }
    body.truncate(content_len);
    stream.flush()?;
    Ok(HttpRequest { method, path, body })
}

fn find_header_end(buf: &[u8]) -> Option<usize> {
    buf.windows(4).position(|w| w == b"\r\n\r\n")
}

fn build_prompt(req: &ChatRequest) -> String {
    let mut out = String::new();
    for msg in &req.messages {
        let content = match &msg.content {
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Array(items) => items
                .iter()
                .filter_map(|item| item.get("text").and_then(|v| v.as_str()))
                .collect::<Vec<_>>()
                .join("\n"),
            _ => String::new(),
        };
        if !content.is_empty() {
            out.push_str(&msg.role);
            out.push_str(": ");
            out.push_str(&content);
            out.push('\n');
        }
    }
    out
}

fn collect_sse_content(sse: &str) -> anyhow::Result<String> {
    let mut out = String::new();
    for line in sse.lines() {
        let line = line.trim();
        if !line.starts_with("data: ") {
            continue;
        }
        let payload = line.trim_start_matches("data: ").trim();
        if payload == "[DONE]" {
            continue;
        }
        let value: serde_json::Value = serde_json::from_str(payload)?;
        if let Some(content) = value
            .get("choices")
            .and_then(|v| v.get(0))
            .and_then(|v| v.get("delta"))
            .and_then(|v| v.get("content"))
            .and_then(|v| v.as_str())
        {
            out.push_str(content);
        }
    }
    Ok(out)
}

fn respond_json(
    stream: &mut std::net::TcpStream,
    status: u16,
    body: &serde_json::Value,
) -> anyhow::Result<()> {
    let bytes = serde_json::to_vec(body)?;
    respond_bytes(
        stream,
        status,
        "application/json",
        &bytes,
        &[("Access-Control-Allow-Origin", "*")],
    )
}

fn respond_bytes(
    stream: &mut std::net::TcpStream,
    status: u16,
    content_type: &str,
    body: &[u8],
    extra_headers: &[(&str, &str)],
) -> anyhow::Result<()> {
    use std::io::Write;

    let status_text = match status {
        200 => "OK",
        404 => "Not Found",
        500 => "Internal Server Error",
        _ => "Error",
    };
    let mut response = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n",
        status,
        status_text,
        content_type,
        body.len()
    );
    for (k, v) in extra_headers {
        response.push_str(k);
        response.push_str(": ");
        response.push_str(v);
        response.push_str("\r\n");
    }
    response.push_str("\r\n");
    stream.write_all(response.as_bytes())?;
    stream.write_all(body)?;
    stream.flush()?;
    Ok(())
}
