//! `evm_node` — a runnable kotoba-EVM L2 node (ADR-2606091500). Seeds genesis +
//! serves the geth/viem-compatible `eth_*` JSON-RPC, so you can point Solidity
//! tooling straight at it:
//!
//!   cargo run --example evm_node -p kotoba-server
//!   forge create … --rpc-url http://127.0.0.1:8545 --private-key 0xac0974…ff80
//!   cast balance 0xf39Fd6…2266 --rpc-url http://127.0.0.1:8545
//!
//! Env:
//!   KOTOBA_EVM_PORT          listen port (default 8545)
//!   KOTOBA_EVM_GENESIS_ADDR  account to fund at genesis (default = Anvil dev acct #0)
//!   KOTOBA_EVM_GENESIS_ETH   its balance in whole ETH (default 10000)

use std::sync::Arc;

use kotoba_core::cid::KotobaCid;
use kotoba_server::evm_rpc::{router, EvmNode};
use tokio::sync::RwLock;

fn parse_addr20(s: &str) -> [u8; 20] {
    let b = hex::decode(s.strip_prefix("0x").unwrap_or(s)).expect("hex addr");
    let mut a = [0u8; 20];
    a.copy_from_slice(&b);
    a
}

fn eth_to_wei_be(eth: u128) -> [u8; 32] {
    let wei = eth.saturating_mul(1_000_000_000_000_000_000u128); // 1e18
    let mut a = [0u8; 32];
    a[16..32].copy_from_slice(&wei.to_be_bytes());
    a
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("KOTOBA_EVM_PORT").ok().and_then(|s| s.parse().ok()).unwrap_or(8545);
    // default funded account = the standard Anvil/Hardhat dev account #0
    // (pk 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80).
    let genesis_addr = std::env::var("KOTOBA_EVM_GENESIS_ADDR")
        .unwrap_or_else(|_| "f39Fd6e51aad88F6F4ce6aB8827279cffFb92266".into());
    let genesis_eth: u128 =
        std::env::var("KOTOBA_EVM_GENESIS_ETH").ok().and_then(|s| s.parse().ok()).unwrap_or(10_000);

    let mut node = EvmNode::default_node();
    let addr = parse_addr20(&genesis_addr);
    node.genesis(&[(addr, eth_to_wei_be(genesis_eth), 0)]);

    let app = router(Arc::new(RwLock::new(node)));
    let bind = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&bind).await.expect("bind");

    println!("== kotoba-EVM node ==");
    println!("  RPC:     http://127.0.0.1:{port}  (chainId 0x6b6f74 = kotoba-EVM)");
    println!("  funded:  0x{genesis_addr}  ({genesis_eth} ETH)");
    println!("  forge:   forge create … --rpc-url http://127.0.0.1:{port} --private-key <key>");
    println!("  (Charter §2(b): gasPrice is 0 — no gas market)");

    let _ = KotobaCid::from_bytes(b"evm-node"); // (graph cid is internal to the node)
    axum::serve(listener, app).await.expect("serve");
}
