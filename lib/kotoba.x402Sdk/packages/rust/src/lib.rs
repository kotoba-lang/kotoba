//! x402 client: read the 402, pay, retry.
//!
//! The loop is four HTTP steps. This crate owns the parsing, the choosing and
//! the encoding, and injects the other two: signing and transport are traits
//! the caller implements.
//!
//! That is why the dependency list is `serde` and nothing else. This crate
//! holds no key and opens no socket, so it is neither a place a key can leak
//! from nor a reason to pull a TLS stack into a program that already has one.
//!
//! See `../../spec/wire.md` for the contract every package here implements.

use serde::{Deserialize, Serialize};
use std::collections::{BTreeSet, HashMap};

/// Sent by callers implementing [`Transport`]. Some edges answer 403 to a
/// default agent -- measured 2026-09-01, Python's urllib default is rejected
/// by x402.nexus outright, and that failure looks like authorisation rather
/// than like a bot rule.
pub const USER_AGENT: &str = "x402-sdk-rust/0.1.0 (+https://github.com/kotoba-lang/x402-sdk)";

/// One acceptable payment, stated completely by the seller.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Offer {
    pub scheme: String,
    pub network: String,
    pub asset: String,
    #[serde(rename = "payTo")]
    pub pay_to: String,
    #[serde(rename = "maxAmountRequired")]
    pub max_amount_required: String,
    #[serde(rename = "maxTimeoutSeconds", default)]
    pub max_timeout_seconds: Option<u64>,
    /// The EIP-712 domain of `asset` on `network`. Never a constant.
    #[serde(default)]
    pub extra: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Challenge {
    #[serde(rename = "x402Version", default)]
    pub x402_version: u32,
    pub accepts: Vec<Offer>,
    #[serde(default)]
    pub error: Option<String>,
}

/// What this buyer will pay. Every field is required: a buyer with an empty
/// policy pays anything, and a default ceiling is a limit nobody chose.
#[derive(Debug, Clone)]
pub struct Policy {
    pub networks: Vec<String>,
    pub assets: Vec<String>,
    pub max_amount: u128,
    /// Empty means `exact` and `transaction`.
    pub schemes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Authorization {
    pub from: String,
    pub to: String,
    pub value: String,
    #[serde(rename = "validAfter")]
    pub valid_after: String,
    #[serde(rename = "validBefore")]
    pub valid_before: String,
    pub nonce: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Domain {
    pub name: String,
    pub version: String,
    pub chain_id: u64,
    pub verifying_contract: String,
}

/// A policy decision, distinct from a transport error.
#[derive(Debug, Clone, PartialEq)]
pub struct Refusal {
    pub refused: String,
    pub detail: String,
}

#[derive(Debug)]
pub enum Error {
    Refused(Refusal),
    UnknownNetwork(String),
    NoDomain,
    UnsupportedScheme(String),
    Transport(String),
    Signing(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Refused(r) => write!(f, "x402: {}: {}", r.refused, r.detail),
            Error::UnknownNetwork(n) => write!(f, "x402: unknown network {n:?}"),
            Error::NoDomain => write!(
                f,
                "x402: the offer carries no EIP-712 domain (extra.name/version); signing \
                 under a guessed one recovers a different address and is rejected as a \
                 bad signature"
            ),
            Error::UnsupportedScheme(s) => write!(
                f,
                "x402: this client signs the 'exact' scheme; the offer asks for {s:?}, \
                 which needs a transfer this crate does not make"
            ),
            Error::Transport(m) => write!(f, "x402: transport: {m}"),
            Error::Signing(m) => write!(f, "x402: signing: {m}"),
        }
    }
}
impl std::error::Error for Error {}

/// The chain id for a network, or an error.
///
/// Never a default: a wrong chainId in an EIP-712 domain makes a valid
/// signature recover a different address, and the payment is rejected as a bad
/// signature -- which reads like the buyer's fault.
pub fn chain_id_for(network: &str) -> Result<u64, Error> {
    match network {
        "base" | "eip155:8453" => Ok(8453),
        "base-sepolia" | "eip155:84532" => Ok(84532),
        other => Err(Error::UnknownNetwork(other.to_string())),
    }
}

/// A 402 body as a challenge, or `None`.
///
/// `None` is only ever "not a challenge". A caller must be able to tell that
/// from a challenge with nothing usable in it.
pub fn parse_challenge(status: u16, body: &[u8]) -> Option<Challenge> {
    if status != 402 {
        return None;
    }
    serde_json::from_slice::<Challenge>(body).ok()
}

/// The cheapest offer the policy allows, or a refusal naming why.
///
/// NOT `accepts[0]`. Sellers list the same resource on mainnet and on a
/// testnet in their own order, and taking the first is how a buyer pays real
/// money to rehearse.
///
/// Every failing check is recorded, not just the first: an offer on the wrong
/// network usually names that network's token too, and a caller told only
/// `network-not-allowed` will fix the network and be refused again.
pub fn select_offer<'a>(
    challenge: Option<&'a Challenge>,
    policy: &Policy,
) -> Result<&'a Offer, Refusal> {
    let challenge = match challenge {
        Some(c) => c,
        None => {
            return Err(Refusal {
                refused: "not-a-challenge".into(),
                detail: "the response was not a 402 x402 challenge".into(),
            })
        }
    };
    if policy.networks.is_empty() || policy.assets.is_empty() {
        return Err(Refusal {
            refused: "no-policy".into(),
            detail: "a buyer without a policy would pay anything".into(),
        });
    }
    let default_schemes = ["exact".to_string(), "transaction".to_string()];
    let schemes: &[String] = if policy.schemes.is_empty() {
        &default_schemes
    } else {
        &policy.schemes
    };

    let mut reasons: BTreeSet<String> = BTreeSet::new();
    let mut allowed: Vec<&Offer> = Vec::new();
    for o in &challenge.accepts {
        let mut fail: Vec<&str> = Vec::new();
        if !schemes.iter().any(|s| s == &o.scheme) {
            fail.push("scheme-not-allowed");
        }
        if !policy.networks.iter().any(|n| n == &o.network) {
            fail.push("network-not-allowed");
        }
        if !policy
            .assets
            .iter()
            .any(|a| a.eq_ignore_ascii_case(&o.asset))
        {
            fail.push("asset-not-allowed");
        }
        match o.max_amount_required.parse::<u128>() {
            Err(_) => fail.push("unparseable-amount"),
            Ok(v) if v > policy.max_amount => fail.push("over-budget"),
            Ok(_) => {}
        }
        for f in &fail {
            reasons.insert((*f).to_string());
        }
        if fail.is_empty() {
            allowed.push(o);
        }
    }
    if allowed.is_empty() {
        let refused = if reasons.is_empty() {
            "no-offers".to_string()
        } else {
            reasons.into_iter().collect::<Vec<_>>().join("+")
        };
        return Err(Refusal {
            refused,
            detail: format!(
                "none of {} offer(s) satisfied the policy",
                challenge.accepts.len()
            ),
        });
    }
    allowed.sort_by_key(|o| o.max_amount_required.parse::<u128>().unwrap_or(u128::MAX));
    Ok(allowed[0])
}

