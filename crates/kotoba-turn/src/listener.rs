//! Async UDP listener — the socket layer over the socket-free core.
//!
//! This is the layer `lib.rs`/`docs/ADR-turn-relay.md` called "the only remaining
//! one". It wires the pure pieces onto real tokio UDP sockets:
//!
//!   * one CLIENT-facing socket receives STUN requests + Send/ChannelData from the
//!     client (`server::classify_datagram` routes each datagram);
//!   * each `Allocate` binds a RELAY socket from a port pool; a per-allocation task
//!     forwards peer→client traffic (as a Data indication, or a ChannelData frame
//!     once the client has bound a channel for that peer);
//!   * client→peer travels via a Send indication or a ChannelData frame, sent out
//!     the relay socket after a permission check.
//!
//! Auth, the STUN codec, the allocation state machine, and ChannelData framing all
//! come from the pure modules — this file only adds sockets, a relay-port pool, and
//! packet forwarding. Gated behind the `listener` feature so the core stays
//! async-free. IPv4 only (the XOR-address codecs are v4); other families are dropped.

use crate::allocation::{AllocationTable, FiveTuple, TransportProto};
use crate::{channel, server, stun};
use std::collections::HashMap;
use std::net::{SocketAddr, SocketAddrV4};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::net::UdpSocket;
use tokio::sync::Mutex;

fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// The error-response message type for a given request type (RFC 8489 class bits:
/// error class = 0b11). Allocate 0x0003→0x0113, Refresh 0x0004→0x0114, etc.
fn err_type(request_type: u16) -> u16 {
    0x0110 | (request_type & 0x000F)
}

/// Relay listener configuration.
#[derive(Clone, Debug)]
pub struct TurnConfig {
    /// The ephemeral-credential shared secret (coturn use-auth-secret). Verifies the
    /// MESSAGE-INTEGRITY on every authed request; must never reach a browser.
    pub secret: String,
    /// The IPv4 address relay (XOR-RELAYED-ADDRESS) sockets bind + advertise on.
    pub relay_ip: std::net::Ipv4Addr,
    /// Inclusive relay-port range. `(0, 0)` means "ephemeral" (bind `relay_ip:0`).
    pub relay_ports: (u16, u16),
}

struct Inner {
    table: AllocationTable,
    relays: HashMap<FiveTuple, Arc<UdpSocket>>,
    /// next port to try in the pool (round-robins the configured range).
    next_port: u16,
}

/// A running UDP TURN relay.
pub struct Server {
    sock: Arc<UdpSocket>,
    state: Arc<Mutex<Inner>>,
    cfg: TurnConfig,
}

impl Server {
    /// Bind the client-facing UDP socket and construct the relay (not yet running).
    pub async fn bind(bind_addr: SocketAddr, cfg: TurnConfig) -> std::io::Result<Arc<Self>> {
        let sock = Arc::new(UdpSocket::bind(bind_addr).await?);
        let next_port = cfg.relay_ports.0;
        Ok(Arc::new(Self {
            sock,
            state: Arc::new(Mutex::new(Inner {
                table: AllocationTable::new(),
                relays: HashMap::new(),
                next_port,
            })),
            cfg,
        }))
    }

    /// The client-facing local address (useful when bound to `:0` in tests).
    pub fn local_addr(&self) -> std::io::Result<SocketAddr> {
        self.sock.local_addr()
    }

    /// Run the recv loop forever (drives requests + client→peer forwarding).
    pub async fn run(self: Arc<Self>) -> std::io::Result<()> {
        let mut buf = vec![0u8; 65_536];
        loop {
            let (n, src) = self.sock.recv_from(&mut buf).await?;
            let SocketAddr::V4(_) = src else { continue };
            let server_addr = self.sock.local_addr()?;
            let tuple = FiveTuple {
                client: src,
                server: server_addr,
                proto: TransportProto::Udp,
            };
            let datagram = &buf[..n];
            match server::classify_datagram(datagram) {
                server::Datagram::Stun => {
                    if let Some(resp) = self.clone().handle_stun(datagram, src, tuple).await {
                        let _ = self.sock.send_to(&resp, src).await;
                    }
                }
                server::Datagram::ChannelData => {
                    self.forward_channel_data(datagram, &tuple).await;
                }
                server::Datagram::Unknown => {}
            }
        }
    }

