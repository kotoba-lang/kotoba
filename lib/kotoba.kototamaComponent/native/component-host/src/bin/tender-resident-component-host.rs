//! Native micro-TCB Component host.
//!
//! The stdin/stdout protocol is deliberately tiny:
//!   1. Clojure sends one run envelope.
//!   2. each imported WIT function yields one provider-call envelope;
//!      Clojure validates and invokes the admitted provider, then responds.
//!   3. the host emits one terminal result or error envelope.
//!
//! No WASI linker is installed.  Therefore a Component receives only the
//! separately named aiueos imports carried in its admitted envelope.

use anyhow::{Context, Result, anyhow, bail};
use ed25519_dalek::{Signer, SigningKey};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::env;
use std::fs::{self, OpenOptions};
use std::io::{self, BufRead, BufReader, BufWriter, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use wasmtime::component::{Component, Linker, Resource, ResourceType, Val, types::Type};
use wasmtime::{Config, Engine, Store, StoreLimits, StoreLimitsBuilder};

#[derive(Debug, Clone, Deserialize, Serialize)]
struct Ability {
    target: String,
    operation: String,
    #[serde(rename = "max-bytes")]
    max_bytes: u64,
    #[serde(rename = "max-items")]
    max_items: u64,
    #[serde(rename = "deadline-ms")]
    deadline_ms: u64,
    #[serde(rename = "audit-id")]
    audit_id: String,
}

#[derive(Debug, Clone, Deserialize)]
struct Import {
    name: String,
    ability: Ability,
}

#[derive(Debug, Clone, Deserialize)]
struct Run {
    #[serde(rename = "type")]
    kind: String,
    component: String,
    #[serde(rename = "capability-mode", default = "default_capability_mode")]
    capability_mode: String,
    imports: Vec<Import>,
    fuel: u64,
    #[serde(rename = "memory-pages")]
    memory_pages: u64,
    #[serde(default)]
    export: Option<String>,
    #[serde(default)]
    params: Vec<Value>,
}

fn default_capability_mode() -> String {
    "function".into()
}

struct Protocol {
    input: BufReader<io::Stdin>,
    output: BufWriter<io::Stdout>,
}

struct State {
    protocol: Option<Arc<Mutex<Protocol>>>,
    resident_effects: Option<Arc<Mutex<EffectSession>>>,
    limits: StoreLimits,
}

fn allowed_binding(name: &str) -> Option<(&'static str, &'static str, &'static str)> {
    match name {
        "aiueos-http-post" => Some(("kotoba:application/http-post@1.0.0", "post", "http/post")),
        "aiueos-clock-now" => Some(("kotoba:application/clock@1.0.0", "now", "clock/now")),
        "aiueos-log-append" => Some(("kotoba:application/log@1.0.0", "append", "log/append")),
        "aiueos-llm-generate" => Some(("kotoba:application/llm@1.0.0", "generate", "llm/generate")),
        "aiueos-storage-transact" => Some((
            "kotoba:application/storage@1.0.0",
            "transact",
            "storage/transact",
        )),
        _ => None,
    }
}

fn validate_ability(name: &str, ability: &Ability) -> Result<()> {
    let Some((_, _, expected_operation)) = allowed_binding(name) else {
        bail!("unrecognized aiueos Component import: {name}");
    };
    if ability.operation != expected_operation {
        bail!("import {name} is bound to an invalid operation");
    }
    if ability.target.is_empty()
        || ability.audit_id.is_empty()
        || ability.max_bytes == 0
        || ability.max_items == 0
        || ability.deadline_ms == 0
    {
        bail!("import {name} has an unbounded or incomplete ability");
    }
    Ok(())
}

fn send(protocol: &mut Protocol, value: &Value) -> Result<()> {
    serde_json::to_writer(&mut protocol.output, value)?;
    protocol.output.write_all(b"\n")?;
    protocol.output.flush()?;
    Ok(())
}

fn provider_call(state: &mut State, name: &str, ability: &Ability, value: i64) -> Result<i64> {
    // The descriptor is captured while linking, never supplied by the guest.
    validate_ability(name, ability)?;
    if let Some(effects) = state.resident_effects.as_ref() {
        return effects
            .lock()
            .map_err(|_| anyhow!("resident effect session lock poisoned"))?
            .invoke(name, ability, value);
    }
    let protocol = state.protocol.as_ref().ok_or_else(|| {
        anyhow!("Component requested a capability but no admitted provider is installed")
    })?;
    let mut protocol = protocol
        .lock()
        .map_err(|_| anyhow!("protocol lock poisoned"))?;
    send(
        &mut protocol,
        &json!({
            "type": "provider-call",
            "import": name,
            "ability": ability,
            "payload": { "value": value }
        }),
    )?;
    let mut response = String::new();
    if protocol.input.read_line(&mut response)? == 0 {
        bail!("provider closed protocol before responding");
    }
    let response: Value = serde_json::from_str(&response).context("invalid provider response")?;
    if response.get("type") != Some(&Value::String("provider-result".into())) {
        bail!("expected provider-result response");
    }
    if response.get("import") != Some(&Value::String(name.into())) {
        bail!("provider response import does not match request");
    }
    response
        .get("value")
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("provider response must contain an i64 value"))
}

// With Wasmtime's deliberately minimal feature set its error type does not
// implement `std::error::Error`. Keep that boundary explicit rather than
// enabling unrelated Wasmtime features merely to use `anyhow` conversion.
fn wasmtime_result<T>(result: std::result::Result<T, wasmtime::Error>, context: &str) -> Result<T> {
    result.map_err(|error| anyhow!("{context}: {error}"))
}

fn value_from_json(ty: &Type, value: &Value) -> Result<Val> {
    match ty {
        Type::Bool => value
            .as_bool()
            .map(Val::Bool)
            .ok_or_else(|| anyhow!("Component bool parameter must be JSON boolean")),
        Type::S64 => value
            .as_i64()
            .map(Val::S64)
            .ok_or_else(|| anyhow!("Component s64 parameter must be a JSON integer")),
        Type::String => value
            .as_str()
            .map(|value| Val::String(value.into()))
            .ok_or_else(|| anyhow!("Component string parameter must be a JSON string")),
        Type::Record(record) => {
            let object = value
                .as_object()
                .ok_or_else(|| anyhow!("Component record parameter must be a JSON object"))?;
            let fields = record
                .fields()
                .map(|field| {
                    let value = object
                        .get(field.name)
                        .ok_or_else(|| anyhow!("Component record is missing {}", field.name))?;
                    Ok((field.name.into(), value_from_json(&field.ty, value)?))
                })
                .collect::<Result<Vec<_>>>()?;
            if fields.len() != object.len() {
                bail!("Component record contains an unknown field");
            }
            Ok(Val::Record(fields))
        }
        Type::Variant(variant) => {
            let object = value
                .as_object()
                .ok_or_else(|| anyhow!("Component variant parameter must be a JSON object"))?;
            if !matches!(object.len(), 1 | 2) {
                bail!("Component variant requires case and optional value only");
            }
            let case = object
                .get("case")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow!("Component variant requires a string case"))?;
            let selected = variant
                .cases()
                .find(|candidate| candidate.name == case)
                .ok_or_else(|| anyhow!("Component variant case is outside the closed type"))?;
            let payload = match selected.ty {
                Some(ty) => Some(Box::new(value_from_json(
                    &ty,
                    object
                        .get("value")
                        .ok_or_else(|| anyhow!("Component variant case requires a value"))?,
                )?)),
                None => {
                    if object.contains_key("value") {
                        bail!("Component variant case does not accept a value");
                    }
                    None
                }
            };
            Ok(Val::Variant(case.into(), payload))
        }
        _ => bail!("Component invocation parameter type is not admitted by the JSON bridge"),
    }
}

fn default_value(ty: &Type) -> Result<Val> {
    match ty {
        Type::Bool => Ok(Val::Bool(false)),
        Type::S64 => Ok(Val::S64(0)),
        Type::String => Ok(Val::String(String::new())),
        Type::Record(record) => Ok(Val::Record(
            record
                .fields()
                .map(|field| Ok((field.name.into(), default_value(&field.ty)?)))
                .collect::<Result<Vec<_>>>()?,
        )),
        Type::Variant(variant) => {
            let case = variant
                .cases()
                .next()
                .ok_or_else(|| anyhow!("Component result variant has no cases"))?;
            let payload = case
                .ty
                .as_ref()
                .map(default_value)
                .transpose()?
                .map(Box::new);
            Ok(Val::Variant(case.name.into(), payload))
        }
        _ => bail!("Component invocation result type is not admitted by the JSON bridge"),
    }
}

fn value_to_json(value: &Val) -> Result<Value> {
    match value {
        Val::Bool(value) => Ok(json!(value)),
        Val::S64(value) => Ok(json!(value)),
        Val::String(value) => Ok(json!(value)),
        Val::Record(fields) => Ok(Value::Object(
            fields
                .iter()
                .map(|(name, value)| Ok((name.clone(), value_to_json(value)?)))
                .collect::<Result<serde_json::Map<_, _>>>()?,
        )),
        Val::Variant(case, payload) => {
            let mut object = serde_json::Map::new();
            object.insert("case".into(), json!(case));
            if let Some(payload) = payload {
                object.insert("value".into(), value_to_json(payload)?);
            }
            Ok(Value::Object(object))
        }
        _ => bail!("Component invocation result type is not admitted by the JSON bridge"),
    }
}

