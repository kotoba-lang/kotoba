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

mod v2_bindings;

use anyhow::{Context, Result, anyhow, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use wasmtime::component::{Component, Linker, Resource, ResourceTable, ResourceType, Val};
use wasmtime::{Config, Engine, Store, StoreLimits, StoreLimitsBuilder};

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
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

#[derive(Debug, Deserialize)]
struct Import {
    name: String,
    ability: Ability,
}

#[derive(Debug, Deserialize)]
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
    lease: Option<Lease>,
}

fn default_capability_mode() -> String {
    "function".into()
}

#[derive(Debug, Clone, Deserialize)]
struct Lease {
    epoch: u64,
    #[serde(rename = "not-before")]
    not_before: u64,
    #[serde(rename = "expires-at")]
    expires_at: u64,
}

struct Protocol {
    input: BufReader<io::Stdin>,
    output: BufWriter<io::Stdout>,
}

struct State {
    protocol: Arc<Mutex<Protocol>>,
    limits: StoreLimits,
    // This is the host representation backing WIT v2 `own<grant>` /
    // `borrow<grant>`. A guest sees only an opaque component resource handle.
    grants: ResourceTable,
    // Per-import accounting lives in the native host, not the provider
    // process.  A compromised or buggy provider therefore cannot turn a
    // bounded grant into an unbounded sequence of guest calls.
    calls: BTreeMap<String, u64>,
    // A WIT v2 acquisition request is mapped to this exact admitted import;
    // the guest can name an operation but cannot create or widen a grant.
    admitted_imports: BTreeMap<String, Ability>,
    lease: Option<Lease>,
}

#[derive(Debug, Clone)]
pub struct Grant {
    import: String,
    ability: Ability,
}

#[derive(Debug)]
pub struct BytesTask {
    bytes: Option<Vec<u8>>,
    max_bytes: u64,
    max_items: u64,
    deadline: Instant,
    cancelled: bool,
}

#[derive(Debug)]
pub struct BytesStream {
    bytes: Vec<u8>,
    offset: usize,
    remaining_bytes: u64,
    remaining_items: u64,
    deadline: Instant,
    cancelled: bool,
}

fn stream_deadline(ability: &Ability) -> Result<Instant, V2Denial> {
    Instant::now()
        .checked_add(Duration::from_millis(ability.deadline_ms))
        .ok_or(V2Denial::Deadline)
}

fn issue_grant(state: &mut State, name: &str, ability: &Ability) -> Result<Resource<Grant>> {
    validate_ability(name, ability)?;
    state
        .grants
        .push(Grant {
            import: name.to_owned(),
            ability: ability.clone(),
        })
        .map_err(|error| anyhow!("cannot issue Component grant resource: {error}"))
}

fn authorize_grant(
    state: &State,
    grant: &Resource<Grant>,
    name: &str,
    ability: &Ability,
) -> Result<()> {
    // Borrowed resources are looked up in a host-only table. A forged handle,
    // wrong resource type, or a handle issued for another import is denied
    // before provider protocol I/O begins.
    let issued = state
        .grants
        .get(grant)
        .map_err(|error| anyhow!("invalid Component grant resource: {error}"))?;
    if issued.import != name || issued.ability != *ability {
        bail!("Component grant resource does not authorize import {name}");
    }
    Ok(())
}

fn allowed_operation(name: &str) -> Option<&'static str> {
    match name {
        "aiueos-identity-sign" => Some("identity/sign"),
        "aiueos-identity-verify" => Some("identity/verify"),
        "aiueos-hash-sha256" => Some("hash/sha256"),
        "aiueos-http-post" => Some("http/post"),
        "aiueos-log-read" => Some("log/read"),
        "aiueos-clock-now" => Some("clock/now"),
        "aiueos-log-append" => Some("log/append"),
        "aiueos-http-get-stream" => Some("http/get-stream"),
        "aiueos-object-get-stream" => Some("object/get-stream"),
        "aiueos-object-put-block" => Some("object/put-block"),
        "aiueos-object-compare-and-set-ref" => Some("object/compare-and-set-ref"),
        _ => None,
    }
}

