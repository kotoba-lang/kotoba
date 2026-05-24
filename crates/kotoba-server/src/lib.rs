pub mod mcp;
pub mod server;
pub mod xrpc;

use std::sync::Arc;
use axum::{
    Router,
    routing::{get, post},
};

use tower_http::trace::TraceLayer;
use crate::server::KotobaState;

pub fn build_router(state: Arc<KotobaState>) -> Router {
    Router::new()
        .route("/_app/meta",  get(xrpc::health))
        .route("/health",     get(xrpc::health))
        .route(
            &format!("/xrpc/{}", xrpc::NSID_QUAD_CREATE),
            post(xrpc::quad_create),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_INVOKE_RUN),
            post(xrpc::invoke_run),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_NODE_STATUS),
            get(xrpc::node_status),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_BLOCK_PUT),
            post(xrpc::block_put),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_BLOCK_GET),
            get(xrpc::block_get),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_COMMIT_GET),
            get(xrpc::commit_get),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_COMMIT_STORE),
            post(xrpc::commit_store),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_GRAPH_QUERY),
            get(xrpc::graph_query),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_WEIGHT_PUT),
            post(xrpc::weight_put),
        )
        .with_state(state)
        .layer(TraceLayer::new_for_http())
}