fn run_values(
    request: Run,
    protocol: Option<Arc<Mutex<Protocol>>>,
    resident_effects: Option<Arc<Mutex<EffectSession>>>,
) -> Result<Vec<Val>> {
    if request.kind != "run" {
        bail!("first protocol envelope must be a run request");
    }
    let mut imports = BTreeMap::new();
    for import in request.imports {
        validate_ability(&import.name, &import.ability)?;
        if imports.insert(import.name, import.ability).is_some() {
            bail!("duplicate Component import");
        }
    }

    let mut config = Config::new();
    config.wasm_component_model(true);
    config.consume_fuel(true);
    let engine = wasmtime_result(Engine::new(&config), "cannot create Component engine")?;
    let component = wasmtime_result(
        Component::from_file(&engine, &request.component),
        "cannot compile admitted Component",
    )?;
    let limits = StoreLimitsBuilder::new()
        .memory_size(request.memory_pages.saturating_mul(65536) as usize)
        .build();
    let mut store = Store::new(
        &engine,
        State {
            protocol,
            resident_effects,
            limits,
        },
    );
    store.limiter(|state| &mut state.limits);
    wasmtime_result(store.set_fuel(request.fuel), "cannot set Component fuel")?;

    let mut linker = Linker::<State>::new(&engine);
    for (name, ability) in imports {
        let import_name = name.clone();
        let (interface, function, _) = allowed_binding(&name)
            .ok_or_else(|| anyhow!("unrecognized aiueos Component import: {name}"))?;
        let mut instance = wasmtime_result(
            linker.instance(interface),
            "cannot create admitted Component interface",
        )?;
        if request.capability_mode == "linear-resource" {
            let resource_name = format!("{function}-capability");
            wasmtime_result(
                instance.resource(&resource_name, ResourceType::host::<()>(), |_, _| Ok(())),
                "cannot bind linear capability resource",
            )?;
            let issue_name = format!("issue-{function}");
            wasmtime_result(
                instance.func_wrap(&issue_name, move |_cx, (): ()| {
                    Ok((Resource::<()>::new_own(1),))
                }),
                "cannot bind linear capability issuer",
            )?;
            let execute_name = format!("execute-{function}");
            wasmtime_result(
                instance.func_wrap(
                    &execute_name,
                    move |mut cx, (_cap, value): (Resource<()>, i64)| {
                        provider_call(cx.data_mut(), &import_name, &ability, value)
                            .map(|result| (result,))
                            .map_err(|error| wasmtime::Error::msg(error.to_string()))
                    },
                ),
                "cannot bind linear capability consumer",
            )?;
        } else {
            if matches!(
                name.as_str(),
                "aiueos-http-post" | "aiueos-storage-transact" | "aiueos-llm-generate"
            ) {
                wasmtime_result(
                    instance.func_new(function, move |mut cx, _ty, params, results| {
                        let outcome = (|| -> Result<()> {
                            if matches!(params, [Val::S64(_)]) {
                                let [Val::S64(value)] = params else {
                                    unreachable!()
                                };
                                provider_call(cx.data_mut(), &import_name, &ability, *value)
                                    .and_then(|result| {
                                        if results.len() != 1 {
                                            bail!("storage capability must return one result");
                                        }
                                        results[0] = Val::S64(result);
                                        Ok(())
                                    })
                            } else {
                                let effects =
                                    cx.data_mut().resident_effects.as_ref().ok_or_else(|| {
                                    anyhow!(
                                        "structured storage requires a resident admitted provider"
                                    )
                                })?;
                                let mut effects = effects.lock().map_err(|_| {
                                    anyhow!("resident effect session lock poisoned")
                                })?;
                                match import_name.as_str() {
                                    "aiueos-http-post" => {
                                        effects.post_value(&ability, params, results)
                                    }
                                    "aiueos-storage-transact" => {
                                        effects.transact_value(&ability, params, results)
                                    }
                                    "aiueos-llm-generate" => {
                                        effects.generate_value(&ability, params, results)
                                    }
                                    _ => unreachable!(),
                                }
                            }
                        })();
                        outcome.map_err(|error| {
                            eprintln!(
                                "{}",
                                json!({
                                    "capability": import_name,
                                    "error": error.to_string(),
                                    "type": "provider-error"
                                })
                            );
                            wasmtime::Error::msg(error.to_string())
                        })
                    }),
                    "cannot bind admitted structured capability import",
                )?;
            } else {
                wasmtime_result(
                    instance.func_wrap(function, move |mut cx, (value,): (i64,)| {
                        provider_call(cx.data_mut(), &import_name, &ability, value)
                            .map(|result| (result,))
                            .map_err(|error| {
                                eprintln!(
                                    "{}",
                                    json!({
                                        "capability": import_name,
                                        "error": error.to_string(),
                                        "type": "provider-error"
                                    })
                                );
                                wasmtime::Error::msg(error.to_string())
                            })
                    }),
                    "cannot bind admitted Component import",
                )?;
            }
        }
    }
    let instance = wasmtime_result(
        linker.instantiate(&mut store, &component),
        "Component imports did not match the admitted bindings",
    )?;
    let export = request.export.as_deref().unwrap_or("main");
    let function = instance
        .get_func(&mut store, export)
        .ok_or_else(|| anyhow!("Component does not export {export}"))?;
    let function_type = function.ty(&store);
    let param_types = function_type.params().map(|(_, ty)| ty).collect::<Vec<_>>();
    let result_types = function_type.results().collect::<Vec<_>>();
    if request.params.len() != param_types.len() {
        bail!("Component invocation parameter count does not match export");
    }
    let params = param_types
        .iter()
        .zip(&request.params)
        .map(|(ty, value)| value_from_json(ty, value))
        .collect::<Result<Vec<_>>>()?;
    let mut results = result_types
        .iter()
        .map(default_value)
        .collect::<Result<Vec<_>>>()?;
    wasmtime_result(
        function.call(&mut store, &params, &mut results),
        "Component export failed",
    )?;
    Ok(results)
}