fn legacy_binding(name: &str) -> Option<(&'static str, &'static str)> {
    match name {
        "aiueos-clock-now" => Some(("kotoba:application/clock@1.0.0", "now")),
        "aiueos-log-append" => Some(("kotoba:application/log@1.0.0", "append")),
        _ => None,
    }
}

fn validate_ability(name: &str, ability: &Ability) -> Result<()> {
    let Some(expected_operation) = allowed_operation(name) else {
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

fn validate_component_import_names<'a>(names: impl IntoIterator<Item = &'a str>) -> Result<()> {
    for name in names {
        if name.starts_with("wasi:") {
            bail!("ambient WASI Component import is forbidden: {name}");
        }
        if name.starts_with("aiueos:capability/") {
            if name.ends_with("@0.2.0") {
                bail!("typed capability Component ABI @0.2.0 is explicitly unsupported");
            }
            if !name.ends_with("@0.3.0") {
                bail!("unsupported typed capability Component ABI version: {name}");
            }
        }
    }
    Ok(())
}

fn send(protocol: &mut Protocol, value: &Value) -> Result<()> {
    serde_json::to_writer(&mut protocol.output, value)?;
    protocol.output.write_all(b"\n")?;
    protocol.output.flush()?;
    Ok(())
}

fn consume_item_quota(
    calls: &mut BTreeMap<String, u64>,
    name: &str,
    ability: &Ability,
) -> Result<()> {
    let calls = calls.entry(name.to_owned()).or_insert(0);
    *calls = calls
        .checked_add(1)
        .ok_or_else(|| anyhow!("provider call counter overflow"))?;
    if *calls > ability.max_items {
        bail!("import {name} exceeded its admitted max-items quota");
    }
    Ok(())
}

fn provider_call(state: &mut State, name: &str, ability: &Ability, value: i64) -> Result<i64> {
    // The descriptor is captured while linking, never supplied by the guest.
    validate_ability(name, ability)?;
    consume_item_quota(&mut state.calls, name, ability)?;
    let mut protocol = state
        .protocol
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

fn provider_call_typed(
    state: &mut State,
    name: &str,
    ability: &Ability,
    payload: Value,
) -> Result<Value> {
    validate_ability(name, ability)?;
    consume_item_quota(&mut state.calls, name, ability)?;
    let mut protocol = state
        .protocol
        .lock()
        .map_err(|_| anyhow!("protocol lock poisoned"))?;
    send(
        &mut protocol,
        &json!({
            "type": "provider-call",
            "import": name,
            "ability": ability,
            "payload": payload
        }),
    )?;
    let mut response = String::new();
    if protocol.input.read_line(&mut response)? == 0 {
        bail!("provider closed protocol before responding");
    }
    let response: Value = serde_json::from_str(&response).context("invalid provider response")?;
    if response.get("type") != Some(&Value::String("provider-result".into()))
        || response.get("import") != Some(&Value::String(name.into()))
    {
        bail!("provider response does not match typed request");
    }
    let lease = state
        .lease
        .as_ref()
        .ok_or_else(|| anyhow!("typed provider response requires an admitted lease"))?;
    let proof = response
        .get("lease-proof")
        .ok_or_else(|| anyhow!("typed provider response is missing lease proof"))?;
    let epoch = proof.get("epoch").and_then(Value::as_u64);
    let observed_at = proof.get("observed-at").and_then(Value::as_u64);
    let expires_at = proof.get("expires-at").and_then(Value::as_u64);
    if epoch != Some(lease.epoch)
        || expires_at != Some(lease.expires_at)
        || !observed_at.is_some_and(|now| lease.not_before <= now && now < lease.expires_at)
    {
        bail!("typed provider lease proof is expired, revoked, or mismatched");
    }
    if response.get("audit-id") != Some(&Value::String(ability.audit_id.clone()))
        || response
            .get("audit-receipt")
            .and_then(Value::as_str)
            .is_none_or(|receipt| receipt.is_empty())
    {
        bail!("typed provider success requires a matching persisted audit receipt");
    }
    response
        .get("payload")
        .cloned()
        .ok_or_else(|| anyhow!("typed provider response is missing payload"))
}

use crate::v2_bindings::aiueos::capability::capability as v2_capability;
type V2Denial = v2_capability::Denial;

fn denial(error: anyhow::Error) -> V2Denial {
    if error.to_string().contains("max-items quota") {
        V2Denial::Quota
    } else {
        V2Denial::ProviderFailed
    }
}

fn v2_authorize(state: &State, grant: &Resource<Grant>, name: &str) -> Result<Ability> {
    let ability = state
        .admitted_imports
        .get(name)
        .ok_or_else(|| anyhow!("Component did not admit typed import {name}"))?;
    authorize_grant(state, grant, name, ability)?;
    Ok(ability.clone())
}

fn typed_call(
    state: &mut State,
    grant: &Resource<Grant>,
    name: &str,
    payload: Value,
) -> Result<Value, V2Denial> {
    let ability = v2_authorize(state, grant, name).map_err(denial)?;
    if serde_json::to_vec(&payload)
        .map_err(|_| V2Denial::ProviderFailed)?
        .len()
        > ability.max_bytes as usize
    {
        return Err(V2Denial::Quota);
    }
    let result = provider_call_typed(state, name, &ability, payload).map_err(denial)?;
    if serde_json::to_vec(&result)
        .map_err(|_| V2Denial::ProviderFailed)?
        .len()
        > ability.max_bytes as usize
    {
        return Err(V2Denial::Quota);
    }
    Ok(result)
}

fn bytes(value: &Value) -> Result<Vec<u8>, V2Denial> {
    value
        .as_array()
        .ok_or(V2Denial::ProviderFailed)?
        .iter()
        .map(|byte| {
            byte.as_u64()
                .filter(|byte| *byte <= u8::MAX as u64)
                .map(|byte| byte as u8)
                .ok_or(V2Denial::ProviderFailed)
        })
        .collect()
}

fn bytes_response(value: Value) -> Result<v2_capability::BytesResponse, V2Denial> {
    Ok(v2_capability::BytesResponse {
        bytes: bytes(value.get("bytes").ok_or(V2Denial::ProviderFailed)?)?,
    })
}

fn headers(value: &Value) -> Result<Vec<(String, String)>, V2Denial> {
    value
        .as_array()
        .ok_or(V2Denial::ProviderFailed)?
        .iter()
        .map(|entry| {
            let pair = entry.as_array().ok_or(V2Denial::ProviderFailed)?;
            if pair.len() != 2 {
                return Err(V2Denial::ProviderFailed);
            }
            Ok((
                pair[0].as_str().ok_or(V2Denial::ProviderFailed)?.to_owned(),
                pair[1].as_str().ok_or(V2Denial::ProviderFailed)?.to_owned(),
            ))
        })
        .collect()
}

fn http_response(value: Value) -> Result<v2_capability::HttpPostResponse, V2Denial> {
    Ok(v2_capability::HttpPostResponse {
        status: value
            .get("status")
            .and_then(Value::as_u64)
            .filter(|status| *status <= u16::MAX as u64)
            .ok_or(V2Denial::ProviderFailed)? as u16,
        headers: headers(value.get("headers").ok_or(V2Denial::ProviderFailed)?)?,
        body: bytes(value.get("body").ok_or(V2Denial::ProviderFailed)?)?,
    })
}

fn log_read_response(value: Value) -> Result<v2_capability::LogReadResponse, V2Denial> {
    Ok(v2_capability::LogReadResponse {
        next_cursor: value
            .get("next-cursor")
            .and_then(Value::as_u64)
            .ok_or(V2Denial::ProviderFailed)?,
        bytes: bytes(value.get("bytes").ok_or(V2Denial::ProviderFailed)?)?,
    })
}

impl v2_capability::HostGrant for State {
    fn drop(&mut self, rep: Resource<Grant>) -> wasmtime::Result<()> {
        self.grants
            .delete(rep)
            .map(|_| ())
            .map_err(|error| wasmtime::Error::msg(format!("cannot drop Component grant: {error}")))
    }
}

impl v2_capability::HostBytesTask for State {
    fn poll(
        &mut self,
        rep: Resource<BytesTask>,
    ) -> wasmtime::Result<Result<v2_capability::BytesTaskState, V2Denial>> {
        let (bytes, max_bytes, max_items, deadline) = {
            let task = self.grants.get_mut(&rep)?;
            if task.cancelled {
                return Ok(Err(V2Denial::Revoked));
            }
            if Instant::now() >= task.deadline {
                return Ok(Err(V2Denial::Deadline));
            }
            let Some(bytes) = task.bytes.take() else {
                return Ok(Ok(v2_capability::BytesTaskState::Pending));
            };
            (bytes, task.max_bytes, task.max_items, task.deadline)
        };
        let stream = self.grants.push(BytesStream {
            bytes,
            offset: 0,
            remaining_bytes: max_bytes,
            remaining_items: max_items,
            deadline,
            cancelled: false,
        })?;
        Ok(Ok(v2_capability::BytesTaskState::Ready(stream)))
    }

    fn cancel(&mut self, rep: Resource<BytesTask>) -> wasmtime::Result<()> {
        self.grants.get_mut(&rep)?.cancelled = true;
        Ok(())
    }

    fn drop(&mut self, rep: Resource<BytesTask>) -> wasmtime::Result<()> {
        Ok(self.grants.delete(rep).map(|_| ())?)
    }
}

impl v2_capability::HostBytesStream for State {
    fn read(
        &mut self,
        rep: Resource<BytesStream>,
        max_bytes: u32,
    ) -> wasmtime::Result<Result<v2_capability::StreamChunk, V2Denial>> {
        let stream = self.grants.get_mut(&rep)?;
        if stream.cancelled {
            return Ok(Err(V2Denial::Revoked));
        }
        if Instant::now() >= stream.deadline {
            return Ok(Err(V2Denial::Deadline));
        }
        if max_bytes == 0 || stream.remaining_items == 0 {
            return Ok(Err(V2Denial::Quota));
        }
        let available = stream.bytes.len().saturating_sub(stream.offset);
        let count = available
            .min(max_bytes as usize)
            .min(stream.remaining_bytes as usize);
        if available > 0 && count == 0 {
            return Ok(Err(V2Denial::Quota));
        }
        let end = stream.offset + count;
        let chunk = stream.bytes[stream.offset..end].to_vec();
        stream.offset = end;
        stream.remaining_bytes -= count as u64;
        stream.remaining_items -= 1;
        Ok(Ok(v2_capability::StreamChunk {
            bytes: chunk,
            done: stream.offset == stream.bytes.len(),
        }))
    }

    fn cancel(&mut self, rep: Resource<BytesStream>) -> wasmtime::Result<()> {
        self.grants.get_mut(&rep)?.cancelled = true;
        Ok(())
    }

    fn drop(&mut self, rep: Resource<BytesStream>) -> wasmtime::Result<()> {
        Ok(self.grants.delete(rep).map(|_| ())?)
    }
}

impl v2_capability::Host for State {
    fn acquire(
        &mut self,
        request: v2_capability::GrantRequest,
    ) -> wasmtime::Result<Result<Resource<Grant>, V2Denial>> {
        let name = match request {
            v2_capability::GrantRequest::IdentitySign => "aiueos-identity-sign",
            v2_capability::GrantRequest::IdentityVerify => "aiueos-identity-verify",
            v2_capability::GrantRequest::HashSha256 => "aiueos-hash-sha256",
            v2_capability::GrantRequest::HttpPost => "aiueos-http-post",
            v2_capability::GrantRequest::LogRead => "aiueos-log-read",
            v2_capability::GrantRequest::LogAppend => "aiueos-log-append",
            v2_capability::GrantRequest::ClockNow => "aiueos-clock-now",
            v2_capability::GrantRequest::HttpGetStream => "aiueos-http-get-stream",
            v2_capability::GrantRequest::ObjectGetStream => "aiueos-object-get-stream",
            v2_capability::GrantRequest::ObjectPutBlock => "aiueos-object-put-block",
            v2_capability::GrantRequest::ObjectCompareAndSetRef => {
                "aiueos-object-compare-and-set-ref"
            }
        };
        let Some(ability) = self.admitted_imports.get(name).cloned() else {
            return Ok(Err(V2Denial::ProviderFailed));
        };
        Ok(issue_grant(self, name, &ability).map_err(denial))
    }
}

impl v2_bindings::aiueos::capability::identity::Host for State {
    fn sign(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::BytesRequest,
    ) -> wasmtime::Result<Result<v2_capability::BytesResponse, V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-identity-sign",
            json!({"bytes": request.bytes}),
        )
        .and_then(bytes_response))
    }
    fn verify(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::BytesRequest,
    ) -> wasmtime::Result<Result<bool, V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-identity-verify",
            json!({"bytes": request.bytes}),
        )
        .and_then(|value| value.as_bool().ok_or(V2Denial::ProviderFailed)))
    }
}

