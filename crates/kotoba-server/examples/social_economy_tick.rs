//! `social_economy_tick` — one cycle of the Mishmar social-capital loop, wired to
//! live infrastructure (ADR-2606082100). Designed to run on a **Murakumo Mac mini
//! fleet node** (which can reach the geth-private tunnel + the KaizenObserver feed),
//! driven on a cadence by launchd (`deploy/social-economy/`).
//!
//! Run: `cargo run --example social_economy_tick -p kotoba-server`
//!
//! Env (live mode — all required, else it runs a built-in FAKE demo so the binary
//! is always exercisable):
//!   KOTOBA_EVM_RPC_URL          geth-private / Base L2 JSON-RPC (e.g. https://geth.etzhayyim.com)
//!   KOTOBA_MISHMAR_ESCROW_ADDR  deployed MishmarBondEscrow address (0x…)
//!   KOTOBA_SOCIAL_GRAPH_CID     social graph CID (multibase)
//!   KOTOBA_KAIZEN_FEED_URL      KaizenObserver wellbecoming-Δ feed (provisional schema)
//!   KOTOBA_RETAINER_POOL_MKOTO  this epoch's donation-funded retainer pool (default 1_000_000)
//!   KOTOBA_OPERATOR_DID         operator DID for the Econ wallet (default did:web:etzhayyim.com)
//!   KOTOBA_EVM_FROM_BLOCK/TO_BLOCK  log range (default 0x0 / latest)

use std::time::{SystemTime, UNIX_EPOCH};

use kotoba_core::cid::KotobaCid;
use kotoba_query::social::MintParams;
use kotoba_server::econ::Econ;
use kotoba_server::social_economy::{fetch_kaizen_feed, live_evm_source, SocialEconomyDriver};

fn env(k: &str) -> Option<String> {
    std::env::var(k).ok().filter(|s| !s.is_empty())
}

#[tokio::main]
async fn main() {
    let pool: i64 = env("KOTOBA_RETAINER_POOL_MKOTO")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1_000_000);
    let epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() / 86_400)
        .unwrap_or(0);
    let operator = env("KOTOBA_OPERATOR_DID").unwrap_or_else(|| "did:web:etzhayyim.com".into());
    let from_block = env("KOTOBA_EVM_FROM_BLOCK").unwrap_or_else(|| "0x0".into());
    let to_block = env("KOTOBA_EVM_TO_BLOCK").unwrap_or_else(|| "latest".into());

    let graph = env("KOTOBA_SOCIAL_GRAPH_CID")
        .and_then(|s| KotobaCid::from_multibase(&s))
        .unwrap_or_else(|| KotobaCid::from_bytes(b"g:social:default"));

    println!("== social_economy_tick (epoch {epoch}, pool {pool} mKOTO) ==");

    let live = live_evm_source(graph.clone());
    let kaizen = fetch_kaizen_feed();

    match (live, kaizen) {
        (Some(evm), kaizen_feed) => {
            // LIVE: observe chain + Kaizen, mint, settle, credit wallet.
            let feed = kaizen_feed.unwrap_or_else(|| serde_json::json!([]));
            let mut driver = SocialEconomyDriver::new(MintParams::default(), graph);
            match driver.tick(&evm, &feed, &from_block, &to_block, epoch, pool) {
                Ok((minted, result)) => {
                    println!("LIVE: minted {} social Datoms; {} pinner credits; total {} mKOTO (remainder {})",
                        minted.len(), result.credits.len(), result.total_mkoto, result.remainder_mkoto);
                    let econ = Econ::from_env(operator);
                    let credited = SocialEconomyDriver::settle_to_wallet(&econ, &result).await;
                    println!("LIVE: credited {credited} mKOTO to the persisted wallet.");
                    // NOTE: `minted` must be transacted to the canonical Datom log
                    // (datomic.transact) so the view survives restart.
                    println!(
                        "NOTE: transact {} minted Datoms to the log (datomic.transact).",
                        minted.len()
                    );
                }
                Err(e) => {
                    eprintln!("LIVE tick failed (is geth-private / the escrow reachable?): {e}");
                    std::process::exit(1);
                }
            }
        }
        _ => {
            // FAKE demo (no live env) — proves the binary runs; mirrors the unit test.
            println!("(no KOTOBA_EVM_RPC_URL / escrow set — running FAKE demo)");
            run_fake_demo(graph, epoch, pool).await;
        }
    }
}

async fn run_fake_demo(graph: KotobaCid, epoch: u64, pool: i64) {
    use kotoba_query::datom::{Datom, Value};
    use kotoba_query::social::{MintSource, ObservedDisclosure, SCALE};

    let did = |s: &str| KotobaCid::from_bytes(s.as_bytes());
    let cid_datom = |e: &KotobaCid, a: &str, v: &KotobaCid| {
        Datom::assert(e.clone(), a.to_string(), Value::Cid(v.clone()), did("g"))
    };
    let a = did("did:key:a");
    let peggy = did("did:key:peggy");

    let mut driver = SocialEconomyDriver::new(MintParams::default(), graph);
    driver.ingest_pins(&[
        cid_datom(&did("pinA"), "mishmar/pin/pinner", &peggy),
        cid_datom(&did("pinA"), "mishmar/pin/root", &did("rootA")),
    ]);
    driver.ingest_origins(&[cid_datom(&did("rootA"), "social/origin", &a)]);
    driver.mint(
        &[ObservedDisclosure {
            did: a.clone(),
            epoch,
            n_validated: 10,
            citation_hits: 0,
            terminal_honest: true,
            witness_quorum_met: true,
        }],
        &[],
        &[],
    );
    let _ = MintSource::Disclosure;
    let result = driver.settle(epoch, pool);
    println!(
        "FAKE: a's capital = {} pts; pinA → peggy gets {} mKOTO (remainder {})",
        driver.view.capital(&a, epoch) / SCALE,
        result.total_mkoto,
        result.remainder_mkoto
    );
    let econ = Econ::from_env("did:key:demo-operator".to_string());
    let credited = SocialEconomyDriver::settle_to_wallet(&econ, &result).await;
    println!(
        "FAKE: credited {credited} mKOTO to peggy; balance now {}.",
        econ.balance(&peggy.to_string()).await
    );
    println!("== fake demo ok — set the KOTOBA_EVM_* env to run live on a fleet node ==");
}