fn run(
    request: Run,
    protocol: Option<Arc<Mutex<Protocol>>>,
    resident_effects: Option<Arc<Mutex<EffectSession>>>,
) -> Result<i64> {
    match run_values(request, protocol, resident_effects)?
        .into_iter()
        .next()
    {
        Some(Val::S64(value)) => Ok(value),
        _ => bail!("Component main must return s64"),
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
struct HttpCapability {
    endpoint: String,
    #[serde(default)]
    request_body: Option<Value>,
    #[serde(default)]
    request_code: Option<i64>,
    #[serde(default)]
    max_request_bytes: Option<u64>,
    max_response_bytes: u64,
    deadline_ms: u64,
    audit_id: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
struct StorageCapability {
    #[serde(default)]
    log: Option<PathBuf>,
    #[serde(default)]
    endpoint: Option<String>,
    #[serde(default)]
    max_request_bytes: Option<u64>,
    max_write_bytes: u64,
    deadline_ms: u64,
    audit_id: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
struct LlmCapability {
    endpoint: String,
    model: String,
    #[serde(default)]
    prompt: Option<String>,
    #[serde(default)]
    success_code: Option<i64>,
    max_request_bytes: u64,
    max_response_bytes: u64,
    deadline_ms: u64,
    audit_id: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
struct ResidentCapabilityConfig {
    format: String,
    #[serde(default)]
    http: Option<HttpCapability>,
    #[serde(default)]
    storage: Option<StorageCapability>,
    #[serde(default)]
    llm: Option<LlmCapability>,
}

#[derive(Debug)]
struct EffectSession {
    config: Arc<ResidentCapabilityConfig>,
    http_response: Option<Value>,
    http_result: Option<i64>,
    stored_bytes: Option<i64>,
    events: Vec<Value>,
}

fn loopback_endpoint(url: &str) -> Result<(SocketAddr, String)> {
    let rest = url
        .strip_prefix("http://127.0.0.1:")
        .ok_or_else(|| anyhow!("resident capability endpoint must use literal loopback HTTP"))?;
    let (authority, path) = match rest.split_once('/') {
        Some((port, suffix)) => (port, format!("/{suffix}")),
        None => (rest, "/".into()),
    };
    let port = authority
        .parse::<u16>()
        .context("resident capability endpoint has an invalid port")?;
    if port == 0 {
        bail!("resident capability endpoint port must be positive");
    }
    Ok((SocketAddr::from(([127, 0, 0, 1], port)), path))
}

fn decode_chunked(input: &[u8], max_bytes: usize) -> Result<Vec<u8>> {
    let mut cursor = 0usize;
    let mut output = Vec::new();
    loop {
        let line_end = input[cursor..]
            .windows(2)
            .position(|window| window == b"\r\n")
            .map(|position| cursor + position)
            .ok_or_else(|| anyhow!("chunked response has an incomplete size line"))?;
        let size_text = std::str::from_utf8(&input[cursor..line_end])
            .context("chunked response size is not UTF-8")?;
        let size =
            usize::from_str_radix(size_text.split(';').next().unwrap_or_default().trim(), 16)
                .context("chunked response has an invalid size")?;
        cursor = line_end + 2;
        if size == 0 {
            return Ok(output);
        }
        if size > max_bytes.saturating_sub(output.len())
            || cursor.saturating_add(size).saturating_add(2) > input.len()
        {
            bail!("chunked response exceeds its admitted byte bound");
        }
        output.extend_from_slice(&input[cursor..cursor + size]);
        cursor += size;
        if input.get(cursor..cursor + 2) != Some(b"\r\n") {
            bail!("chunked response is missing a chunk terminator");
        }
        cursor += 2;
    }
}

fn post_loopback_json(
    endpoint: &str,
    body: &Value,
    deadline_ms: u64,
    max_response_bytes: u64,
) -> Result<(u16, Value, usize)> {
    if deadline_ms == 0 || max_response_bytes == 0 {
        bail!("resident capability HTTP bounds must be positive");
    }
    let (address, path) = loopback_endpoint(endpoint)?;
    let timeout = std::time::Duration::from_millis(deadline_ms);
    let mut stream = TcpStream::connect_timeout(&address, timeout)
        .with_context(|| format!("cannot connect to admitted endpoint {endpoint}"))?;
    stream.set_read_timeout(Some(timeout))?;
    stream.set_write_timeout(Some(timeout))?;
    let payload = serde_json::to_vec(body)?;
    write!(
        stream,
        "POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        address.port(),
        payload.len()
    )?;
    stream.write_all(&payload)?;
    stream.flush()?;

    let hard_limit = usize::try_from(max_response_bytes)
        .unwrap_or(usize::MAX)
        .saturating_add(16 * 1024);
    let mut response = Vec::new();
    stream
        .take(hard_limit.saturating_add(1) as u64)
        .read_to_end(&mut response)?;
    if response.len() > hard_limit {
        bail!("resident capability response exceeds its admitted byte bound");
    }
    let split = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| anyhow!("resident capability returned an invalid HTTP response"))?;
    let headers = std::str::from_utf8(&response[..split])
        .context("resident capability HTTP headers are not UTF-8")?;
    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(|| anyhow!("resident capability returned an invalid HTTP status"))?;
    if !(200..300).contains(&status) {
        bail!("resident capability endpoint returned HTTP {status}");
    }
    let chunked = headers
        .lines()
        .any(|line| line.to_ascii_lowercase().trim() == "transfer-encoding: chunked");
    let raw_body = &response[split + 4..];
    let decoded_chunked = chunked
        .then(|| decode_chunked(raw_body, max_response_bytes as usize))
        .transpose()?;
    let body = decoded_chunked.as_deref().unwrap_or(raw_body);
    if body.len() > max_response_bytes as usize {
        bail!("resident capability response body exceeds its admitted byte bound");
    }
    let decoded =
        serde_json::from_slice(body).context("resident capability response body is not JSON")?;
    Ok((status, decoded, body.len()))
}

fn append_json_line(path: &Path, value: &Value, max_bytes: u64) -> Result<usize> {
    if !path.is_absolute() || max_bytes == 0 {
        bail!("resident storage capability requires an absolute bounded log");
    }
    let mut bytes = serde_json::to_vec(value)?;
    bytes.push(b'\n');
    if bytes.len() > max_bytes as usize {
        bail!("resident storage write exceeds its admitted byte bound");
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .with_context(|| format!("cannot open admitted storage log {}", path.display()))?;
    file.write_all(&bytes)?;
    file.flush()?;
    file.sync_data()?;
    Ok(bytes.len())
}

fn record_string(fields: &[(String, Val)], name: &str) -> Result<String> {
    fields
        .iter()
        .find_map(|(field, value)| {
            (field == name).then(|| match value {
                Val::String(value) => Ok(value.clone()),
                _ => bail!("structured storage field {name} must be a string"),
            })
        })
        .transpose()?
        .ok_or_else(|| anyhow!("structured storage record is missing field {name}"))
}

fn record_i64(fields: &[(String, Val)], name: &str) -> Result<i64> {
    fields
        .iter()
        .find_map(|(field, value)| {
            (field == name).then(|| match value {
                Val::S64(value) => Ok(*value),
                _ => bail!("structured storage field {name} must be s64"),
            })
        })
        .transpose()?
        .ok_or_else(|| anyhow!("structured storage record is missing field {name}"))
}

fn storage_result_from_json(response: &Value) -> Result<Val> {
    let tag = response
        .get("tag")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("storage provider response is missing tag"))?;
    let string = |name: &str| {
        response
            .get(name)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .ok_or_else(|| anyhow!("storage provider response is missing {name}"))
    };
    let integer = |name: &str| {
        response
            .get(name)
            .and_then(Value::as_i64)
            .ok_or_else(|| anyhow!("storage provider response is missing {name}"))
    };
    let boolean = |name: &str| {
        response
            .get(name)
            .and_then(Value::as_bool)
            .ok_or_else(|| anyhow!("storage provider response is missing {name}"))
    };
    let payload = match tag {
        "found" | "written" => Val::Record(vec![
            ("key".into(), Val::String(string("key")?)),
            ("value".into(), Val::String(string("value")?)),
            ("version".into(), Val::S64(integer("version")?)),
        ]),
        "missing" | "conflict-missing" | "deleted" => Val::Bool(boolean("value")?),
        "conflict-current" => Val::Record(vec![
            ("key".into(), Val::String(string("key")?)),
            (
                "current-version".into(),
                Val::S64(integer("current-version")?),
            ),
        ]),
        "error" => Val::Record(vec![
            ("code".into(), Val::String(string("code")?)),
            ("message".into(), Val::String(string("message")?)),
            ("retryable".into(), Val::Bool(boolean("retryable")?)),
        ]),
        _ => bail!("storage provider response tag is outside the admitted subset"),
    };
    Ok(Val::Variant(tag.into(), Some(Box::new(payload))))
}

fn conditional_values(path: &Path, max_bytes: u64) -> Result<BTreeMap<String, (String, i64)>> {
    if !path.exists() {
        return Ok(BTreeMap::new());
    }
    let metadata = fs::metadata(path)?;
    if metadata.len() > max_bytes {
        bail!("resident structured storage namespace exceeds its admitted quota");
    }
    let input = fs::read_to_string(path)
        .with_context(|| format!("cannot read admitted storage log {}", path.display()))?;
    let mut values = BTreeMap::new();
    for line in input.lines().filter(|line| !line.trim().is_empty()) {
        let Ok(record) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        if record.get("format").and_then(Value::as_str) != Some("kototama.conditional-value/v1") {
            continue;
        }
        let Some(key) = record.get("key").and_then(Value::as_str) else {
            continue;
        };
        let Some(value) = record.get("value").and_then(Value::as_str) else {
            continue;
        };
        let Some(version) = record.get("version").and_then(Value::as_i64) else {
            continue;
        };
        values.insert(key.to_owned(), (value.to_owned(), version));
    }
    Ok(values)
}

impl EffectSession {
    fn new(config: Arc<ResidentCapabilityConfig>) -> Self {
        Self {
            config,
            http_response: None,
            http_result: None,
            stored_bytes: None,
            events: Vec::new(),
        }
    }

    fn event(
        &mut self,
        capability: &str,
        ability: &Ability,
        request: i64,
        result: i64,
        response_bytes: usize,
    ) -> Result<()> {
        self.events.push(json!({
            "ability-audit-id": ability.audit_id,
            "at-ms": now_ms()?,
            "capability": capability,
            "request": request,
            "response-bytes": response_bytes,
            "result": result,
            "target": ability.target
        }));
        Ok(())
    }

    fn invoke(&mut self, name: &str, ability: &Ability, value: i64) -> Result<i64> {
        match name {
            "aiueos-http-post" => {
                let http = self
                    .config
                    .http
                    .as_ref()
                    .ok_or_else(|| anyhow!("HTTP capability is not configured"))?;
                if Some(value) != http.request_code {
                    bail!("HTTP capability request code is outside the admitted operation");
                }
                let request_body = http
                    .request_body
                    .as_ref()
                    .ok_or_else(|| anyhow!("scalar HTTP capability requires a request body"))?;
                let (_, response, response_bytes) = post_loopback_json(
                    &http.endpoint,
                    request_body,
                    http.deadline_ms,
                    http.max_response_bytes,
                )?;
                let result = i64::try_from(response_bytes)
                    .context("HTTP response length does not fit the scalar Component ABI")?;
                self.http_response = Some(response);
                self.http_result = Some(result);
                self.event(name, ability, value, result, response_bytes)?;
                Ok(result)
            }
            "aiueos-storage-transact" => {
                let storage = self
                    .config
                    .storage
                    .as_ref()
                    .ok_or_else(|| anyhow!("storage capability is not configured"))?;
                let response = self
                    .http_response
                    .as_ref()
                    .ok_or_else(|| anyhow!("storage capability requires a prior HTTP result"))?;
                if self.http_result != Some(value) {
                    bail!("storage capability input does not match the prior HTTP result");
                }
                let record = json!({
                    "format": "cloud-itonami.effect-checkpoint/v1",
                    "http-response": response,
                    "recorded-at-ms": now_ms()?
                });
                let log = storage.log.as_deref().ok_or_else(|| {
                    anyhow!("scalar storage capability requires an admitted local log")
                })?;
                let written = append_json_line(log, &record, storage.max_write_bytes)?;
                let result = i64::try_from(written)
                    .context("storage write length does not fit the scalar Component ABI")?;
                self.stored_bytes = Some(result);
                self.event(name, ability, value, result, written)?;
                Ok(result)
            }
            "aiueos-llm-generate" => {
                let llm = self
                    .config
                    .llm
                    .as_ref()
                    .ok_or_else(|| anyhow!("LLM capability is not configured"))?;
                if self.stored_bytes != Some(value) {
                    bail!("LLM capability input does not match the durable checkpoint");
                }
                let context = self
                    .http_response
                    .as_ref()
                    .ok_or_else(|| anyhow!("LLM capability requires a prior HTTP result"))?;
                let legacy_prompt = llm
                    .prompt
                    .as_deref()
                    .ok_or_else(|| anyhow!("scalar LLM capability requires a configured prompt"))?;
                let prompt = format!(
                    "{}\n\nBounded provider context:\n{}",
                    legacy_prompt,
                    serde_json::to_string(context)?
                );
                if prompt.len() > llm.max_request_bytes as usize {
                    bail!("LLM request exceeds its admitted byte bound");
                }
                let request = json!({
                    "model": llm.model,
                    "prompt": prompt,
                    "stream": false
                });
                let (_, response, response_bytes) = post_loopback_json(
                    &llm.endpoint,
                    &request,
                    llm.deadline_ms,
                    llm.max_response_bytes,
                )?;
                let generated = response
                    .get("response")
                    .and_then(Value::as_str)
                    .filter(|text| !text.trim().is_empty())
                    .ok_or_else(|| anyhow!("LLM provider returned no bounded text result"))?;
                let result = llm
                    .success_code
                    .ok_or_else(|| anyhow!("scalar LLM capability requires a success code"))?;
                self.event(
                    name,
                    ability,
                    value,
                    result,
                    generated.len().min(response_bytes),
                )?;
                Ok(result)
            }
            _ => bail!("resident provider does not implement capability {name}"),
        }
    }

    fn post_value(&mut self, ability: &Ability, params: &[Val], results: &mut [Val]) -> Result<()> {
        validate_ability("aiueos-http-post", ability)?;
        let http = self
            .config
            .http
            .as_ref()
            .ok_or_else(|| anyhow!("HTTP capability is not configured"))?;
        let [Val::Variant(case, Some(payload))] = params else {
            bail!("structured HTTP requires one request variant");
        };
        if case != "post" {
            bail!("structured HTTP request is outside the admitted operation");
        }
        let Val::Record(fields) = payload.as_ref() else {
            bail!("structured HTTP post case requires a record");
        };
        if results.len() != 1 {
            bail!("structured HTTP must return one result variant");
        }
        let body = record_string(fields, "body")?;
        let timeout_ms = record_i64(fields, "timeout-ms")?;
        let request_limit = http
            .max_request_bytes
            .unwrap_or(http.max_response_bytes)
            .min(ability.max_bytes);
        if body.len() > request_limit as usize {
            bail!("structured HTTP request exceeds its admitted byte bound");
        }
        if timeout_ms <= 0 || timeout_ms as u64 > http.deadline_ms.min(ability.deadline_ms) {
            bail!("structured HTTP timeout is outside the admitted deadline");
        }
        let body: Value =
            serde_json::from_str(&body).context("structured HTTP body must be JSON")?;
        let posted = post_loopback_json(
            &http.endpoint,
            &body,
            timeout_ms as u64,
            http.max_response_bytes.min(ability.max_bytes),
        );
        let (status, response, response_bytes) = match posted {
            Ok(response) => response,
            Err(_) => {
                results[0] = Val::Variant(
                    "error".into(),
                    Some(Box::new(Val::Record(vec![
                        ("code".into(), Val::String("http/provider-failed".into())),
                        (
                            "message".into(),
                            Val::String("admitted HTTP provider failed".into()),
                        ),
                        ("retryable".into(), Val::Bool(true)),
                    ]))),
                );
                self.events.push(json!({
                    "ability-audit-id": ability.audit_id,
                    "at-ms": now_ms()?,
                    "capability": "aiueos-http-post",
                    "outcome": "error",
                    "target": ability.target
                }));
                return Ok(());
            }
        };
        let response_body = serde_json::to_string(&response)?;
        if response_body.len() > http.max_response_bytes.min(ability.max_bytes) as usize {
            bail!("structured HTTP response exceeds its admitted byte bound");
        }
        results[0] = Val::Variant(
            "ok".into(),
            Some(Box::new(Val::Record(vec![
                ("status".into(), Val::S64(i64::from(status))),
                ("body".into(), Val::String(response_body)),
            ]))),
        );
        self.events.push(json!({
            "ability-audit-id": ability.audit_id,
            "at-ms": now_ms()?,
            "capability": "aiueos-http-post",
            "outcome": "ok",
            "response-bytes": response_bytes,
            "status": status,
            "target": ability.target
        }));
        Ok(())
    }

    fn generate_value(
        &mut self,
        ability: &Ability,
        params: &[Val],
        results: &mut [Val],
    ) -> Result<()> {
        validate_ability("aiueos-llm-generate", ability)?;
        let llm = self
            .config
            .llm
            .as_ref()
            .ok_or_else(|| anyhow!("LLM capability is not configured"))?;
        let [request] = params else {
            bail!("structured LLM requires one request");
        };
        let (fields, flattened_result) = match request {
            Val::Record(fields) => (fields, false),
            Val::Variant(case, Some(payload)) if case == "generate" => {
                let Val::Record(fields) = payload.as_ref() else {
                    bail!("structured LLM generate case requires a record");
                };
                (fields, true)
            }
            _ => bail!("structured LLM request is outside the admitted subset"),
        };
        if results.len() != 1 {
            bail!("structured LLM must return one result variant");
        }
        let model = record_string(fields, "model")?;
        let system = record_string(fields, "system")?;
        let prompt = record_string(fields, "prompt")?;
        let max_output_tokens = record_i64(fields, "max-output-tokens")?;
        let temperature_milli = record_i64(fields, "temperature-milli")?;
        if model != llm.model {
            bail!("LLM model is outside the exact host allowlist");
        }
        if !(1..=4096).contains(&max_output_tokens) || !(0..=2000).contains(&temperature_milli) {
            bail!("structured LLM request budget is outside llm-v1");
        }
        let combined = format!("{system}\n\n{prompt}");
        if system.len() > 65536
            || prompt.len() > 65536
            || combined.len() > llm.max_request_bytes as usize
        {
            bail!("structured LLM request exceeds its admitted byte bound");
        }
        let request = json!({
            "model": llm.model,
            "prompt": prompt,
            "stream": false,
            "system": system,
            "options": {
                "num_predict": max_output_tokens,
                "temperature": temperature_milli as f64 / 1000.0
            }
        });
        let generated = post_loopback_json(
            &llm.endpoint,
            &request,
            llm.deadline_ms.min(ability.deadline_ms),
            llm.max_response_bytes.min(ability.max_bytes),
        );
        let (_, response, response_bytes) = match generated {
            Ok(response) => response,
            Err(_) => {
                results[0] = Val::Variant(
                    "error".into(),
                    Some(Box::new(Val::Record(vec![
                        ("code".into(), Val::String("llm/transport".into())),
                        (
                            "message".into(),
                            Val::String("admitted LLM provider failed".into()),
                        ),
                        ("retryable".into(), Val::Bool(true)),
                    ]))),
                );
                self.events.push(json!({
                    "ability-audit-id": ability.audit_id,
                    "at-ms": now_ms()?,
                    "capability": "aiueos-llm-generate",
                    "model": model,
                    "outcome": "error",
                    "target": ability.target
                }));
                return Ok(());
            }
        };
        let text = response
            .get("response")
            .and_then(Value::as_str)
            .filter(|text| !text.trim().is_empty());
        let Some(text) = text else {
            results[0] = Val::Variant(
                "error".into(),
                Some(Box::new(Val::Record(vec![
                    ("code".into(), Val::String("llm/empty-output".into())),
                    (
                        "message".into(),
                        Val::String("LLM provider returned no text".into()),
                    ),
                    ("retryable".into(), Val::Bool(true)),
                ]))),
            );
            self.events.push(json!({
                "ability-audit-id": ability.audit_id,
                "at-ms": now_ms()?,
                "capability": "aiueos-llm-generate",
                "model": model,
                "outcome": "empty-output",
                "response-bytes": response_bytes,
                "target": ability.target
            }));
            return Ok(());
        };
        if text.len() > llm.max_response_bytes.min(ability.max_bytes) as usize {
            bail!("LLM provider text exceeds its admitted byte bound");
        }
        let finish_reason = response
            .get("done_reason")
            .and_then(Value::as_str)
            .filter(|reason| !reason.is_empty())
            .unwrap_or("llm/stop");
        let input_tokens = response
            .get("prompt_eval_count")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let output_tokens = response
            .get("eval_count")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let mut completion = vec![
            ("text".into(), Val::String(text.into())),
            ("finish-reason".into(), Val::String(finish_reason.into())),
        ];
        if flattened_result {
            completion.extend([
                ("input-tokens".into(), Val::S64(input_tokens)),
                ("output-tokens".into(), Val::S64(output_tokens)),
            ]);
        } else {
            completion.push((
                "usage".into(),
                Val::Record(vec![
                    ("input-tokens".into(), Val::S64(input_tokens)),
                    ("output-tokens".into(), Val::S64(output_tokens)),
                ]),
            ));
        }
        results[0] = Val::Variant("ok".into(), Some(Box::new(Val::Record(completion))));
        self.events.push(json!({
            "ability-audit-id": ability.audit_id,
            "at-ms": now_ms()?,
            "capability": "aiueos-llm-generate",
            "finish-reason": finish_reason,
            "input-tokens": input_tokens,
            "model": model,
            "output-tokens": output_tokens,
            "response-bytes": response_bytes,
            "target": ability.target
        }));
        Ok(())
    }

    fn transact_value(
        &mut self,
        ability: &Ability,
        params: &[Val],
        results: &mut [Val],
    ) -> Result<()> {
        validate_ability("aiueos-storage-transact", ability)?;
        let storage = self
            .config
            .storage
            .as_ref()
            .ok_or_else(|| anyhow!("storage capability is not configured"))?;
        let [Val::Variant(operation, Some(payload))] = params else {
            bail!("structured storage requires one request variant");
        };
        let Val::Record(fields) = payload.as_ref() else {
            bail!("structured storage request case requires a record payload");
        };
        if results.len() != 1 {
            bail!("structured storage must return one result variant");
        }
        let key = record_string(fields, "key")?;
        if key.is_empty() || key.len() > 4096 {
            bail!("structured storage request exceeds its admitted bounds");
        }
        if let Some(endpoint) = storage.endpoint.as_deref() {
            let mut request = json!({"operation": operation, "key": key});
            if matches!(operation.as_str(), "put-new" | "put-existing") {
                let value = record_string(fields, "value")?;
                if value.len() > storage.max_write_bytes as usize {
                    bail!("structured storage request exceeds its admitted bounds");
                }
                request["value"] = Value::String(value);
            }
            if operation == "put-existing" {
                request["expected-version"] =
                    Value::Number(record_i64(fields, "expected-version")?.into());
            }
            let request_bytes = serde_json::to_vec(&request)?.len();
            let request_limit = storage
                .max_request_bytes
                .unwrap_or(storage.max_write_bytes)
                .min(ability.max_bytes);
            if request_bytes > request_limit as usize {
                bail!("structured storage provider request exceeds its admitted byte bound");
            }
            let (_, response, response_bytes) = post_loopback_json(
                endpoint,
                &request,
                storage.deadline_ms.min(ability.deadline_ms),
                storage.max_write_bytes.min(ability.max_bytes),
            )?;
            results[0] = storage_result_from_json(&response)?;
            self.events.push(json!({
                "ability-audit-id": ability.audit_id,
                "at-ms": now_ms()?,
                "capability": "aiueos-storage-transact",
                "operation": operation,
                "outcome": response.get("tag"),
                "request-key": key,
                "response-bytes": response_bytes,
                "target": ability.target
            }));
            return Ok(());
        }
        let log = storage
            .log
            .as_deref()
            .ok_or_else(|| anyhow!("storage capability has no admitted provider"))?;
        let current = conditional_values(log, storage.max_write_bytes)?
            .get(&key)
            .cloned();
        if operation == "get" {
            results[0] = match current {
                Some((value, version)) => Val::Variant(
                    "found".into(),
                    Some(Box::new(Val::Record(vec![
                        ("key".into(), Val::String(key.clone())),
                        ("value".into(), Val::String(value)),
                        ("version".into(), Val::S64(version)),
                    ]))),
                ),
                None => Val::Variant("missing".into(), Some(Box::new(Val::Bool(true)))),
            };
            self.events.push(json!({
                "ability-audit-id": ability.audit_id,
                "at-ms": now_ms()?,
                "capability": "aiueos-storage-transact",
                "operation": operation,
                "request-key": key,
                "response-bytes": 0,
                "target": ability.target
            }));
            return Ok(());
        }
        let value = record_string(fields, "value")?;
        if value.len() > storage.max_write_bytes as usize {
            bail!("structured storage request exceeds its admitted bounds");
        }
        let next_version = match operation.as_str() {
            "put-new" => match current {
                Some((_, version)) => {
                    results[0] = Val::Variant(
                        "conflict-current".into(),
                        Some(Box::new(Val::Record(vec![
                            ("key".into(), Val::String(key.clone())),
                            ("current-version".into(), Val::S64(version)),
                        ]))),
                    );
                    return Ok(());
                }
                None => 1,
            },
            "put-existing" => {
                let expected = record_i64(fields, "expected-version")?;
                match current {
                    None => {
                        results[0] = Val::Variant(
                            "conflict-missing".into(),
                            Some(Box::new(Val::Bool(true))),
                        );
                        return Ok(());
                    }
                    Some((_, version)) if version != expected => {
                        results[0] = Val::Variant(
                            "conflict-current".into(),
                            Some(Box::new(Val::Record(vec![
                                ("key".into(), Val::String(key.clone())),
                                ("current-version".into(), Val::S64(version)),
                            ]))),
                        );
                        return Ok(());
                    }
                    Some((_, version)) => version
                        .checked_add(1)
                        .ok_or_else(|| anyhow!("structured storage version overflow"))?,
                }
            }
            _ => bail!("structured storage operation is outside the admitted subset"),
        };
        let record = json!({
            "format": "kototama.conditional-value/v1",
            "key": key,
            "recorded-at-ms": now_ms()?,
            "value": value,
            "version": next_version
        });
        let written = append_json_line(log, &record, storage.max_write_bytes)?;
        results[0] = Val::Variant(
            "written".into(),
            Some(Box::new(Val::Record(vec![
                ("key".into(), Val::String(key.clone())),
                ("value".into(), Val::String(value)),
                ("version".into(), Val::S64(next_version)),
            ]))),
        );
        self.events.push(json!({
            "ability-audit-id": ability.audit_id,
            "at-ms": now_ms()?,
            "capability": "aiueos-storage-transact",
            "operation": operation,
            "request-key": key,
            "response-bytes": written,
            "result-version": next_version,
            "target": ability.target
        }));
        Ok(())
    }
}

struct ResidentConfig {
    bind: SocketAddr,
    component: PathBuf,
    component_cid: String,
    component_sha256: String,
    expected_result: i64,
    fuel: u64,
    memory_pages: u64,
    node: String,
    receipt_log: PathBuf,
    signing_key: SigningKey,
    capabilities: Option<Arc<ResidentCapabilityConfig>>,
    capability_config_sha256: Option<String>,
    startup_mode: String,
}

fn required_env(name: &str) -> Result<String> {
    let value = env::var(name).with_context(|| format!("{name} is required"))?;
    if value.is_empty() {
        bail!("{name} must not be empty");
    }
    Ok(value)
}

fn parse_positive_env(name: &str) -> Result<u64> {
    let value = required_env(name)?;
    let parsed = value
        .parse::<u64>()
        .with_context(|| format!("{name} must be a positive integer"))?;
    if parsed == 0 {
        bail!("{name} must be positive");
    }
    Ok(parsed)
}

fn sha256_file(path: &Path) -> Result<String> {
    let bytes =
        fs::read(path).with_context(|| format!("cannot read Component {}", path.display()))?;
    Ok(hex::encode(Sha256::digest(bytes)))
}

fn read_signing_key(path: &Path) -> Result<SigningKey> {
    let encoded = fs::read_to_string(path)
        .with_context(|| format!("cannot read receipt signing key {}", path.display()))?;
    let bytes = hex::decode(encoded.trim()).context("receipt signing key is not hex")?;
    let seed: [u8; 32] = bytes
        .try_into()
        .map_err(|_| anyhow!("receipt signing key must contain exactly 32 bytes"))?;
    Ok(SigningKey::from_bytes(&seed))
}

fn read_capability_config() -> Result<Option<(Arc<ResidentCapabilityConfig>, String)>> {
    let path = match env::var("KOTOTAMA_CAPABILITY_CONFIG_PATH") {
        Ok(value) if !value.is_empty() => PathBuf::from(value),
        _ => return Ok(None),
    };
    if !path.is_absolute() || !path.is_file() {
        bail!("KOTOTAMA_CAPABILITY_CONFIG_PATH must be an absolute file");
    }
    let expected_sha256 = required_env("KOTOTAMA_CAPABILITY_CONFIG_SHA256")?;
    if expected_sha256.len() != 64 || !expected_sha256.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        bail!("KOTOTAMA_CAPABILITY_CONFIG_SHA256 must be lowercase SHA-256 hex");
    }
    if sha256_file(&path)? != expected_sha256 {
        bail!("resident capability configuration does not match its admitted SHA-256");
    }
    let config: ResidentCapabilityConfig = serde_json::from_slice(
        &fs::read(&path)
            .with_context(|| format!("cannot read capability config {}", path.display()))?,
    )
    .context("resident capability configuration is invalid")?;
    if config.format != "kototama.resident-capabilities/v1" {
        bail!("resident capability configuration format is unsupported");
    }
    if config.http.is_none() && config.storage.is_none() && config.llm.is_none() {
        bail!("resident capability configuration must grant at least one capability");
    }
    if let Some(http) = config.http.as_ref() {
        loopback_endpoint(&http.endpoint)?;
        if http.audit_id.is_empty()
            || http.max_request_bytes == Some(0)
            || http.max_response_bytes == 0
            || http.deadline_ms == 0
        {
            bail!("resident HTTP capability contains an unbounded field");
        }
    }
    if let Some(storage) = config.storage.as_ref() {
        if let Some(endpoint) = storage.endpoint.as_deref() {
            loopback_endpoint(endpoint)?;
        }
        let provider_count =
            usize::from(storage.log.is_some()) + usize::from(storage.endpoint.is_some());
        if provider_count != 1
            || storage.log.as_ref().is_some_and(|path| !path.is_absolute())
            || storage.max_request_bytes == Some(0)
            || storage.audit_id.is_empty()
            || storage.max_write_bytes == 0
            || storage.deadline_ms == 0
        {
            bail!("resident storage capability contains an unbounded field");
        }
    }
    if let Some(llm) = config.llm.as_ref() {
        loopback_endpoint(&llm.endpoint)?;
        if llm.audit_id.is_empty()
            || llm.model.is_empty()
            || llm.max_request_bytes == 0
            || llm.max_response_bytes == 0
            || llm.deadline_ms == 0
        {
            bail!("resident LLM capability contains an unbounded field");
        }
    }
    Ok(Some((Arc::new(config), expected_sha256)))
}

fn resident_imports(config: &ResidentCapabilityConfig) -> Vec<Import> {
    let mut imports = Vec::new();
    if let Some(http) = config.http.as_ref() {
        imports.push(Import {
            name: "aiueos-http-post".into(),
            ability: Ability {
                target: http.endpoint.clone(),
                operation: "http/post".into(),
                max_bytes: http.max_response_bytes,
                max_items: 1,
                deadline_ms: http.deadline_ms,
                audit_id: http.audit_id.clone(),
            },
        });
    }
    if let Some(storage) = config.storage.as_ref() {
        let target = storage.endpoint.clone().unwrap_or_else(|| {
            storage
                .log
                .as_ref()
                .expect("validated storage provider")
                .to_string_lossy()
                .into_owned()
        });
        imports.push(Import {
            name: "aiueos-storage-transact".into(),
            ability: Ability {
                target,
                operation: "storage/transact".into(),
                max_bytes: storage.max_write_bytes,
                max_items: 1,
                deadline_ms: storage.deadline_ms,
                audit_id: storage.audit_id.clone(),
            },
        });
    }
    if let Some(llm) = config.llm.as_ref() {
        imports.push(Import {
            name: "aiueos-llm-generate".into(),
            ability: Ability {
                target: llm.endpoint.clone(),
                operation: "llm/generate".into(),
                max_bytes: llm.max_response_bytes,
                max_items: 1,
                deadline_ms: llm.deadline_ms,
                audit_id: llm.audit_id.clone(),
            },
        });
    }
    imports
}

fn resident_config() -> Result<ResidentConfig> {
    let bind = env::var("KOTOTAMA_BIND_ADDR")
        .unwrap_or_else(|_| "127.0.0.1:18901".into())
        .parse::<SocketAddr>()
        .context("KOTOTAMA_BIND_ADDR must be a socket address")?;
    if !bind.ip().is_loopback() {
        bail!("resident Component host must bind a loopback address");
    }
    let component = PathBuf::from(required_env("KOTOTAMA_COMPONENT_PATH")?);
    if !component.is_absolute() || !component.is_file() {
        bail!("KOTOTAMA_COMPONENT_PATH must be an absolute file");
    }
    let expected_sha256 = required_env("KOTOTAMA_COMPONENT_SHA256")?;
    if expected_sha256.len() != 64 || !expected_sha256.bytes().all(|b| b.is_ascii_hexdigit()) {
        bail!("KOTOTAMA_COMPONENT_SHA256 must be lowercase SHA-256 hex");
    }
    let actual_sha256 = sha256_file(&component)?;
    if actual_sha256 != expected_sha256 {
        bail!("resident Component bytes do not match KOTOTAMA_COMPONENT_SHA256");
    }
    let seed_path = PathBuf::from(required_env("KOTOTAMA_RECEIPT_SEED_PATH")?);
    let receipt_log = PathBuf::from(required_env("KOTOTAMA_RECEIPT_LOG")?);
    if !seed_path.is_absolute() || !receipt_log.is_absolute() {
        bail!("receipt key and log paths must be absolute");
    }
    let capability_config = read_capability_config()?;
    let startup_mode = env::var("KOTOTAMA_STARTUP_MODE").unwrap_or_else(|_| "execute-main".into());
    if !matches!(startup_mode.as_str(), "execute-main" | "compile-only") {
        bail!("KOTOTAMA_STARTUP_MODE must be execute-main or compile-only");
    }
    Ok(ResidentConfig {
        bind,
        component,
        component_cid: required_env("KOTOTAMA_COMPONENT_CID")?,
        component_sha256: expected_sha256,
        expected_result: required_env("KOTOTAMA_EXPECTED_RESULT")?
            .parse::<i64>()
            .context("KOTOTAMA_EXPECTED_RESULT must be i64")?,
        fuel: parse_positive_env("KOTOTAMA_FUEL")?,
        memory_pages: parse_positive_env("KOTOTAMA_MEMORY_PAGES")?,
        node: required_env("KOTOTAMA_NODE")?,
        receipt_log,
        signing_key: read_signing_key(&seed_path)?,
        capabilities: capability_config.as_ref().map(|(config, _)| config.clone()),
        capability_config_sha256: capability_config.map(|(_, digest)| digest),
        startup_mode,
    })
}

fn now_ms() -> Result<u128> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("system clock is before Unix epoch")?
        .as_millis())
}

fn receipt_envelope(body: Value, signing_key: &SigningKey) -> Result<Value> {
    let canonical = serde_json::to_vec(&body)?;
    let signature = signing_key.sign(&canonical);
    let payload = String::from_utf8(canonical)
        .map_err(|_| anyhow!("canonical receipt payload is not UTF-8"))?;
    Ok(json!({
        "algorithm": "ed25519",
        "body": body,
        "payload": payload,
        "signature": hex::encode(signature.to_bytes())
    }))
}

fn persist_receipt(path: &Path, receipt: &Value) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .with_context(|| format!("cannot open receipt log {}", path.display()))?;
    serde_json::to_writer(&mut file, receipt)?;
    file.write_all(b"\n")?;
    file.flush()?;
    file.sync_data()?;
    Ok(())
}