impl v2_bindings::aiueos::capability::hash::Host for State {
    fn sha256(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::BytesRequest,
    ) -> wasmtime::Result<Result<v2_capability::BytesResponse, V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-hash-sha256",
            json!({"bytes": request.bytes}),
        )
        .and_then(bytes_response))
    }
}

impl v2_bindings::aiueos::capability::http::Host for State {
    fn post(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::HttpPostRequest,
    ) -> wasmtime::Result<Result<v2_capability::HttpPostResponse, V2Denial>> {
        let payload =
            json!({"path": request.path, "headers": request.headers, "body": request.body});
        Ok(typed_call(self, &authority, "aiueos-http-post", payload).and_then(http_response))
    }

    fn get_stream(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::HttpGetStreamRequest,
    ) -> wasmtime::Result<Result<Resource<BytesTask>, V2Denial>> {
        let ability = match v2_authorize(self, &authority, "aiueos-http-get-stream") {
            Ok(ability) => ability,
            Err(error) => return Ok(Err(denial(error))),
        };
        let deadline = match stream_deadline(&ability) {
            Ok(deadline) => deadline,
            Err(error) => return Ok(Err(error)),
        };
        let payload = json!({"path": request.path, "headers": request.headers});
        let value = match typed_call(self, &authority, "aiueos-http-get-stream", payload) {
            Ok(value) => value,
            Err(error) => return Ok(Err(error)),
        };
        let data = match value.get("bytes").map(bytes) {
            Some(Ok(data)) => data,
            _ => return Ok(Err(V2Denial::ProviderFailed)),
        };
        Ok(self
            .grants
            .push(BytesTask {
                bytes: Some(data),
                max_bytes: ability.max_bytes,
                max_items: ability.max_items,
                deadline,
                cancelled: false,
            })
            .map_err(|_| V2Denial::ProviderFailed))
    }
}

