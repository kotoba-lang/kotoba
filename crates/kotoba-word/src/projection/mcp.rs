//! MCP projection — exposes a root as MCP tools.
//!
//! Same handrolled JSON-RPC 2.0 style as kotoba-server/src/mcp.rs (no SDK
//! dependency). Two entry points:
//! - [`handle`] — pure request→response, mountable behind any transport
//!   (kotoba-server can route its POST /mcp here for word tools)
//! - [`serve_stdio`] — newline-delimited JSON-RPC over stdin/stdout, the MCP
//!   stdio transport, so any agent can attach to a root directly.

use std::sync::Arc;

use serde_json::{json, Value};

use crate::root::Root;

pub const PROTOCOL_VERSION: &str = "2024-11-05";

/// Tool name = NSID segments under the root, joined by `_`, prefixed `word_`.
/// `com.etzhayyim.apps.kotoba.word.git.status` → `word_git_status`.
pub fn tool_name(root: &Root, nsid: &str) -> String {
    let suffix = nsid
        .strip_prefix(&format!("{}.", root.nsid_root()))
        .unwrap_or(nsid);
    format!("word_{}", suffix.replace('.', "_"))
}

pub fn nsid_for_tool(root: &Root, tool: &str) -> Option<String> {
    root.words()
        .map(|w| w.nsid.clone())
        .find(|nsid| tool_name(root, nsid) == *tool)
}

pub fn tools_list(root: &Root) -> Value {
    let tools: Vec<Value> = root
        .words()
        .map(|w| {
            json!({
                "name": tool_name(root, &w.nsid),
                "description": format!("[{}] {} (caps: {})",
                    w.nsid,
                    w.description,
                    if w.caps.is_empty() { "none".to_string() }
                    else { w.caps.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(", ") }),
                "inputSchema": w.input_schema,
            })
        })
        .collect();
    json!({ "tools": tools })
}

fn rpc_result(id: Option<Value>, result: Value) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "result": result })
}

fn rpc_error(id: Option<Value>, code: i64, message: String) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message } })
}

/// Handle one JSON-RPC request. Returns `None` for notifications.
pub async fn handle(root: &Root, req: Value) -> Option<Value> {
    let id = req.get("id").cloned();
    let method = req.get("method").and_then(|m| m.as_str()).unwrap_or("");

    match method {
        "initialize" => Some(rpc_result(
            id,
            json!({
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": { "tools": {} },
                "serverInfo": {
                    "name": format!("kotoba-word ({})", root.nsid_root()),
                    "version": env!("CARGO_PKG_VERSION"),
                },
            }),
        )),
        "notifications/initialized" => None,
        "ping" => Some(rpc_result(id, json!({}))),
        "tools/list" => Some(rpc_result(id, tools_list(root))),
        "tools/call" => {
            let params = req.get("params").cloned().unwrap_or(json!({}));
            let tool = params.get("name").and_then(|n| n.as_str()).unwrap_or("");
            let args = params.get("arguments").cloned().unwrap_or(json!({}));
            let Some(nsid) = nsid_for_tool(root, tool) else {
                return Some(rpc_error(id, -32602, format!("unknown tool `{tool}`")));
            };
            match root.invoke(&nsid, args).await {
                Ok(out) => Some(rpc_result(
                    id,
                    json!({
                        "content": [{ "type": "text", "text": out.to_string() }],
                        "isError": false,
                    }),
                )),
                Err(e) => Some(rpc_result(
                    id,
                    json!({
                        "content": [{ "type": "text", "text": e.to_string() }],
                        "isError": true,
                    }),
                )),
            }
        }
        _ => Some(rpc_error(id, -32601, format!("method `{method}` not found"))),
    }
}

/// MCP stdio transport: newline-delimited JSON-RPC on stdin/stdout.
pub async fn serve_stdio(root: Arc<Root>) -> anyhow::Result<()> {
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

    let stdin = BufReader::new(tokio::io::stdin());
    let mut stdout = tokio::io::stdout();
    let mut lines = stdin.lines();

    while let Some(line) = lines.next_line().await? {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let req: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => {
                let resp = rpc_error(None, -32700, format!("parse error: {e}"));
                stdout
                    .write_all(format!("{resp}\n").as_bytes())
                    .await?;
                stdout.flush().await?;
                continue;
            }
        };
        if let Some(resp) = handle(&root, req).await {
            stdout.write_all(format!("{resp}\n").as_bytes()).await?;
            stdout.flush().await?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::word::{Word, WordMode};
    use schemars::JsonSchema;
    use serde::{Deserialize, Serialize};

    #[derive(Deserialize, Serialize, JsonSchema)]
    struct AddIn {
        a: f64,
        b: f64,
    }
    #[derive(Deserialize, Serialize, JsonSchema)]
    struct AddOut {
        sum: f64,
    }

    fn test_root() -> Root {
        let mut root = Root::new("com.example.word", vec![]).unwrap();
        root.register(
            Word::closure(
                "com.example.word.math.add",
                "add",
                WordMode::Query,
                vec![],
                |i: AddIn, _ctx| async move { Ok(AddOut { sum: i.a + i.b }) },
            )
            .unwrap(),
        )
        .unwrap();
        root
    }

    #[test]
    fn tool_name_mapping_roundtrips() {
        let root = test_root();
        let name = tool_name(&root, "com.example.word.math.add");
        assert_eq!(name, "word_math_add");
        assert_eq!(
            nsid_for_tool(&root, &name).unwrap(),
            "com.example.word.math.add"
        );
    }

    #[tokio::test]
    async fn initialize_list_call() {
        let root = test_root();

        let init = handle(&root, json!({"jsonrpc":"2.0","id":1,"method":"initialize"}))
            .await
            .unwrap();
        assert_eq!(init["result"]["protocolVersion"], PROTOCOL_VERSION);

        let list = handle(&root, json!({"jsonrpc":"2.0","id":2,"method":"tools/list"}))
            .await
            .unwrap();
        let tools = list["result"]["tools"].as_array().unwrap();
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0]["name"], "word_math_add");
        assert_eq!(tools[0]["inputSchema"]["type"], "object");

        let call = handle(
            &root,
            json!({"jsonrpc":"2.0","id":3,"method":"tools/call",
                   "params":{"name":"word_math_add","arguments":{"a":1.0,"b":2.0}}}),
        )
        .await
        .unwrap();
        assert_eq!(call["result"]["isError"], false);
        let text = call["result"]["content"][0]["text"].as_str().unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(text).unwrap(),
            json!({"sum": 3.0})
        );
    }

    #[tokio::test]
    async fn call_error_paths() {
        let root = test_root();
        let bad_tool = handle(
            &root,
            json!({"jsonrpc":"2.0","id":4,"method":"tools/call",
                   "params":{"name":"word_nope","arguments":{}}}),
        )
        .await
        .unwrap();
        assert_eq!(bad_tool["error"]["code"], -32602);

        let bad_input = handle(
            &root,
            json!({"jsonrpc":"2.0","id":5,"method":"tools/call",
                   "params":{"name":"word_math_add","arguments":{"a":"x"}}}),
        )
        .await
        .unwrap();
        assert_eq!(bad_input["result"]["isError"], true);

        // notification → no response
        assert!(handle(
            &root,
            json!({"jsonrpc":"2.0","method":"notifications/initialized"})
        )
        .await
        .is_none());
    }
}