fn execute_resident(config: &ResidentConfig) -> Result<Value> {
    let started_at_ms = now_ms()?;
    let effect_session = config
        .capabilities
        .as_ref()
        .map(|capabilities| Arc::new(Mutex::new(EffectSession::new(capabilities.clone()))));
    let result = run(
        Run {
            kind: "run".into(),
            component: config.component.to_string_lossy().into_owned(),
            capability_mode: "function".into(),
            imports: config
                .capabilities
                .as_deref()
                .map(resident_imports)
                .unwrap_or_default(),
            fuel: config.fuel,
            memory_pages: config.memory_pages,
            export: None,
            params: Vec::new(),
        },
        None,
        effect_session.clone(),
    )?;
    let finished_at_ms = now_ms()?;
    if result != config.expected_result {
        bail!("Component result does not match admitted expected result");
    }
    let public_key = hex::encode(config.signing_key.verifying_key().to_bytes());
    let effects = effect_session
        .map(|session| {
            session
                .lock()
                .map(|state| state.events.clone())
                .map_err(|_| anyhow!("resident effect session lock poisoned"))
        })
        .transpose()?
        .unwrap_or_default();
    let body = json!({
        "ambient-wasi": false,
        "capabilities": effects.iter().filter_map(|event| event.get("capability")).collect::<Vec<_>>(),
        "capability-config-sha256": config.capability_config_sha256,
        "component-cid": config.component_cid,
        "component-sha256": config.component_sha256,
        "effects": effects,
        "expected-result": config.expected_result,
        "finished-at-ms": finished_at_ms,
        "format": "kototama.component-execution-receipt/v1",
        "fuel": config.fuel,
        "memory-pages": config.memory_pages,
        "node": config.node,
        "receipt-public-key": public_key,
        "result": result,
        "runtime": "tender-component/0.1.0+wasmtime-42.0.1",
        "started-at-ms": started_at_ms,
        "status": "ok"
    });
    let receipt = receipt_envelope(body, &config.signing_key)?;
    persist_receipt(&config.receipt_log, &receipt)?;
    Ok(receipt)
}