    // ── request handling ─────────────────────────────────────────────────────

    async fn handle_stun(
        self: Arc<Self>,
        msg: &[u8],
        src: SocketAddr,
        tuple: FiveTuple,
    ) -> Option<Vec<u8>> {
        let hdr = stun::Header::decode(msg).ok()?;
        let SocketAddr::V4(src_v4) = src else {
            return None;
        };

        // Send indication is a client→peer data path, not a request — no response.
        if hdr.typ == stun::SEND_INDICATION {
            self.forward_send_indication(msg, &tuple).await;
            return None;
        }

        match server::method_of(hdr.typ) {
            server::TurnMethod::Binding => Some(binding_response(hdr.txid, src_v4)),
            server::TurnMethod::Allocate => self.handle_allocate(&hdr, msg, src_v4, tuple).await,
            server::TurnMethod::Refresh => self.handle_refresh(&hdr, msg, tuple).await,
            server::TurnMethod::CreatePermission => {
                self.handle_create_permission(&hdr, msg, tuple).await
            }
            server::TurnMethod::ChannelBind => self.handle_channel_bind(&hdr, msg, tuple).await,
            server::TurnMethod::Other => None,
        }
    }

    async fn handle_allocate(
        self: Arc<Self>,
        hdr: &stun::Header,
        msg: &[u8],
        src_v4: SocketAddrV4,
        tuple: FiveTuple,
    ) -> Option<Vec<u8>> {
        let t = now();
        let scope = match server::authenticate(msg, &self.cfg.secret, t) {
            Ok(s) => s,
            Err(reject) => {
                return Some(error_response(
                    err_type(hdr.typ),
                    hdr.txid,
                    reject.error_code(),
                ))
            }
        };
        let username = find_attr_str(msg, stun::ATTR_USERNAME)?;
        let key = crate::hmac_sha1_base64(&self.cfg.secret, username);

        // Idempotent retransmit: an Allocate on a live 5-tuple echoes the existing
        // relay instead of erroring (clients retransmit on packet loss).
        if let Some(SocketAddr::V4(relay)) = self.state.lock().await.table.relay_addr(&tuple, t) {
            return Some(allocate_response(
                hdr.txid,
                relay,
                src_v4,
                crate::allocation::DEFAULT_LIFETIME,
                key.as_bytes(),
            ));
        }

        let requested = find_attr_u32(msg, stun::ATTR_LIFETIME).unwrap_or(0) as u64;
        let relay_sock = match self.alloc_relay_socket().await {
            Some(s) => s,
            None => return Some(error_response(err_type(hdr.typ), hdr.txid, 508)), // Insufficient Capacity
        };
        let SocketAddr::V4(relay_v4) = relay_sock.local_addr().ok()? else {
            return None;
        };

        let expires_at = {
            let mut st = self.state.lock().await;
            match st
                .table
                .allocate(tuple, SocketAddr::V4(relay_v4), scope, requested, t)
            {
                Ok(exp) => {
                    st.relays.insert(tuple, relay_sock.clone());
                    exp
                }
                Err(_) => return Some(error_response(err_type(hdr.typ), hdr.txid, 437)),
            }
        };
        self.clone().spawn_relay(tuple, relay_sock);

        Some(allocate_response(
            hdr.txid,
            relay_v4,
            src_v4,
            expires_at.saturating_sub(t),
            key.as_bytes(),
        ))
    }