impl v2_bindings::aiueos::capability::log::Host for State {
    fn read(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::LogReadRequest,
    ) -> wasmtime::Result<Result<v2_capability::LogReadResponse, V2Denial>> {
        let payload = json!({"cursor": request.cursor, "max-bytes": request.max_bytes});
        Ok(typed_call(self, &authority, "aiueos-log-read", payload).and_then(log_read_response))
    }
    fn append(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::BytesRequest,
    ) -> wasmtime::Result<Result<(), V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-log-append",
            json!({"bytes": request.bytes}),
        )
        .and_then(|value| {
            if value.is_null() {
                Ok(())
            } else {
                Err(V2Denial::ProviderFailed)
            }
        }))
    }
}

impl v2_bindings::aiueos::capability::clock::Host for State {
    fn now(&mut self, authority: Resource<Grant>) -> wasmtime::Result<Result<u64, V2Denial>> {
        Ok(
            typed_call(self, &authority, "aiueos-clock-now", Value::Null)
                .and_then(|value| value.as_u64().ok_or(V2Denial::ProviderFailed)),
        )
    }
}

impl v2_bindings::aiueos::capability::object_store::Host for State {
    fn get_stream(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::ObjectGetStreamRequest,
    ) -> wasmtime::Result<Result<Resource<BytesTask>, V2Denial>> {
        let ability = match v2_authorize(self, &authority, "aiueos-object-get-stream") {
            Ok(ability) => ability,
            Err(error) => return Ok(Err(denial(error))),
        };
        let deadline = match stream_deadline(&ability) {
            Ok(deadline) => deadline,
            Err(error) => return Ok(Err(error)),
        };
        let value = match typed_call(
            self,
            &authority,
            "aiueos-object-get-stream",
            json!({"key": request.key}),
        ) {
            Ok(value) => value,
            Err(error) => return Ok(Err(error)),
        };
        let data = match value.get("bytes").map(bytes) {
            Some(Ok(data)) => data,
            _ => return Ok(Err(V2Denial::ProviderFailed)),
        };
        Ok(self
            .grants
            .push(BytesTask {
                bytes: Some(data),
                max_bytes: ability.max_bytes,
                max_items: ability.max_items,
                deadline,
                cancelled: false,
            })
            .map_err(|_| V2Denial::ProviderFailed))
    }