fn compile_resident(config: &ResidentConfig) -> Result<()> {
    let mut engine_config = Config::new();
    engine_config.wasm_component_model(true);
    let engine = wasmtime_result(
        Engine::new(&engine_config),
        "cannot create Component engine",
    )?;
    wasmtime_result(
        Component::from_file(&engine, &config.component),
        "cannot compile admitted Component",
    )?;
    Ok(())
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case", deny_unknown_fields)]
struct InvocationRequest {
    export: String,
    params: Vec<Value>,
}

fn execute_invocation(config: &ResidentConfig, invocation: InvocationRequest) -> Result<Value> {
    if invocation.export.is_empty()
        || invocation.export.len() > 128
        || !invocation
            .export
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        bail!("Component invocation export name is outside the admitted syntax");
    }
    let started_at_ms = now_ms()?;
    let request_bytes = serde_json::to_vec(&invocation)?;
    let request_sha256 = hex::encode(Sha256::digest(&request_bytes));
    let effect_session = config
        .capabilities
        .as_ref()
        .map(|capabilities| Arc::new(Mutex::new(EffectSession::new(capabilities.clone()))));
    let export = invocation.export.clone();
    let results = run_values(
        Run {
            kind: "run".into(),
            component: config.component.to_string_lossy().into_owned(),
            capability_mode: "function".into(),
            imports: config
                .capabilities
                .as_deref()
                .map(resident_imports)
                .unwrap_or_default(),
            fuel: config.fuel,
            memory_pages: config.memory_pages,
            export: Some(invocation.export),
            params: invocation.params,
        },
        None,
        effect_session.clone(),
    )?;
    let output = results
        .iter()
        .map(value_to_json)
        .collect::<Result<Vec<_>>>()?;
    let effects = effect_session
        .map(|session| {
            session
                .lock()
                .map(|state| state.events.clone())
                .map_err(|_| anyhow!("resident effect session lock poisoned"))
        })
        .transpose()?
        .unwrap_or_default();
    let body = json!({
        "ambient-wasi": false,
        "capability-config-sha256": config.capability_config_sha256,
        "component-cid": config.component_cid,
        "component-sha256": config.component_sha256,
        "effects": effects,
        "export": export,
        "finished-at-ms": now_ms()?,
        "format": "kototama.component-invocation-receipt/v1",
        "fuel": config.fuel,
        "memory-pages": config.memory_pages,
        "node": config.node,
        "output": output,
        "receipt-public-key": hex::encode(config.signing_key.verifying_key().to_bytes()),
        "request-sha256": request_sha256,
        "runtime": "tender-component/0.1.0+wasmtime-42.0.1",
        "started-at-ms": started_at_ms,
        "status": "ok"
    });
    let receipt = receipt_envelope(body, &config.signing_key)?;
    persist_receipt(&config.receipt_log, &receipt)?;
    Ok(receipt)
}

