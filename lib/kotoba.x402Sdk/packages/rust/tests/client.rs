use std::collections::HashMap;
use com_kotobalabs_x402::*;

fn policy() -> Policy {
    Policy {
        networks: vec!["base-sepolia".into()],
        assets: vec!["0x036CbD53842c5426634e7929541eC2318f3dCF7e".into()],
        max_amount: 5000,
        schemes: vec![],
    }
}

fn offer() -> Offer {
    let mut extra = HashMap::new();
    extra.insert("name".to_string(), "USDC".to_string());
    extra.insert("version".to_string(), "2".to_string());
    Offer {
        scheme: "exact".into(),
        network: "base-sepolia".into(),
        asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e".into(),
        pay_to: "0xA00366234D29d4F882088048c0B2fa0dB7302D4E".into(),
        max_amount_required: "1000".into(),
        max_timeout_seconds: Some(60),
        extra: Some(extra),
    }
}

fn chal(offers: Vec<Offer>) -> Challenge {
    Challenge { x402_version: 1, accepts: offers, error: None }
}

#[test]
fn no_policy_pays_nothing() {
    let empty = Policy { networks: vec![], assets: vec![], max_amount: 0, schemes: vec![] };
    let c = chal(vec![offer()]);
    assert_eq!(select_offer(Some(&c), &empty).unwrap_err().refused, "no-policy");
}

#[test]
fn cheapest_not_first() {
    let mut a = offer(); a.max_amount_required = "4000".into();
    let c = chal(vec![a, offer()]);
    assert_eq!(select_offer(Some(&c), &policy()).unwrap().max_amount_required, "1000");
}

#[test]
fn every_failing_check_is_named() {
    let mut o = offer();
    o.network = "base".into();
    o.asset = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".into();
    let c = chal(vec![o]);
    let r = select_offer(Some(&c), &policy()).unwrap_err();
    assert!(r.refused.contains("network-not-allowed"), "{}", r.refused);
    assert!(r.refused.contains("asset-not-allowed"), "{}", r.refused);
}

#[test]
fn unparseable_amount_is_not_silently_over_budget() {
    let mut o = offer(); o.max_amount_required = "one dollar".into();
    let c = chal(vec![o]);
    assert_eq!(select_offer(Some(&c), &policy()).unwrap_err().refused, "unparseable-amount");
}

#[test]
fn none_refuses_rather_than_panics() {
    assert_eq!(select_offer(None, &policy()).unwrap_err().refused, "not-a-challenge");
}

#[test]
fn unknown_network_errors_rather_than_defaulting() {
    assert!(chain_id_for("optimism").is_err());
    assert_eq!(chain_id_for("base-sepolia").unwrap(), 84532);
    assert_eq!(chain_id_for("eip155:8453").unwrap(), 8453);
}

#[test]
fn parse_challenge_only_accepts_a_challenge() {
    assert!(parse_challenge(500, b"boom").is_none());
    assert!(parse_challenge(402, b"nope").is_none());
    assert!(parse_challenge(402, br#"{"x402Version":1,"accepts":[]}"#).is_some());
}

#[test]
fn authorization_expires_by_the_offers_own_timeout() {
    let mut o = offer(); o.max_timeout_seconds = Some(30);
    let a = build_authorization(&o, "0xabc", 1000, "0xnonce");
    assert_eq!(a.valid_before, "1030");
    assert_eq!(a.valid_after, "0");
}

#[test]
fn base64_round_trips_through_the_header() {
    let v = serde_json::json!({"scheme":"exact","payload":{"signature":"0x01"}});
    let h = encode_payment_header(&v);
    // Decode with a table walk rather than a dependency, so the test does not
    // trust the same code it is checking.
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut bits = Vec::new();
    for ch in h.bytes().filter(|c| *c != b'=') {
        let i = T.iter().position(|t| *t == ch).expect("base64 alphabet") as u32;
        for k in (0..6).rev() { bits.push((i >> k) & 1); }
    }
    let bytes: Vec<u8> = bits.chunks(8).filter(|c| c.len() == 8)
        .map(|c| c.iter().fold(0u8, |a, b| (a << 1) | *b as u8)).collect();
    let back: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(back["payload"]["signature"], "0x01");
}

struct StubSigner;
impl Signer for StubSigner {
    fn address(&self) -> String { "0xdeadbeef".into() }
    fn sign_transfer_with_authorization(&self, _d: &Domain, _m: &Authorization) -> Result<String, Error> {
        Ok("0xsig".into())
    }
}

struct Once { body: Vec<u8>, status: u16 }
impl Transport for Once {
    fn send(&self, _m: &str, _u: &str, headers: &[(String, String)], _b: Option<&[u8]>)
        -> Result<(u16, Vec<u8>), Error> {
        assert!(headers.iter().any(|(k, v)| k == "User-Agent" && v.contains("x402-sdk-rust")),
                "a default agent gets 403 from some edges");
        Ok((self.status, self.body.clone()))
    }
}

#[test]
fn a_non_402_is_returned_untouched() {
    let t = Once { body: b"boom".to_vec(), status: 500 };
    let c = Client { policy: policy(), signer: &StubSigner, transport: &t };
    let (s, b) = c.fetch("GET", "https://x/y", None, 1000, "0xn").unwrap();
    assert_eq!((s, b), (500, b"boom".to_vec()));
}

#[test]
fn missing_domain_is_refused_not_guessed() {
    let mut o = offer(); o.extra = None;
    let body = serde_json::to_vec(&chal(vec![o])).unwrap();
    let t = Once { body, status: 402 };
    let c = Client { policy: policy(), signer: &StubSigner, transport: &t };
    match c.fetch("GET", "https://x/y", None, 1000, "0xn") {
        Err(Error::NoDomain) => {}
        other => panic!("want NoDomain, got {other:?}"),
    }
}