    fn put_block(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::ObjectPutBlockRequest,
    ) -> wasmtime::Result<Result<(), V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-object-put-block",
            json!({"key": request.key, "bytes": request.bytes}),
        )
        .and_then(|value| {
            value
                .is_null()
                .then_some(())
                .ok_or(V2Denial::ProviderFailed)
        }))
    }

    fn compare_and_set_ref(
        &mut self,
        authority: Resource<Grant>,
        request: v2_capability::ObjectCompareAndSetRefRequest,
    ) -> wasmtime::Result<Result<v2_capability::ObjectCompareAndSetRefResponse, V2Denial>> {
        Ok(typed_call(
            self,
            &authority,
            "aiueos-object-compare-and-set-ref",
            json!({
                "key": request.key,
                "expected-etag": request.expected_etag,
                "bytes": request.bytes
            }),
        )
        .and_then(|value| {
            Ok(v2_capability::ObjectCompareAndSetRefResponse {
                won: value
                    .get("won")
                    .and_then(Value::as_bool)
                    .ok_or(V2Denial::ProviderFailed)?,
                etag: value
                    .get("etag")
                    .map(|etag| {
                        if etag.is_null() {
                            Ok(None)
                        } else {
                            etag.as_str()
                                .map(|etag| Some(etag.to_owned()))
                                .ok_or(V2Denial::ProviderFailed)
                        }
                    })
                    .transpose()?
                    .flatten(),
            })
        }))
    }
}