pub fn build_authorization(offer: &Offer, from: &str, now: u64, nonce: &str) -> Authorization {
    Authorization {
        from: from.to_string(),
        to: offer.pay_to.clone(),
        value: offer.max_amount_required.clone(),
        valid_after: "0".into(),
        valid_before: (now + offer.max_timeout_seconds.unwrap_or(60)).to_string(),
        nonce: nonce.to_string(),
    }
}

/// Base64 of the JSON payload, for the `X-PAYMENT` header.
pub fn encode_payment_header(v: &serde_json::Value) -> String {
    base64(serde_json::to_string(v).unwrap_or_default().as_bytes())
}

fn base64(input: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(input.len().div_ceil(3) * 4);
    for c in input.chunks(3) {
        let b = [c[0], *c.get(1).unwrap_or(&0), *c.get(2).unwrap_or(&0)];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        out.push(if c.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if c.len() > 2 { T[n as usize & 63] as char } else { '=' });
    }
    out
}

/// Supplied by the caller. The key never enters this crate.
pub trait Signer {
    fn address(&self) -> String;
    fn sign_transfer_with_authorization(
        &self,
        domain: &Domain,
        message: &Authorization,
    ) -> Result<String, Error>;
}

/// Supplied by the caller. This crate opens no socket, so a program that
/// already has an HTTP client does not gain a second one.
pub trait Transport {
    fn send(
        &self,
        method: &str,
        url: &str,
        headers: &[(String, String)],
        body: Option<&[u8]>,
    ) -> Result<(u16, Vec<u8>), Error>;
}

pub struct Client<'a> {
    pub policy: Policy,
    pub signer: &'a dyn Signer,
    pub transport: &'a dyn Transport,
}

impl Client<'_> {
    /// Ask what a resource costs, without paying. The safe first call.
    pub fn challenge(&self, url: &str) -> Result<Option<Challenge>, Error> {
        let (status, body) = self.transport.send(
            "GET",
            url,
            &[("User-Agent".into(), USER_AGENT.into())],
            None,
        )?;
        Ok(parse_challenge(status, &body))
    }

    /// Fetch a resource, paying if it asks.
    ///
    /// A non-402 response is returned untouched -- including errors, because a
    /// 500 is the server's answer and swallowing it to retry would hide it.
    pub fn fetch(
        &self,
        method: &str,
        url: &str,
        body: Option<&[u8]>,
        now: u64,
        nonce: &str,
    ) -> Result<(u16, Vec<u8>), Error> {
        let base = vec![("User-Agent".to_string(), USER_AGENT.to_string())];
        let (status, res) = self.transport.send(method, url, &base, body)?;
        let challenge = match parse_challenge(status, &res) {
            None => return Ok((status, res)),
            Some(c) => c,
        };
        let offer = select_offer(Some(&challenge), &self.policy).map_err(Error::Refused)?;
        if offer.scheme != "exact" {
            return Err(Error::UnsupportedScheme(offer.scheme.clone()));
        }
        let extra = offer.extra.as_ref().ok_or(Error::NoDomain)?;
        let (name, version) = match (extra.get("name"), extra.get("version")) {
            (Some(n), Some(v)) if !n.is_empty() && !v.is_empty() => (n.clone(), v.clone()),
            _ => return Err(Error::NoDomain),
        };
        let domain = Domain {
            name,
            version,
            chain_id: chain_id_for(&offer.network)?,
            verifying_contract: offer.asset.clone(),
        };
        let auth = build_authorization(offer, &self.signer.address(), now, nonce);
        let signature = self
            .signer
            .sign_transfer_with_authorization(&domain, &auth)?;
        let header = encode_payment_header(&serde_json::json!({
            "x402Version": challenge.x402_version,
            "scheme": "exact",
            "network": offer.network,
            "payload": {"signature": signature, "authorization": auth},
        }));
        let mut headers = base;
        headers.push(("X-PAYMENT".to_string(), header));
        self.transport.send(method, url, &headers, body)
    }
}