fn read_http_request(stream: &mut TcpStream) -> Result<(String, String, Vec<u8>)> {
    stream.set_read_timeout(Some(std::time::Duration::from_secs(5)))?;
    let mut bytes = Vec::new();
    let mut one = [0u8; 1];
    while bytes.len() < 16 * 1024 {
        if stream.read(&mut one)? == 0 {
            break;
        }
        bytes.push(one[0]);
        if bytes.ends_with(b"\r\n\r\n") {
            break;
        }
    }
    if !bytes.ends_with(b"\r\n\r\n") {
        bail!("HTTP header is incomplete or too large");
    }
    let text = std::str::from_utf8(&bytes).context("HTTP header is not UTF-8")?;
    let mut lines = text.split("\r\n");
    let mut request = lines.next().unwrap_or_default().split_whitespace();
    let method = request.next().unwrap_or_default().to_owned();
    let path = request.next().unwrap_or_default().to_owned();
    if request.next() != Some("HTTP/1.1") {
        bail!("only HTTP/1.1 is accepted");
    }
    let mut content_length = 0usize;
    for line in lines {
        let lower = line.to_ascii_lowercase();
        if lower.starts_with("content-length:") {
            let length = line.split_once(':').map(|(_, v)| v.trim()).unwrap_or("");
            content_length = length
                .parse::<usize>()
                .context("HTTP Content-Length is invalid")?;
            if content_length > 1024 * 1024 {
                bail!("HTTP request body exceeds its admitted byte bound");
            }
        }
    }
    let mut body = vec![0u8; content_length];
    stream.read_exact(&mut body)?;
    Ok((method, path, body))
}

fn write_http_json(stream: &mut TcpStream, status: &str, body: &Value) -> Result<()> {
    let bytes = serde_json::to_vec(body)?;
    write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        bytes.len()
    )?;
    stream.write_all(&bytes)?;
    stream.flush()?;
    Ok(())
}

fn health(config: &ResidentConfig) -> Value {
    let capabilities = config
        .capabilities
        .as_deref()
        .map(resident_imports)
        .unwrap_or_default()
        .into_iter()
        .map(|import| import.name)
        .collect::<Vec<_>>();
    json!({
        "ambient-wasi": false,
        "capabilities": capabilities,
        "capability-config-sha256": config.capability_config_sha256,
        "component-cid": config.component_cid,
        "component-sha256": config.component_sha256,
        "node": config.node,
        "ready": true,
        "receipt-public-key": hex::encode(config.signing_key.verifying_key().to_bytes()),
        "runtime": "tender-component/0.1.0+wasmtime-42.0.1"
        ,"startup-mode": config.startup_mode
    })
}

