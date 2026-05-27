/// Two-node Bitswap exchange: node A stores a block, node B fetches it.
use kotoba_ipfs::IpfsConfig;
use tokio::time::{timeout, Duration};

#[tokio::test]
async fn two_node_bitswap_exchange() {
    tracing_subscriber::fmt()
        .with_env_filter("kotoba_ipfs=debug,co_libp2p_bitswap=debug")
        .try_init()
        .ok();

    // Start two nodes on random ports.
    let node_a = IpfsConfig::new().start().await.expect("node A start");
    let node_b = IpfsConfig::new().start().await.expect("node B start");

    // Give the nodes a moment to open their listeners.
    tokio::time::sleep(Duration::from_millis(100)).await;

    // Node A stores a block.
    let data = b"hello kotoba-ipfs bitswap".to_vec();
    let cid = node_a.put_block(data.clone()).await.expect("put_block");
    eprintln!("stored CID: {cid}");

    // We need node B to know node A's listen address.
    // Obtain it via the connected_peers trick: dial and wait, or use
    // a known loopback address. Since the port is random we build the addr
    // from the swarm's perspective by adding a known peer.
    //
    // Strategy: add node A's peer_id + dial addr manually.
    // We discover the listen address by querying node A's event log.
    // Instead, we just use a hack: start node A on a known port for this test.

    // Restart node A on a fixed port so B can dial it.
    drop(node_a);
    let node_a = IpfsConfig {
        listen: "/ip4/127.0.0.1/tcp/17001".parse().unwrap(),
    }
    .start()
    .await
    .expect("node A restart");

    tokio::time::sleep(Duration::from_millis(100)).await;

    let cid = node_a.put_block(data.clone()).await.expect("put_block");
    let peer_a = node_a.peer_id();
    eprintln!("node A peer_id: {peer_a}, CID: {cid}");

    // B dials A.
    node_b
        .dial(format!("/ip4/127.0.0.1/tcp/17001/p2p/{peer_a}").parse().unwrap())
        .expect("dial");

    // Give connection a moment to establish.
    tokio::time::sleep(Duration::from_millis(300)).await;

    let peers = node_b.connected_peers().await.expect("peers");
    eprintln!("B connected peers: {peers:?}");
    assert!(peers.contains(&peer_a), "B should be connected to A");

    // B fetches the block from A.
    let fetched = timeout(
        Duration::from_secs(5),
        node_b.get_block(cid, vec![peer_a]),
    )
    .await
    .expect("timeout")
    .expect("get_block");

    assert_eq!(fetched, data);
    eprintln!("two-node Bitswap exchange: OK");
}
