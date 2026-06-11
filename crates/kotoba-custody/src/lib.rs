//! kotoba-custody — t-of-N key custody for the sealed cold tier
//! (ADR-sealed-cold-tier R3).
//!
//! - [`shares`]   — R3a share plane: Shamir split / HPKE-wrap / open / combine.
//! - [`protocol`] — R3b custodian protocol core: the verify-then-release
//!   decision and requester-side recombination, transport-agnostic.

pub mod protocol;
pub mod shares;

pub use protocol::{
    combine_granted, handle_key_share_request, GrantedShare, KeyShareRequest, KeyShareResponse,
    ProtocolError,
};
pub use shares::{
    combine_key, open_share, split_key, CustodianShare, CustodyError, RecoveredShare, KEY_LEN,
};