    async fn handle_refresh(
        self: Arc<Self>,
        hdr: &stun::Header,
        msg: &[u8],
        tuple: FiveTuple,
    ) -> Option<Vec<u8>> {
        let t = now();
        if let Err(reject) = server::authenticate(msg, &self.cfg.secret, t) {
            return Some(error_response(
                err_type(hdr.typ),
                hdr.txid,
                reject.error_code(),
            ));
        }
        let key =
            crate::hmac_sha1_base64(&self.cfg.secret, find_attr_str(msg, stun::ATTR_USERNAME)?);
        let requested = find_attr_u32(msg, stun::ATTR_LIFETIME)
            .unwrap_or(crate::allocation::DEFAULT_LIFETIME as u32) as u64;
        let granted = {
            let mut st = self.state.lock().await;
            match st.table.refresh(&tuple, requested, t) {
                Ok(exp) => {
                    if requested == 0 {
                        st.relays.remove(&tuple);
                        0
                    } else {
                        exp.saturating_sub(t)
                    }
                }
                Err(_) => return Some(error_response(err_type(hdr.typ), hdr.txid, 437)),
            }
        };
        let mut r = header(stun::REFRESH_RESPONSE, hdr.txid);
        stun::push_attr(
            &mut r,
            stun::ATTR_LIFETIME,
            &stun::encode_u32(granted as u32),
        );
        seal(&mut r, key.as_bytes());
        Some(r)
    }

    async fn handle_create_permission(
        self: Arc<Self>,
        hdr: &stun::Header,
        msg: &[u8],
        tuple: FiveTuple,
    ) -> Option<Vec<u8>> {
        let t = now();
        if let Err(reject) = server::authenticate(msg, &self.cfg.secret, t) {
            return Some(error_response(
                err_type(hdr.typ),
                hdr.txid,
                reject.error_code(),
            ));
        }
        let key =
            crate::hmac_sha1_base64(&self.cfg.secret, find_attr_str(msg, stun::ATTR_USERNAME)?);
        let peer = find_attr_peer(msg)?;
        {
            let mut st = self.state.lock().await;
            if st
                .table
                .create_permission(&tuple, (*peer.ip()).into(), t)
                .is_err()
            {
                return Some(error_response(err_type(hdr.typ), hdr.txid, 437));
            }
        }
        let mut r = header(stun::CREATE_PERMISSION_RESPONSE, hdr.txid);
        seal(&mut r, key.as_bytes());
        Some(r)
    }

    async fn handle_channel_bind(
        self: Arc<Self>,
        hdr: &stun::Header,
        msg: &[u8],
        tuple: FiveTuple,
    ) -> Option<Vec<u8>> {
        let t = now();
        if let Err(reject) = server::authenticate(msg, &self.cfg.secret, t) {
            return Some(error_response(
                err_type(hdr.typ),
                hdr.txid,
                reject.error_code(),
            ));
        }
        let key =
            crate::hmac_sha1_base64(&self.cfg.secret, find_attr_str(msg, stun::ATTR_USERNAME)?);
        let channel = find_attr_u16(msg, stun::ATTR_CHANNEL_NUMBER)?;
        let peer = find_attr_peer(msg)?;
        {
            let mut st = self.state.lock().await;
            match st
                .table
                .bind_channel(&tuple, channel, SocketAddr::V4(peer), t)
            {
                Ok(()) => {}
                Err(crate::allocation::AllocError::BadChannel) => {
                    return Some(error_response(err_type(hdr.typ), hdr.txid, 400))
                }
                Err(_) => return Some(error_response(err_type(hdr.typ), hdr.txid, 437)),
            }
        }
        let mut r = header(stun::CHANNEL_BIND_RESPONSE, hdr.txid);
        seal(&mut r, key.as_bytes());
        Some(r)
    }

    // ── data forwarding ──────────────────────────────────────────────────────