fn handle_http(mut stream: TcpStream, config: &ResidentConfig) -> Result<()> {
    let request = read_http_request(&mut stream);
    match request {
        Ok((method, path, _)) if method == "GET" && path == "/healthz" => {
            write_http_json(&mut stream, "200 OK", &health(config))
        }
        Ok((method, path, _)) if method == "POST" && path == "/v1/run" => {
            match execute_resident(config) {
                Ok(receipt) => write_http_json(&mut stream, "200 OK", &receipt),
                Err(error) => write_http_json(
                    &mut stream,
                    "500 Internal Server Error",
                    &json!({"error": error.to_string(), "ok": false}),
                ),
            }
        }
        Ok((method, path, body)) if method == "POST" && path == "/v1/invoke" => {
            match serde_json::from_slice::<InvocationRequest>(&body)
                .context("Component invocation body is invalid")
                .and_then(|invocation| execute_invocation(config, invocation))
            {
                Ok(receipt) => write_http_json(&mut stream, "200 OK", &receipt),
                Err(error) => write_http_json(
                    &mut stream,
                    "400 Bad Request",
                    &json!({"error": error.to_string(), "ok": false}),
                ),
            }
        }
        Ok(_) => write_http_json(
            &mut stream,
            "404 Not Found",
            &json!({"error": "not found", "ok": false}),
        ),
        Err(error) => write_http_json(
            &mut stream,
            "400 Bad Request",
            &json!({"error": error.to_string(), "ok": false}),
        ),
    }
}

fn serve_resident() -> Result<()> {
    let config = resident_config()?;
    match config.startup_mode.as_str() {
        "execute-main" => {
            execute_resident(&config).context("resident Component startup canary failed")?;
        }
        "compile-only" => {
            compile_resident(&config).context("resident Component startup compile failed")?;
        }
        _ => unreachable!(),
    }
    let listener =
        TcpListener::bind(config.bind).with_context(|| format!("cannot bind {}", config.bind))?;
    eprintln!(
        "{}",
        json!({
            "bind": config.bind.to_string(),
            "component-cid": config.component_cid,
            "node": config.node,
            "ready": true
        })
    );
    for connection in listener.incoming() {
        match connection {
            Ok(stream) => {
                if let Err(error) = handle_http(stream, &config) {
                    eprintln!("resident request failed: {error:#}");
                }
            }
            Err(error) => eprintln!("resident accept failed: {error}"),
        }
    }
    Ok(())
}