// With Wasmtime's deliberately minimal feature set its error type does not
// implement `std::error::Error`. Keep that boundary explicit rather than
// enabling unrelated Wasmtime features merely to use `anyhow` conversion.
fn wasmtime_result<T>(result: std::result::Result<T, wasmtime::Error>, context: &str) -> Result<T> {
    result.map_err(|error| anyhow!("{context}: {error}"))
}

fn run(request: Run, protocol: Arc<Mutex<Protocol>>) -> Result<i64> {
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
    validate_component_import_names(
        component
            .component_type()
            .imports(&engine)
            .map(|(name, _)| name),
    )?;
    let limits = StoreLimitsBuilder::new()
        .memory_size(request.memory_pages.saturating_mul(65536) as usize)
        .build();
    let mut store = Store::new(
        &engine,
        State {
            protocol,
            limits,
            grants: ResourceTable::new(),
            calls: BTreeMap::new(),
            admitted_imports: imports.clone(),
            lease: request.lease,
        },
    );
    store.limiter(|state| &mut state.limits);
    wasmtime_result(store.set_fuel(request.fuel), "cannot set Component fuel")?;

    let mut linker = Linker::<State>::new(&engine);
    // Register the generated v2 interfaces as named Component imports. This
    // remains separate from the legacy scalar v1 bindings below and adds no
    // WASI or fallback namespace.
    wasmtime_result(
        v2_bindings::Application::add_to_linker::<State, wasmtime::component::HasSelf<State>>(
            &mut linker,
            |state| state,
        ),
        "cannot bind typed Component capability interfaces",
    )?;
    for (name, ability) in imports {
        let import_name = name.clone();
        // The generated v0.3 linker above owns typed imports. Only legacy
        // compiler artifacts need these scalar compatibility bindings.
        let Some((interface, function)) = legacy_binding(&name) else {
            continue;
        };
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
            wasmtime_result(
                instance.func_wrap(function, move |mut cx, (value,): (i64,)| {
                    provider_call(cx.data_mut(), &import_name, &ability, value)
                        .map(|result| (result,))
                        .map_err(|error| wasmtime::Error::msg(error.to_string()))
                }),
                "cannot bind admitted Component import",
            )?;
        }
    }
    let instance = wasmtime_result(
        linker.instantiate(&mut store, &component),
        "Component imports did not match the admitted bindings",
    )?;
    let function = instance
        .get_func(&mut store, "main")
        .ok_or_else(|| anyhow!("Component does not export main"))?;
    let mut results = [Val::S64(0)];
    wasmtime_result(
        function.call(&mut store, &[], &mut results),
        "Component main failed",
    )?;
    match results.into_iter().next() {
        Some(Val::S64(value)) => Ok(value),
        _ => bail!("Component main must return s64"),
    }
}