    /// Client→peer via a ChannelData frame: resolve the channel's bound peer and
    /// send the payload out the allocation's relay socket (permission-checked).
    async fn forward_channel_data(&self, datagram: &[u8], tuple: &FiveTuple) {
        let t = now();
        let cd = match channel::decode(datagram) {
            Ok(c) => c,
            Err(_) => return,
        };
        let (peer, relay) = {
            let st = self.state.lock().await;
            (
                st.table.channel_peer(tuple, cd.channel, t),
                st.relays.get(tuple).cloned(),
            )
        };
        if let (Some(peer), Some(relay)) = (peer, relay) {
            if self.state.lock().await.table.permitted(tuple, peer.ip(), t) {
                let _ = relay.send_to(cd.data, peer).await;
            }
        }
    }

    /// Client→peer via a STUN Send indication (XOR-PEER-ADDRESS + DATA).
    async fn forward_send_indication(&self, msg: &[u8], tuple: &FiveTuple) {
        let t = now();
        let Some(peer) = find_attr_peer(msg) else {
            return;
        };
        let Some(data) = find_attr(msg, stun::ATTR_DATA) else {
            return;
        };
        let relay = self.state.lock().await.relays.get(tuple).cloned();
        if let Some(relay) = relay {
            if self
                .state
                .lock()
                .await
                .table
                .permitted(tuple, (*peer.ip()).into(), t)
            {
                let _ = relay.send_to(data, SocketAddr::V4(peer)).await;
            }
        }
    }

    /// Spawn the per-allocation peer→client forwarder. Lives until the allocation
    /// expires/refreshes-to-zero (checked each packet), then the task exits.
    fn spawn_relay(self: Arc<Self>, tuple: FiveTuple, relay: Arc<UdpSocket>) {
        let main = self.sock.clone();
        let state = self.state.clone();
        tokio::spawn(async move {
            let mut buf = vec![0u8; 65_536];
            loop {
                let (n, peer) = match relay.recv_from(&mut buf).await {
                    Ok(v) => v,
                    Err(_) => break,
                };
                let SocketAddr::V4(peer_v4) = peer else {
                    continue;
                };
                let t = now();
                let (alive, permitted, chan) = {
                    let st = state.lock().await;
                    (
                        st.table.relay_addr(&tuple, t).is_some(),
                        st.table.permitted(&tuple, peer.ip(), t),
                        st.table.channel_for_peer(&tuple, peer, t),
                    )
                };
                if !alive {
                    break; // allocation gone → stop forwarding
                }
                if !permitted {
                    continue; // peer has no permission → drop
                }
                let payload = &buf[..n];
                let frame = match chan {
                    // a channel is bound for this peer → the compact ChannelData path
                    Some(c) => match channel::encode(c, payload, false) {
                        Ok(f) => f,
                        Err(_) => continue,
                    },
                    // otherwise a Data indication (XOR-PEER-ADDRESS + DATA)
                    None => data_indication(peer_v4, payload),
                };
                let _ = main.send_to(&frame, tuple.client).await;
            }
        });
    }

    /// Bind a relay socket from the configured port pool (or ephemeral for `(0,0)`).
    async fn alloc_relay_socket(&self) -> Option<Arc<UdpSocket>> {
        let (lo, hi) = self.cfg.relay_ports;
        if lo == 0 && hi == 0 {
            let addr = SocketAddr::V4(SocketAddrV4::new(self.cfg.relay_ip, 0));
            return UdpSocket::bind(addr).await.ok().map(Arc::new);
        }
        let span = (hi - lo + 1) as u32;
        let start = self.state.lock().await.next_port;
        for i in 0..span {
            let port = (lo as u32 + ((start as u32 - lo as u32 + i) % span)) as u16;
            let addr = SocketAddr::V4(SocketAddrV4::new(self.cfg.relay_ip, port));
            if let Ok(s) = UdpSocket::bind(addr).await {
                let mut st = self.state.lock().await;
                st.next_port = if port >= hi { lo } else { port + 1 };
                return Some(Arc::new(s));
            }
        }
        None
    }
}

// ── response builders (pure) ─────────────────────────────────────────────────