fn main() {
    if env::args().nth(1).as_deref() == Some("--serve") {
        if let Err(error) = serve_resident() {
            eprintln!("resident Component host failed: {error:#}");
            std::process::exit(1);
        }
        return;
    }
    let protocol = Arc::new(Mutex::new(Protocol {
        input: BufReader::new(io::stdin()),
        output: BufWriter::new(io::stdout()),
    }));
    let outcome = (|| -> Result<i64> {
        let mut line = String::new();
        {
            let mut locked = protocol
                .lock()
                .map_err(|_| anyhow!("protocol lock poisoned"))?;
            if locked.input.read_line(&mut line)? == 0 {
                bail!("missing run envelope");
            }
        }
        run(
            serde_json::from_str(&line).context("invalid run envelope")?,
            Some(protocol.clone()),
            None,
        )
    })();
    let terminal = match outcome {
        Ok(value) => json!({ "type": "result", "value": value }),
        Err(error) => json!({ "type": "error", "message": format!("{error:#}") }),
    };
    if let Ok(mut locked) = protocol.lock() {
        let _ = send(&mut locked, &terminal);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::Verifier;

    fn structured_session(log: PathBuf) -> EffectSession {
        EffectSession::new(Arc::new(ResidentCapabilityConfig {
            format: "kototama.resident-capabilities/v1".into(),
            http: Some(HttpCapability {
                endpoint: "http://127.0.0.1:1/http".into(),
                request_body: Some(json!({})),
                request_code: Some(1),
                max_request_bytes: Some(1024),
                max_response_bytes: 1024,
                deadline_ms: 1000,
                audit_id: "http".into(),
            }),
            storage: Some(StorageCapability {
                log: Some(log),
                endpoint: None,
                max_request_bytes: None,
                max_write_bytes: 65536,
                deadline_ms: 1000,
                audit_id: "storage".into(),
            }),
            llm: Some(LlmCapability {
                endpoint: "http://127.0.0.1:1/llm".into(),
                model: "model".into(),
                prompt: Some("prompt".into()),
                success_code: Some(1),
                max_request_bytes: 1024,
                max_response_bytes: 1024,
                deadline_ms: 1000,
                audit_id: "llm".into(),
            }),
        }))
    }

    fn storage_ability(path: &Path) -> Ability {
        Ability {
            target: path.to_string_lossy().into_owned(),
            operation: "storage/transact".into(),
            max_bytes: 65536,
            max_items: 1,
            deadline_ms: 1000,
            audit_id: "order-commit".into(),
        }
    }

    fn llm_ability(endpoint: &str) -> Ability {
        Ability {
            target: endpoint.into(),
            operation: "llm/generate".into(),
            max_bytes: 65536,
            max_items: 1,
            deadline_ms: 1000,
            audit_id: "commitment-advisor".into(),
        }
    }

    fn http_ability(endpoint: &str) -> Ability {
        Ability {
            target: endpoint.into(),
            operation: "http/post".into(),
            max_bytes: 65536,
            max_items: 1,
            deadline_ms: 1000,
            audit_id: "isic6492-intake".into(),
        }
    }

    fn http_request(body: &str, timeout_ms: i64) -> Vec<Val> {
        vec![Val::Variant(
            "post".into(),
            Some(Box::new(Val::Record(vec![
                ("body".into(), Val::String(body.into())),
                ("timeout-ms".into(), Val::S64(timeout_ms)),
            ]))),
        )]
    }

    fn llm_request(model: &str) -> Vec<Val> {
        vec![Val::Variant(
            "generate".into(),
            Some(Box::new(Val::Record(vec![
                ("model".into(), Val::String(model.into())),
                (
                    "system".into(),
                    Val::String("Use admitted facts only.".into()),
                ),
                ("prompt".into(), Val::String("Draft one proposal.".into())),
                ("max-output-tokens".into(), Val::S64(256)),
                ("temperature-milli".into(), Val::S64(200)),
            ]))),
        )]
    }

    fn put_new(key: &str, value: &str) -> Vec<Val> {
        vec![Val::Variant(
            "put-new".into(),
            Some(Box::new(Val::Record(vec![
                ("key".into(), Val::String(key.into())),
                ("value".into(), Val::String(value.into())),
            ]))),
        )]
    }

    fn put_existing(key: &str, value: &str, expected: i64) -> Vec<Val> {
        vec![Val::Variant(
            "put-existing".into(),
            Some(Box::new(Val::Record(vec![
                ("key".into(), Val::String(key.into())),
                ("value".into(), Val::String(value.into())),
                ("expected-version".into(), Val::S64(expected)),
            ]))),
        )]
    }

    fn get_value(key: &str) -> Vec<Val> {
        vec![Val::Variant(
            "get".into(),
            Some(Box::new(Val::Record(vec![(
                "key".into(),
                Val::String(key.into()),
            )]))),
        )]
    }

    #[test]
    fn receipt_signature_covers_exact_body() {
        let key = SigningKey::from_bytes(&[7u8; 32]);
        let body = json!({"format": "kototama.component-execution-receipt/v1",
                          "result": 6419002});
        let receipt = receipt_envelope(body.clone(), &key).unwrap();
        let payload = receipt.get("payload").unwrap().as_str().unwrap();
        assert_eq!(serde_json::from_str::<Value>(payload).unwrap(), body);
        let signature_bytes: [u8; 64] =
            hex::decode(receipt.get("signature").unwrap().as_str().unwrap())
                .unwrap()
                .try_into()
                .unwrap();
        let signature = ed25519_dalek::Signature::from_bytes(&signature_bytes);
        key.verifying_key()
            .verify(payload.as_bytes(), &signature)
            .unwrap();
        assert!(
            key.verifying_key()
                .verify(
                    &serde_json::to_vec(&json!({"result": 0})).unwrap(),
                    &signature
                )
                .is_err()
        );
    }

    #[test]
    fn public_bind_is_rejected() {
        let public = "0.0.0.0:18901".parse::<SocketAddr>().unwrap();
        let loopback = "127.0.0.1:18901".parse::<SocketAddr>().unwrap();
        assert!(!public.ip().is_loopback());
        assert!(loopback.ip().is_loopback());
    }

    #[test]
    fn resident_effect_endpoints_are_literal_loopback_only() {
        assert!(loopback_endpoint("http://127.0.0.1:11434/api/show").is_ok());
        assert!(loopback_endpoint("http://localhost:11434/api/show").is_err());
        assert!(loopback_endpoint("http://10.0.0.1:11434/api/show").is_err());
        assert!(loopback_endpoint("https://127.0.0.1:11434/api/show").is_err());
    }

    #[test]
    fn bounded_chunked_response_is_decoded_strictly() {
        assert_eq!(
            decode_chunked(b"4\r\n{\"ok\r\n7\r\n\":true}\r\n0\r\n\r\n", 32).unwrap(),
            br#"{"ok":true}"#
        );
        assert!(decode_chunked(b"20\r\noversize\r\n0\r\n\r\n", 4).is_err());
        assert!(decode_chunked(b"4\r\nno-terminator", 32).is_err());
    }

    #[test]
    fn resident_capability_config_rejects_ambient_fields() {
        let value = json!({
            "format": "kototama.resident-capabilities/v1",
            "http": {
                "endpoint": "http://127.0.0.1:1/http",
                "request-body": {},
                "request-code": 1,
                "max-response-bytes": 1,
                "deadline-ms": 1,
                "audit-id": "http"
            },
            "storage": {
                "log": "/tmp/effects.jsonl",
                "max-write-bytes": 1,
                "deadline-ms": 1,
                "audit-id": "storage"
            },
            "llm": {
                "endpoint": "http://127.0.0.1:1/llm",
                "model": "model",
                "prompt": "prompt",
                "success-code": 1,
                "max-request-bytes": 1,
                "max-response-bytes": 1,
                "deadline-ms": 1,
                "audit-id": "llm"
            },
            "filesystem": "/"
        });
        assert!(serde_json::from_value::<ResidentCapabilityConfig>(value).is_err());
    }

    #[test]
    fn resident_capability_config_can_grant_storage_only() {
        let config: ResidentCapabilityConfig = serde_json::from_value(json!({
            "format": "kototama.resident-capabilities/v1",
            "storage": {
                "log": "/tmp/order-values.jsonl",
                "max-write-bytes": 65536,
                "deadline-ms": 1000,
                "audit-id": "storage-only"
            }
        }))
        .unwrap();
        let imports = resident_imports(&config);
        assert_eq!(imports.len(), 1);
        assert_eq!(imports[0].name, "aiueos-storage-transact");
    }

    #[test]
    fn resident_capability_config_can_grant_loopback_storage_provider() {
        let config: ResidentCapabilityConfig = serde_json::from_value(json!({
            "format": "kototama.resident-capabilities/v1",
            "storage": {
                "endpoint": "http://127.0.0.1:18921/v1/storage",
                "max-request-bytes": 65536,
                "max-write-bytes": 65536,
                "deadline-ms": 1000,
                "audit-id": "commitment-kotobase"
            }
        }))
        .unwrap();
        let imports = resident_imports(&config);
        assert_eq!(imports.len(), 1);
        assert_eq!(
            imports[0].ability.target,
            "http://127.0.0.1:18921/v1/storage"
        );
    }

    #[test]
    fn resident_capability_config_can_grant_structured_llm_only() {
        let config: ResidentCapabilityConfig = serde_json::from_value(json!({
            "format": "kototama.resident-capabilities/v1",
            "llm": {
                "endpoint": "http://127.0.0.1:11434/api/generate",
                "model": "kotoba/murakumo-main",
                "max-request-bytes": 65536,
                "max-response-bytes": 65536,
                "deadline-ms": 1000,
                "audit-id": "commitment-advisor"
            }
        }))
        .unwrap();
        let imports = resident_imports(&config);
        assert_eq!(imports.len(), 1);
        assert_eq!(imports[0].name, "aiueos-llm-generate");
    }

    #[test]
    fn resident_capability_config_can_grant_structured_http_only() {
        let config: ResidentCapabilityConfig = serde_json::from_value(json!({
            "format": "kototama.resident-capabilities/v1",
            "http": {
                "endpoint": "http://127.0.0.1:18080/api/loan/intake",
                "max-request-bytes": 65536,
                "max-response-bytes": 65536,
                "deadline-ms": 1000,
                "audit-id": "isic6492-intake"
            }
        }))
        .unwrap();
        let imports = resident_imports(&config);
        assert_eq!(imports.len(), 1);
        assert_eq!(imports[0].name, "aiueos-http-post");
    }

    #[test]
    fn structured_http_posts_only_to_the_configured_loopback_provider() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!(
            "http://127.0.0.1:{}/api/loan/intake",
            listener.local_addr().unwrap().port()
        );
        let server = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(std::time::Duration::from_secs(1)))
                .unwrap();
            let mut request = Vec::new();
            let mut chunk = [0u8; 4096];
            while !String::from_utf8_lossy(&request).contains("\"requested-principal\":100000") {
                let read = stream.read(&mut chunk).unwrap();
                assert!(read > 0);
                request.extend_from_slice(&chunk[..read]);
            }
            let request = String::from_utf8_lossy(&request);
            assert!(request.starts_with("POST /api/loan/intake HTTP/1.1"));
            let body = br#"{"ok":true,"id":"loan-1"}"#;
            write!(
                stream,
                "HTTP/1.1 201 Created\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            )
            .unwrap();
            stream.write_all(body).unwrap();
        });
        let mut session = EffectSession::new(Arc::new(ResidentCapabilityConfig {
            format: "kototama.resident-capabilities/v1".into(),
            http: Some(HttpCapability {
                endpoint: endpoint.clone(),
                request_body: None,
                request_code: None,
                max_request_bytes: Some(65536),
                max_response_bytes: 65536,
                deadline_ms: 1000,
                audit_id: "isic6492-intake".into(),
            }),
            storage: None,
            llm: None,
        }));
        let mut result = vec![Val::Bool(false)];
        session
            .post_value(
                &http_ability(&endpoint),
                &http_request(r#"{"requested-principal":100000}"#, 1000),
                &mut result,
            )
            .unwrap();
        server.join().unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "ok"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.first(), Some((name, Val::S64(201)))
                            if name == "status")
                        && matches!(fields.last(), Some((name, Val::String(body)))
                            if name == "body" && body.contains("\"loan-1\"")))
        ));
        assert_eq!(session.events.len(), 1);
    }

    #[test]
    fn structured_llm_returns_typed_completion_with_usage() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!(
            "http://127.0.0.1:{}/api/generate",
            listener.local_addr().unwrap().port()
        );
        let server = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(std::time::Duration::from_secs(1)))
                .unwrap();
            let mut request = Vec::new();
            let mut chunk = [0u8; 4096];
            while !String::from_utf8_lossy(&request).contains("\"num_predict\":256") {
                let read = stream.read(&mut chunk).unwrap();
                assert!(read > 0);
                request.extend_from_slice(&chunk[..read]);
            }
            let request = String::from_utf8_lossy(&request);
            assert!(request.contains("\"num_predict\":256"));
            assert!(request.contains("\"system\":\"Use admitted facts only.\""));
            let body = br#"{"response":"{:confidence 0.4}","done_reason":"stop","prompt_eval_count":12,"eval_count":5}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            )
            .unwrap();
            stream.write_all(body).unwrap();
        });
        let mut session = EffectSession::new(Arc::new(ResidentCapabilityConfig {
            format: "kototama.resident-capabilities/v1".into(),
            http: None,
            storage: None,
            llm: Some(LlmCapability {
                endpoint: endpoint.clone(),
                model: "kotoba/murakumo-main".into(),
                prompt: None,
                success_code: None,
                max_request_bytes: 65536,
                max_response_bytes: 65536,
                deadline_ms: 1000,
                audit_id: "commitment-advisor".into(),
            }),
        }));
        let mut result = vec![Val::Bool(false)];
        session
            .generate_value(
                &llm_ability(&endpoint),
                &llm_request("kotoba/murakumo-main"),
                &mut result,
            )
            .unwrap();
        server.join().unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "ok"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.first(), Some((name, Val::String(text)))
                            if name == "text" && text == "{:confidence 0.4}")
                        && matches!(fields.last(), Some((name, Val::S64(5)))
                            if name == "output-tokens"))
        ));
        assert_eq!(session.events.len(), 1);
    }

    #[test]
    fn structured_storage_is_linearized_by_expected_version() {
        let path = env::temp_dir().join(format!(
            "tender-structured-storage-{}-{}.jsonl",
            std::process::id(),
            now_ms().unwrap()
        ));
        let ability = storage_ability(&path);
        let mut session = structured_session(path.clone());
        let mut result = vec![Val::Bool(false)];

        session
            .transact_value(&ability, &put_new("order/1", "v1"), &mut result)
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "written"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.last(), Some((name, Val::S64(1))) if name == "version"))
        ));

        session
            .transact_value(&ability, &put_new("order/1", "duplicate"), &mut result)
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(_)) if case == "conflict-current"
        ));

        session
            .transact_value(&ability, &put_existing("order/1", "stale", 0), &mut result)
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(_)) if case == "conflict-current"
        ));

        session
            .transact_value(&ability, &put_existing("order/1", "v2", 1), &mut result)
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "written"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.last(), Some((name, Val::S64(2))) if name == "version"))
        ));
        assert_eq!(
            conditional_values(&path, 65536).unwrap().get("order/1"),
            Some(&("v2".into(), 2))
        );
        session
            .transact_value(&ability, &get_value("order/1"), &mut result)
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "found"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.get(1), Some((name, Val::String(value)))
                            if name == "value" && value == "v2"))
        ));
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn structured_storage_uses_only_the_configured_loopback_provider() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!(
            "http://127.0.0.1:{}/v1/storage",
            listener.local_addr().unwrap().port()
        );
        let server = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(std::time::Duration::from_secs(1)))
                .unwrap();
            let mut request = Vec::new();
            let mut chunk = [0u8; 4096];
            while !String::from_utf8_lossy(&request).contains(r#""operation":"get""#) {
                let read = stream.read(&mut chunk).unwrap();
                assert!(read > 0);
                request.extend_from_slice(&chunk[..read]);
            }
            let request = String::from_utf8_lossy(&request);
            assert!(request.starts_with("POST /v1/storage HTTP/1.1"));
            assert!(request.contains(r#""key":"application/app-x""#));
            let body =
                br#"{"tag":"found","key":"application/app-x","value":"{\"id\":\"app-x\"}","version":7}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            )
            .unwrap();
            stream.write_all(body).unwrap();
        });
        let mut session = EffectSession::new(Arc::new(ResidentCapabilityConfig {
            format: "kototama.resident-capabilities/v1".into(),
            http: None,
            storage: Some(StorageCapability {
                log: None,
                endpoint: Some(endpoint.clone()),
                max_request_bytes: Some(65536),
                max_write_bytes: 65536,
                deadline_ms: 1000,
                audit_id: "commitment-kotobase".into(),
            }),
            llm: None,
        }));
        let ability = Ability {
            target: endpoint,
            operation: "storage/transact".into(),
            max_bytes: 65536,
            max_items: 1,
            deadline_ms: 1000,
            audit_id: "commitment-kotobase".into(),
        };
        let mut result = vec![Val::Bool(false)];
        session
            .transact_value(&ability, &get_value("application/app-x"), &mut result)
            .unwrap();
        server.join().unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "found"
                    && matches!(payload.as_ref(), Val::Record(fields)
                        if matches!(fields.last(), Some((name, Val::S64(7)))
                            if name == "version"))
        ));
        assert_eq!(session.events.len(), 1);
    }

    #[test]
    fn structured_replace_of_missing_value_fails_closed() {
        let path = env::temp_dir().join(format!(
            "tender-structured-storage-missing-{}-{}.jsonl",
            std::process::id(),
            now_ms().unwrap()
        ));
        let ability = storage_ability(&path);
        let mut session = structured_session(path.clone());
        let mut result = vec![Val::Bool(false)];
        session
            .transact_value(
                &ability,
                &put_existing("order/missing", "value", 1),
                &mut result,
            )
            .unwrap();
        assert!(matches!(
            &result[0],
            Val::Variant(case, Some(payload))
                if case == "conflict-missing"
                    && matches!(payload.as_ref(), Val::Bool(true))
        ));
        assert!(!path.exists(), "a rejected replace performs no write");
    }
}
