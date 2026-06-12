//! git **wire protocol** — pkt-line framing, pack encode/ingest, and the
//! smart-HTTP service layer that lets a real `git` client clone, fetch and push
//! against a [`crate::GitStore`].
//!
//! The substrate underneath is unchanged: every git object is still a
//! content-addressed [`kotoba_core::cid::KotobaCid`] block (IPFS) plus its
//! `:git/*` Datom projection (datomic). This module is purely the transport that
//! moves objects in and out over the network — it adds no new storage model.

pub mod pack_encode;
pub mod pack_ingest;
pub mod pktline;
pub mod smart_http;

pub use smart_http::{advertise_refs, receive_pack, upload_pack, GitService};