fn main() {
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
            protocol.clone(),
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

    fn bounded_ability() -> Ability {
        Ability {
            target: "clock://monotonic".into(),
            operation: "clock/now".into(),
            max_bytes: 1,
            max_items: 1,
            deadline_ms: 1,
            audit_id: "native-quota-test".into(),
        }
    }

    #[test]
    fn native_host_rejects_calls_after_the_admitted_item_quota() {
        let mut calls = BTreeMap::new();
        let ability = bounded_ability();
        consume_item_quota(&mut calls, "aiueos-clock-now", &ability).unwrap();
        assert!(consume_item_quota(&mut calls, "aiueos-clock-now", &ability).is_err());
    }

    #[test]
    fn host_only_grant_resource_cannot_cross_named_imports() {
        let protocol = Arc::new(Mutex::new(Protocol {
            input: BufReader::new(io::stdin()),
            output: BufWriter::new(io::stdout()),
        }));
        let mut state = State {
            protocol,
            limits: StoreLimitsBuilder::new().build(),
            grants: ResourceTable::new(),
            calls: BTreeMap::new(),
            admitted_imports: BTreeMap::new(),
            lease: None,
        };
        let ability = bounded_ability();
        let grant = issue_grant(&mut state, "aiueos-clock-now", &ability).unwrap();
        assert!(authorize_grant(&state, &grant, "aiueos-clock-now", &ability).is_ok());
        assert!(authorize_grant(&state, &grant, "aiueos-log-append", &ability).is_err());
    }

    #[test]
    fn typed_acquire_issues_only_the_requested_admitted_grant() {
        let protocol = Arc::new(Mutex::new(Protocol {
            input: BufReader::new(io::stdin()),
            output: BufWriter::new(io::stdout()),
        }));
        let ability = bounded_ability();
        let mut state = State {
            protocol,
            limits: StoreLimitsBuilder::new().build(),
            grants: ResourceTable::new(),
            calls: BTreeMap::new(),
            admitted_imports: BTreeMap::from([("aiueos-clock-now".into(), ability.clone())]),
            lease: None,
        };
        let grant = <State as v2_capability::Host>::acquire(
            &mut state,
            v2_capability::GrantRequest::ClockNow,
        )
        .unwrap()
        .unwrap();
        assert!(authorize_grant(&state, &grant, "aiueos-clock-now", &ability).is_ok());
        assert!(
            <State as v2_capability::Host>::acquire(
                &mut state,
                v2_capability::GrantRequest::HttpPost,
            )
            .unwrap()
            .is_err()
        );
    }

    #[test]
    fn old_typed_component_abi_is_rejected_explicitly() {
        assert!(
            validate_component_import_names([
                "aiueos:capability/capability@0.3.0",
                "aiueos:capability/clock@0.3.0",
            ])
            .is_ok()
        );
        let error =
            validate_component_import_names(["aiueos:capability/capability@0.2.0"]).unwrap_err();
        assert!(
            error
                .to_string()
                .contains("@0.2.0 is explicitly unsupported")
        );
        assert!(validate_component_import_names(["wasi:cli/environment@0.2.0"]).is_err());
    }

    #[test]
    fn stream_resources_enforce_byte_and_item_budgets_and_cancellation() {
        let protocol = Arc::new(Mutex::new(Protocol {
            input: BufReader::new(io::stdin()),
            output: BufWriter::new(io::stdout()),
        }));
        let mut state = State {
            protocol,
            limits: StoreLimitsBuilder::new().build(),
            grants: ResourceTable::new(),
            calls: BTreeMap::new(),
            admitted_imports: BTreeMap::new(),
            lease: None,
        };
        let task = state
            .grants
            .push(BytesTask {
                bytes: Some(vec![1, 2, 3, 4]),
                max_bytes: 3,
                max_items: 2,
                deadline: Instant::now() + Duration::from_secs(1),
                cancelled: false,
            })
            .unwrap();
        let stream = match <State as v2_capability::HostBytesTask>::poll(&mut state, task)
            .unwrap()
            .unwrap()
        {
            v2_capability::BytesTaskState::Ready(stream) => stream,
            v2_capability::BytesTaskState::Pending => panic!("host task is immediately ready"),
        };
        let first = <State as v2_capability::HostBytesStream>::read(
            &mut state,
            Resource::new_borrow(stream.rep()),
            2,
        )
        .unwrap()
        .unwrap();
        assert_eq!(vec![1, 2], first.bytes);
        assert!(!first.done);
        let second = <State as v2_capability::HostBytesStream>::read(
            &mut state,
            Resource::new_borrow(stream.rep()),
            2,
        )
        .unwrap()
        .unwrap();
        assert_eq!(vec![3], second.bytes);
        assert!(!second.done);
        assert!(
            <State as v2_capability::HostBytesStream>::read(
                &mut state,
                Resource::new_borrow(stream.rep()),
                1,
            )
            .unwrap()
            .is_err()
        );
        <State as v2_capability::HostBytesStream>::cancel(
            &mut state,
            Resource::new_borrow(stream.rep()),
        )
        .unwrap();
        assert!(
            <State as v2_capability::HostBytesStream>::read(
                &mut state,
                Resource::new_borrow(stream.rep()),
                1,
            )
            .unwrap()
            .is_err()
        );
    }

    #[test]
    fn task_and_stream_resources_fail_closed_after_the_ability_deadline() {
        let protocol = Arc::new(Mutex::new(Protocol {
            input: BufReader::new(io::stdin()),
            output: BufWriter::new(io::stdout()),
        }));
        let mut state = State {
            protocol,
            limits: StoreLimitsBuilder::new().build(),
            grants: ResourceTable::new(),
            calls: BTreeMap::new(),
            admitted_imports: BTreeMap::new(),
            lease: None,
        };
        let task = state
            .grants
            .push(BytesTask {
                bytes: Some(vec![1]),
                max_bytes: 1,
                max_items: 1,
                deadline: Instant::now(),
                cancelled: false,
            })
            .unwrap();
        assert!(matches!(
            <State as v2_capability::HostBytesTask>::poll(&mut state, task).unwrap(),
            Err(V2Denial::Deadline)
        ));

        let stream = state
            .grants
            .push(BytesStream {
                bytes: vec![1],
                offset: 0,
                remaining_bytes: 1,
                remaining_items: 1,
                deadline: Instant::now(),
                cancelled: false,
            })
            .unwrap();
        assert!(matches!(
            <State as v2_capability::HostBytesStream>::read(&mut state, stream, 1).unwrap(),
            Err(V2Denial::Deadline)
        ));
    }
}