fn header(typ: u16, txid: [u8; 12]) -> Vec<u8> {
    stun::Header {
        typ,
        length: 0,
        txid,
    }
    .encode()
    .to_vec()
}

/// Finalize an authed response: patch length, append MESSAGE-INTEGRITY (keyed by
/// the client's credential) then FINGERPRINT.
fn seal(buf: &mut Vec<u8>, key: &[u8]) {
    stun::append_message_integrity(buf, key);
    stun::append_fingerprint(buf);
}

fn binding_response(txid: [u8; 12], src: SocketAddrV4) -> Vec<u8> {
    let mut r = header(stun::BINDING_RESPONSE, txid);
    stun::push_attr(
        &mut r,
        stun::ATTR_XOR_MAPPED_ADDRESS,
        &stun::encode_xor_mapped_v4(*src.ip(), src.port()),
    );
    stun::set_attr_length(&mut r);
    stun::append_fingerprint(&mut r);
    r
}

fn allocate_response(
    txid: [u8; 12],
    relay: SocketAddrV4,
    mapped: SocketAddrV4,
    lifetime: u64,
    key: &[u8],
) -> Vec<u8> {
    let mut r = header(stun::ALLOCATE_RESPONSE, txid);
    stun::push_attr(
        &mut r,
        stun::ATTR_XOR_RELAYED_ADDRESS,
        &stun::encode_xor_mapped_v4(*relay.ip(), relay.port()),
    );
    stun::push_attr(
        &mut r,
        stun::ATTR_LIFETIME,
        &stun::encode_u32(lifetime as u32),
    );
    stun::push_attr(
        &mut r,
        stun::ATTR_XOR_MAPPED_ADDRESS,
        &stun::encode_xor_mapped_v4(*mapped.ip(), mapped.port()),
    );
    seal(&mut r, key);
    r
}

fn error_response(typ: u16, txid: [u8; 12], code: u16) -> Vec<u8> {
    let mut r = header(typ, txid);
    stun::push_attr(
        &mut r,
        stun::ATTR_ERROR_CODE,
        &stun::encode_error_code(code, ""),
    );
    stun::set_attr_length(&mut r);
    stun::append_fingerprint(&mut r);
    r
}

fn data_indication(peer: SocketAddrV4, payload: &[u8]) -> Vec<u8> {
    let mut r = header(stun::DATA_INDICATION, [0u8; 12]);
    stun::push_attr(
        &mut r,
        stun::ATTR_XOR_PEER_ADDRESS,
        &stun::encode_xor_mapped_v4(*peer.ip(), peer.port()),
    );
    stun::push_attr(&mut r, stun::ATTR_DATA, payload);
    stun::set_attr_length(&mut r);
    r
}

// ── request attribute readers (pure) ─────────────────────────────────────────

fn find_attr(msg: &[u8], typ: u16) -> Option<&[u8]> {
    if msg.len() < 20 {
        return None;
    }
    stun::attributes(&msg[20..])
        .ok()?
        .into_iter()
        .find(|(t, _)| *t == typ)
        .map(|(_, v)| v)
}

fn find_attr_str(msg: &[u8], typ: u16) -> Option<&str> {
    std::str::from_utf8(find_attr(msg, typ)?).ok()
}

fn find_attr_u32(msg: &[u8], typ: u16) -> Option<u32> {
    let v = find_attr(msg, typ)?;
    (v.len() >= 4).then(|| u32::from_be_bytes([v[0], v[1], v[2], v[3]]))
}

fn find_attr_u16(msg: &[u8], typ: u16) -> Option<u16> {
    let v = find_attr(msg, typ)?;
    (v.len() >= 2).then(|| u16::from_be_bytes([v[0], v[1]]))
}

