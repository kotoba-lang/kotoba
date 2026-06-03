//! Integration test: Circuit Relay v2 reservation between a relay-server node
//! and a relay-client node — the NAT-traversal fallback path added in the
//! kotoba-net NAT-traversal work (AutoNAT + Circuit Relay v2 + DCUtR).
//!
//! Spins up two real libp2p swarms on ephemeral loopback QUIC ports. The relay
//! server runs the Circuit Relay v2 server (`NatConfig { relay_server: true }`);
//! the client takes a reservation via `reserve_relay_with_peer` and we assert it
//! is accepted — i.e. the client is now reachable at
//! `<relay-addr>/p2p-circuit/p2p/<client>`.
//!
//! SCOPE (honest R0→R1): this verifies the reservation handshake end-to-end over
//! a real network stack. It does NOT assert the full DCUtR hole-punch upgrade
//! (relayed → direct): on loopback both peers are already directly dialable, so
//! a hole-punch is a no-op. Cross-NAT DCUtR validation remains the R1 step (a
//! real two-host test on the public internet), per ADR-2606039000.

use kotoba_net::{KotobaNetEvent, KotobaSwarm, Multiaddr, NatConfig};
use std::time::Duration;
use tokio::time::timeout;

/// Collect a swarm's first `ListenAddr` event. Returns None on timeout.
async fn get_listen_addr(swarm: &mut KotobaSwarm) -> Option<Multiaddr> {
    timeout(Duration::from_secs(5), async {
        loop {
            if let KotobaNetEvent::ListenAddr(a) = swarm.next_event().await? {
                return Some(a);
            }
        }
    })
    .await
    .ok()
    .flatten()
}

/// A relay-client takes a Circuit Relay v2 reservation on a relay-server node.
///
/// Both swarms are driven concurrently with `tokio::select!` so the reservation
/// request/accept handshake can flow over the established QUIC connection.
#[tokio::test]
async fn relay_client_obtains_reservation_from_relay_server() {
    // Relay server — a designated public helper node (relay_server on).
    let relay_addr: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
    let mut relay = KotobaSwarm::new_with_config(relay_addr, NatConfig { relay_server: true })
        .await
        .expect("relay server init");
    let relay_peer = relay.local_peer_id; // Copy out before the select borrows `relay`.

    // Client — would be behind NAT in production; relay_client is always on.
    let client_addr: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
    let mut client = KotobaSwarm::new(client_addr).await.expect("client init");

    let relay_listen = get_listen_addr(&mut relay)
        .await
        .expect("relay did not emit a ListenAddr within timeout");

    // A relay server must advertise a reachable external address, otherwise its
    // reservation responses carry no addresses and the client rejects them with
    // `NoAddressesInReservation`. In production this comes from AutoNAT (or an
    // operator-set address); on loopback we set it explicitly. This also
    // exercises the `add_external_address` API.
    relay.add_external_address(relay_listen.clone());

    // Edge node reserves a Circuit Relay v2 slot on the relay (dials it, requests
    // a reservation). `reserve_relay_with_peer` appends `/p2p/<relay>` + circuit.
    client
        .reserve_relay_with_peer(relay_peer, relay_listen)
        .expect("reserve_relay_with_peer accepted the circuit listen addr");

    // Drive both concurrently until the client's reservation is accepted.
    let accepted = timeout(Duration::from_secs(15), async {
        loop {
            tokio::select! {
                ev = relay.next_event() => {
                    if ev.is_none() {
                        return false; // relay terminated
                    }
                    // Keep the relay alive to answer the reservation request.
                }
                ev = client.next_event() => {
                    match ev {
                        None => return false,
                        Some(KotobaNetEvent::RelayReservationAccepted { relay: r }) => {
                            assert_eq!(r, relay_peer, "reservation from the expected relay");
                            return true;
                        }
                        _ => {}
                    }
                }
            }
        }
    })
    .await;

    assert!(
        matches!(accepted, Ok(true)),
        "client did not obtain a Circuit Relay v2 reservation within 15 s \
         (check libp2p relay client/server wiring)"
    );
}
