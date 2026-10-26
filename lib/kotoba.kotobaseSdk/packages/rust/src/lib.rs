//! Async Rust client for the Kotobase unified query envelope.

pub mod merge;

use reqwest::StatusCode;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

const QUERY_PATH: &str = "/xrpc/ai.gftd.apps.kotobase.query.execute";

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum QueryLanguage {
    Datalog,
    Cypher,
    Gremlin,
    Graphdb,
    Graphql,
    Sparql,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct QueryOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout_ms: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub as_of: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explain: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub emit_cid: Option<bool>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub enum QueryDocument {
    Text(String),
    Gremlin(Vec<Vec<Value>>),
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct QueryRequest {
    pub language: QueryLanguage,
    pub query: QueryDocument,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parameters: Option<BTreeMap<String, Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub database: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collections: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<QueryOptions>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct QueryMeta {
    pub request_id: String,
    pub elapsed_ms: u64,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct QueryResult {
    pub ok: bool,
    pub language: QueryLanguage,
    pub data: Value,
    pub meta: QueryMeta,
    #[serde(default)]
    pub warnings: Vec<String>,
}

#[derive(Clone, Debug, Default)]
pub struct RequestOptions {
    pub parameters: Option<BTreeMap<String, Value>>,
    pub database: Option<String>,
    pub collections: Option<Vec<String>>,
    pub options: Option<QueryOptions>,
    pub request_id: Option<String>,
}

#[derive(Debug, thiserror::Error)]
#[error("{message}")]
pub struct KotobaseError {
    pub code: String,
    pub message: String,
    pub status: Option<StatusCode>,
    pub retryable: bool,
    pub request_id: Option<String>,
    pub details: Option<Value>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ErrorEnvelope {
    error: ErrorDetail,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ErrorDetail {
    code: String,
    message: String,
    retryable: bool,
    request_id: Option<String>,
    details: Option<Value>,
}

#[derive(Clone)]
pub struct KotobaseClient {
    endpoint: String,
    token: Option<String>,
    http: reqwest::Client,
}

impl KotobaseClient {
    pub fn new(endpoint: impl Into<String>) -> Self {
        Self {
            endpoint: endpoint.into().trim_end_matches('/').to_owned(),
            token: None,
            http: reqwest::Client::new(),
        }
    }

    pub fn with_token(mut self, token: impl Into<String>) -> Self {
        self.token = Some(token.into());
        self
    }

    pub async fn query(&self, request: QueryRequest, request_id: Option<&str>) -> Result<QueryResult, KotobaseError> {
        validate_request(&request)?;
        let mut builder = self.http
            .post(format!("{}{}", self.endpoint, QUERY_PATH))
            .header("accept", "application/json")
            .json(&request);
        if let Some(token) = &self.token {
            builder = builder.bearer_auth(token);
        }
        if let Some(request_id) = request_id {
            builder = builder.header("x-request-id", request_id);
        }
        let response = builder.send().await.map_err(transport_error)?;
        let status = response.status();
        let bytes = response.bytes().await.map_err(transport_error)?;
        if !status.is_success() {
            let detail = serde_json::from_slice::<ErrorEnvelope>(&bytes).ok().map(|v| v.error);
            return Err(KotobaseError {
                code: detail.as_ref().map(|v| v.code.clone()).unwrap_or_else(|| "query_failed".into()),
                message: detail.as_ref().map(|v| v.message.clone()).unwrap_or_else(|| format!("Kotobase query failed with HTTP {status}")),
                status: Some(status),
                retryable: detail.as_ref().map(|v| v.retryable).unwrap_or(status.is_server_error()),
                request_id: detail.as_ref().and_then(|v| v.request_id.clone()),
                details: detail.and_then(|v| v.details),
            });
        }
        serde_json::from_slice(&bytes).map_err(|error| KotobaseError {
            code: "invalid_response".into(),
            message: error.to_string(),
            status: Some(status),
            retryable: false,
            request_id: None,
            details: None,
        })
    }

    pub async fn datalog(&self, query: impl Into<String>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        self.text_query(QueryLanguage::Datalog, query.into(), options).await
    }

    pub async fn cypher(&self, query: impl Into<String>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        self.text_query(QueryLanguage::Cypher, query.into(), options).await
    }

    pub async fn graphql(&self, query: impl Into<String>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        self.text_query(QueryLanguage::Graphql, query.into(), options).await
    }

    pub async fn graphdb(&self, query: impl Into<String>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        self.text_query(QueryLanguage::Graphdb, query.into(), options).await
    }

    pub async fn sparql(&self, query: impl Into<String>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        self.text_query(QueryLanguage::Sparql, query.into(), options).await
    }

    pub async fn gremlin(&self, bytecode: Vec<Vec<Value>>, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        let request_id = options.request_id.clone();
        self.query(build_request(QueryLanguage::Gremlin, QueryDocument::Gremlin(bytecode), options), request_id.as_deref()).await
    }

    async fn text_query(&self, language: QueryLanguage, query: String, options: RequestOptions) -> Result<QueryResult, KotobaseError> {
        let request_id = options.request_id.clone();
        self.query(build_request(language, QueryDocument::Text(query), options), request_id.as_deref()).await
    }
}

fn build_request(language: QueryLanguage, query: QueryDocument, input: RequestOptions) -> QueryRequest {
    QueryRequest {
        language,
        query,
        parameters: input.parameters,
        database: input.database,
        collections: input.collections,
        options: input.options,
    }
}

fn validate_request(request: &QueryRequest) -> Result<(), KotobaseError> {
    let valid = match (&request.language, &request.query) {
        (QueryLanguage::Gremlin, QueryDocument::Gremlin(steps)) => !steps.is_empty(),
        (QueryLanguage::Gremlin, _) => false,
        (_, QueryDocument::Text(text)) => !text.trim().is_empty(),
        _ => false,
    };
    if valid {
        Ok(())
    } else {
        Err(KotobaseError {
            code: "invalid_request".into(),
            message: "query document does not match its language".into(),
            status: None,
            retryable: false,
            request_id: None,
            details: None,
        })
    }
}

fn transport_error(error: reqwest::Error) -> KotobaseError {
    KotobaseError {
        code: "transport_error".into(),
        message: error.to_string(),
        status: error.status(),
        retryable: true,
        request_id: None,
        details: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn common_envelope_serializes_camel_case_options() {
        let request = build_request(
            QueryLanguage::Cypher,
            QueryDocument::Text("MATCH (n:users) RETURN n.name".into()),
            RequestOptions {
                parameters: Some(BTreeMap::from([("role".into(), json!("admin"))])),
                options: Some(QueryOptions { timeout_ms: Some(2500), ..Default::default() }),
                ..Default::default()
            },
        );
        let value = serde_json::to_value(request).unwrap();
        assert_eq!(value["language"], "cypher");
        assert_eq!(value["options"]["timeoutMs"], 2500);
    }

    #[test]
    fn gremlin_text_is_rejected() {
        let request = QueryRequest {
            language: QueryLanguage::Gremlin,
            query: QueryDocument::Text("g.V()".into()),
            parameters: None,
            database: None,
            collections: None,
            options: None,
        };
        assert_eq!(validate_request(&request).unwrap_err().code, "invalid_request");
    }

    #[test]
    fn graphdb_serializes_as_a_distinct_language() {
        let request = build_request(
            QueryLanguage::Graphdb,
            QueryDocument::Text("SELECT ?s WHERE { ?s ?p ?o }".into()),
            RequestOptions { database: Some("default".into()), ..Default::default() },
        );
        let value = serde_json::to_value(request).unwrap();
        assert_eq!(value["language"], "graphdb");
        assert_eq!(value["database"], "default");
    }
}