fn find_attr_peer(msg: &[u8]) -> Option<SocketAddrV4> {
    let v = find_attr(msg, stun::ATTR_XOR_PEER_ADDRESS)?;
    let (ip, port) = stun::decode_xor_mapped_v4(v).ok()?;
    Some(SocketAddrV4::new(ip, port))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{mint, Credential};
    use std::net::Ipv4Addr;
    use std::time::Duration;

    const SECRET: &str = "s3cret";

    fn cred() -> Credential {
        // far-future expiry so the relay's `now()` always accepts it
        mint(SECRET, "room-1", 7, 4_102_444_800) // 2100-01-01
    }

    /// Build an authed STUN request: USERNAME + extra attrs + MESSAGE-INTEGRITY.
    fn authed(typ: u16, c: &Credential, extra: &[(u16, Vec<u8>)]) -> Vec<u8> {
        let mut m = header(typ, [7u8; 12]);
        stun::push_attr(&mut m, stun::ATTR_USERNAME, c.username.as_bytes());
        for (t, v) in extra {
            stun::push_attr(&mut m, *t, v);
        }
        stun::append_message_integrity(&mut m, c.credential.as_bytes());
        m
    }

    fn xor_peer(addr: SocketAddrV4) -> Vec<u8> {
        stun::encode_xor_mapped_v4(*addr.ip(), addr.port()).to_vec()
    }

    async fn recv(sock: &UdpSocket) -> Vec<u8> {
        let mut buf = vec![0u8; 65_536];
        let (n, _) = tokio::time::timeout(Duration::from_secs(2), sock.recv_from(&mut buf))
            .await
            .expect("recv timed out")
            .unwrap();
        buf.truncate(n);
        buf
    }

    fn relayed_addr(resp: &[u8]) -> SocketAddrV4 {
        let v = find_attr(resp, stun::ATTR_XOR_RELAYED_ADDRESS).expect("relayed addr");
        let (ip, port) = stun::decode_xor_mapped_v4(v).unwrap();
        SocketAddrV4::new(ip, port)
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn full_relay_roundtrip_over_loopback() {
        // start the relay on an ephemeral client-facing port, ephemeral relay ports
        let srv = Server::bind(
            "127.0.0.1:0".parse().unwrap(),
            TurnConfig {
                secret: SECRET.into(),
                relay_ip: Ipv4Addr::LOCALHOST,
                relay_ports: (0, 0),
            },
        )
        .await
        .unwrap();
        let srv_addr = srv.local_addr().unwrap();
        tokio::spawn(srv.clone().run());

        let c = cred();
        let client = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        client.connect(srv_addr).await.unwrap();

        // 1) Allocate → expect a relayed address.
        client
            .send(&authed(
                stun::ALLOCATE_REQUEST,
                &c,
                &[(stun::ATTR_REQUESTED_TRANSPORT, vec![17, 0, 0, 0])],
            ))
            .await
            .unwrap();
        let resp = recv(&client).await;
        assert_eq!(
            stun::Header::decode(&resp).unwrap().typ,
            stun::ALLOCATE_RESPONSE,
            "Allocate should succeed"
        );
        let relay_addr = relayed_addr(&resp);

        // a peer that will talk to the relayed address
        let peer = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let peer_addr = match peer.local_addr().unwrap() {
            SocketAddr::V4(a) => a,
            _ => unreachable!(),
        };

        // 2) CreatePermission for the peer's IP.
        client
            .send(&authed(
                stun::CREATE_PERMISSION_REQUEST,
                &c,
                &[(stun::ATTR_XOR_PEER_ADDRESS, xor_peer(peer_addr))],
            ))
            .await
            .unwrap();
        assert_eq!(
            stun::Header::decode(&recv(&client).await).unwrap().typ,
            stun::CREATE_PERMISSION_RESPONSE
        );

        // 3) peer → relay → client arrives as a Data indication.
        peer.send_to(b"ping", relay_addr).await.unwrap();
        let ind = recv(&client).await;
        assert_eq!(
            stun::Header::decode(&ind).unwrap().typ,
            stun::DATA_INDICATION
        );
        assert_eq!(find_attr(&ind, stun::ATTR_DATA).unwrap(), b"ping");

        // 4) ChannelBind, then client → peer via a ChannelData frame.
        let chan: u16 = 0x4001;
        client
            .send(&authed(
                stun::CHANNEL_BIND_REQUEST,
                &c,
                &[
                    (
                        stun::ATTR_CHANNEL_NUMBER,
                        vec![(chan >> 8) as u8, chan as u8, 0, 0],
                    ),
                    (stun::ATTR_XOR_PEER_ADDRESS, xor_peer(peer_addr)),
                ],
            ))
            .await
            .unwrap();
        assert_eq!(
            stun::Header::decode(&recv(&client).await).unwrap().typ,
            stun::CHANNEL_BIND_RESPONSE
        );
        client
            .send(&channel::encode(chan, b"pong", false).unwrap())
            .await
            .unwrap();
        let (n, from) = {
            let mut b = vec![0u8; 1500];
            let (n, from) = tokio::time::timeout(Duration::from_secs(2), peer.recv_from(&mut b))
                .await
                .expect("peer recv timed out")
                .unwrap();
            b.truncate(n);
            (b, from)
        };
        assert_eq!(&n, b"pong");
        assert_eq!(from, SocketAddr::V4(relay_addr)); // came from the relay

        // 5) now that a channel is bound, peer → client comes back as ChannelData.
        peer.send_to(b"again", relay_addr).await.unwrap();
        let frame = recv(&client).await;
        let cd = channel::decode(&frame).expect("ChannelData frame");
        assert_eq!(cd.channel, chan);
        assert_eq!(cd.data, b"again");
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn allocate_rejects_bad_credentials() {
        let srv = Server::bind(
            "127.0.0.1:0".parse().unwrap(),
            TurnConfig {
                secret: SECRET.into(),
                relay_ip: Ipv4Addr::LOCALHOST,
                relay_ports: (0, 0),
            },
        )
        .await
        .unwrap();
        let srv_addr = srv.local_addr().unwrap();
        tokio::spawn(srv.clone().run());

        // a credential minted under the WRONG secret must fail MESSAGE-INTEGRITY.
        let bad = mint("WRONG", "r", 1, 4_102_444_800);
        let client = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        client.connect(srv_addr).await.unwrap();
        client
            .send(&authed(stun::ALLOCATE_REQUEST, &bad, &[]))
            .await
            .unwrap();
        let resp = recv(&client).await;
        let hdr = stun::Header::decode(&resp).unwrap();
        assert_eq!(hdr.typ, err_type(stun::ALLOCATE_REQUEST));
        // ERROR-CODE 401 (class 4, number 1).
        let ec = find_attr(&resp, stun::ATTR_ERROR_CODE).unwrap();
        assert_eq!((ec[2], ec[3]), (4, 1));
    }

    #[tokio::test]
    async fn binding_needs_no_auth() {
        let srv = Server::bind(
            "127.0.0.1:0".parse().unwrap(),
            TurnConfig {
                secret: SECRET.into(),
                relay_ip: Ipv4Addr::LOCALHOST,
                relay_ports: (0, 0),
            },
        )
        .await
        .unwrap();
        let srv_addr = srv.local_addr().unwrap();
        tokio::spawn(srv.clone().run());

        let client = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        client.connect(srv_addr).await.unwrap();
        let mut req = header(stun::BINDING_REQUEST, [3u8; 12]);
        stun::set_attr_length(&mut req);
        client.send(&req).await.unwrap();
        let resp = recv(&client).await;
        assert_eq!(
            stun::Header::decode(&resp).unwrap().typ,
            stun::BINDING_RESPONSE
        );
        // XOR-MAPPED-ADDRESS reflects the client's own port.
        let v = find_attr(&resp, stun::ATTR_XOR_MAPPED_ADDRESS).unwrap();
        let (_ip, port) = stun::decode_xor_mapped_v4(v).unwrap();
        assert_eq!(port, client.local_addr().unwrap().port());
    }
}
