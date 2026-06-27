//! TURN allocation state machine (RFC 8656 §5–§11) — pure logic, no sockets.
//!
//! Models the server-side lifecycle the UDP/TCP listeners will drive: 5-tuple
//! allocations, peer permissions, channel bindings, and time-based expiry. All
//! methods take `now` (unix seconds) so the model is deterministic and testable
//! without a clock. Relay-port assignment and packet forwarding live in the
//! listener layer; this module only tracks *what is allowed*.

use crate::Scope;
use std::collections::HashMap;
use std::net::{IpAddr, SocketAddr};

/// Default allocation lifetime when the client requests 0 (RFC 8656 §6.2).
pub const DEFAULT_LIFETIME: u64 = 600;
/// Maximum allocation lifetime the server grants; longer requests are clamped.
pub const MAX_LIFETIME: u64 = 3600;
/// Permission lifetime, fixed by RFC 8656 §9.
pub const PERMISSION_LIFETIME: u64 = 300;
/// Channel-binding lifetime, fixed by RFC 8656 §12.
pub const CHANNEL_LIFETIME: u64 = 600;

/// Transport between client and server (the third element of the 5-tuple).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TransportProto {
    Udp,
    Tcp,
}

/// The TURN allocation key: (client address, server address, transport).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct FiveTuple {
    pub client: SocketAddr,
    pub server: SocketAddr,
    pub proto: TransportProto,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum AllocError {
    /// Allocate on an existing 5-tuple, or an op on a missing one (RFC 437).
    #[error("allocation mismatch")]
    Mismatch,
    /// Channel number outside the valid 0x4000–0x7FFF range (RFC 8656 §12).
    #[error("bad channel number")]
    BadChannel,
}

#[derive(Clone, Debug)]
struct Allocation {
    relay: SocketAddr,
    scope: Scope,
    expires_at: u64,
    /// peer IP → permission expiry.
    permissions: HashMap<IpAddr, u64>,
    /// channel number → (peer, expiry).
    channels: HashMap<u16, (SocketAddr, u64)>,
}

fn clamp_lifetime(requested: u64) -> u64 {
    if requested == 0 {
        DEFAULT_LIFETIME
    } else {
        requested.min(MAX_LIFETIME)
    }
}

fn channel_in_range(n: u16) -> bool {
    (0x4000..=0x7FFF).contains(&n)
}

/// All live allocations, keyed by 5-tuple.
#[derive(Default)]
pub struct AllocationTable {
    allocations: HashMap<FiveTuple, Allocation>,
}

impl AllocationTable {
    pub fn new() -> Self {
        Self::default()
    }

    /// Create an allocation. Returns the granted absolute expiry, or `Mismatch`
    /// if one already exists for this 5-tuple.
    pub fn allocate(
        &mut self,
        tuple: FiveTuple,
        relay: SocketAddr,
        scope: Scope,
        requested_lifetime: u64,
        now: u64,
    ) -> Result<u64, AllocError> {
        if self.is_live(&tuple, now) {
            return Err(AllocError::Mismatch);
        }
        let expires_at = now + clamp_lifetime(requested_lifetime);
        self.allocations.insert(
            tuple,
            Allocation {
                relay,
                scope,
                expires_at,
                permissions: HashMap::new(),
                channels: HashMap::new(),
            },
        );
        Ok(expires_at)
    }

    /// Refresh an allocation. `requested_lifetime == 0` deletes it (RFC 8656 §7).
    pub fn refresh(
        &mut self,
        tuple: &FiveTuple,
        requested_lifetime: u64,
        now: u64,
    ) -> Result<u64, AllocError> {
        if !self.is_live(tuple, now) {
            return Err(AllocError::Mismatch);
        }
        if requested_lifetime == 0 {
            self.allocations.remove(tuple);
            return Ok(0);
        }
        let alloc = self
            .allocations
            .get_mut(tuple)
            .ok_or(AllocError::Mismatch)?;
        alloc.expires_at = now + clamp_lifetime(requested_lifetime);
        Ok(alloc.expires_at)
    }

    /// Install/refresh a peer permission (CreatePermission).
    pub fn create_permission(
        &mut self,
        tuple: &FiveTuple,
        peer: IpAddr,
        now: u64,
    ) -> Result<(), AllocError> {
        let alloc = self.live_mut(tuple, now)?;
        alloc.permissions.insert(peer, now + PERMISSION_LIFETIME);
        Ok(())
    }

    /// Is `peer` currently permitted to exchange data on this allocation?
    pub fn permitted(&self, tuple: &FiveTuple, peer: IpAddr, now: u64) -> bool {
        self.allocations
            .get(tuple)
            .filter(|a| a.expires_at > now)
            .and_then(|a| a.permissions.get(&peer))
            .is_some_and(|&exp| exp > now)
    }

    /// Bind a channel to a peer (ChannelBind). Also installs a permission for the
    /// peer's IP, per RFC 8656 §12. Rejects out-of-range channel numbers.
    pub fn bind_channel(
        &mut self,
        tuple: &FiveTuple,
        channel: u16,
        peer: SocketAddr,
        now: u64,
    ) -> Result<(), AllocError> {
        if !channel_in_range(channel) {
            return Err(AllocError::BadChannel);
        }
        let alloc = self.live_mut(tuple, now)?;
        alloc
            .channels
            .insert(channel, (peer, now + CHANNEL_LIFETIME));
        alloc
            .permissions
            .insert(peer.ip(), now + PERMISSION_LIFETIME);
        Ok(())
    }

    /// Resolve a channel number to its bound peer, if the binding is live.
    pub fn channel_peer(&self, tuple: &FiveTuple, channel: u16, now: u64) -> Option<SocketAddr> {
        self.allocations
            .get(tuple)
            .filter(|a| a.expires_at > now)
            .and_then(|a| a.channels.get(&channel))
            .filter(|&&(_, exp)| exp > now)
            .map(|&(peer, _)| peer)
    }

    /// The channel bound to `peer` on this allocation, if any (the reverse of
    /// [`channel_peer`]). Lets the relay forward peer→client traffic as a
    /// ChannelData frame instead of a Data indication when a channel exists.
    pub fn channel_for_peer(&self, tuple: &FiveTuple, peer: SocketAddr, now: u64) -> Option<u16> {
        self.allocations
            .get(tuple)
            .filter(|a| a.expires_at > now)
            .and_then(|a| {
                a.channels
                    .iter()
                    .find(|(_, &(p, exp))| p == peer && exp > now)
                    .map(|(&c, _)| c)
            })
    }

    /// The relay address assigned to a live allocation.
    pub fn relay_addr(&self, tuple: &FiveTuple, now: u64) -> Option<SocketAddr> {
        self.allocations
            .get(tuple)
            .filter(|a| a.expires_at > now)
            .map(|a| a.relay)
    }

    /// The owning room/player scope of a live allocation.
    pub fn scope(&self, tuple: &FiveTuple, now: u64) -> Option<&Scope> {
        self.allocations
            .get(tuple)
            .filter(|a| a.expires_at > now)
            .map(|a| &a.scope)
    }

    /// Drop expired allocations, and expired permissions/channels within live ones.
    /// Returns the number of whole allocations removed.
    pub fn gc(&mut self, now: u64) -> usize {
        let before = self.allocations.len();
        self.allocations.retain(|_, a| a.expires_at > now);
        for a in self.allocations.values_mut() {
            a.permissions.retain(|_, &mut exp| exp > now);
            a.channels.retain(|_, &mut (_, exp)| exp > now);
        }
        before - self.allocations.len()
    }

    /// Count of live allocations (after lazily ignoring expired ones).
    pub fn live_count(&self, now: u64) -> usize {
        self.allocations
            .values()
            .filter(|a| a.expires_at > now)
            .count()
    }

    fn is_live(&self, tuple: &FiveTuple, now: u64) -> bool {
        self.allocations
            .get(tuple)
            .is_some_and(|a| a.expires_at > now)
    }

    fn live_mut(&mut self, tuple: &FiveTuple, now: u64) -> Result<&mut Allocation, AllocError> {
        match self.allocations.get_mut(tuple) {
            Some(a) if a.expires_at > now => Ok(a),
            _ => Err(AllocError::Mismatch),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tuple() -> FiveTuple {
        FiveTuple {
            client: "203.0.113.5:51000".parse().unwrap(),
            server: "198.51.100.1:3478".parse().unwrap(),
            proto: TransportProto::Udp,
        }
    }
    fn relay() -> SocketAddr {
        "198.51.100.1:49160".parse().unwrap()
    }
    fn scope() -> Scope {
        Scope {
            room: "r".into(),
            player: 1,
            expires_at: 9_999_999_999,
        }
    }

    #[test]
    fn allocate_then_reject_duplicate() {
        let mut t = AllocationTable::new();
        let exp = t.allocate(tuple(), relay(), scope(), 0, 1000).unwrap();
        assert_eq!(exp, 1000 + DEFAULT_LIFETIME);
        assert_eq!(t.relay_addr(&tuple(), 1000), Some(relay()));
        assert_eq!(
            t.allocate(tuple(), relay(), scope(), 0, 1000),
            Err(AllocError::Mismatch)
        );
    }

    #[test]
    fn requested_lifetime_is_clamped() {
        let mut t = AllocationTable::new();
        let exp = t.allocate(tuple(), relay(), scope(), 100_000, 0).unwrap();
        assert_eq!(exp, MAX_LIFETIME); // now=0 + clamp(100000)=3600
    }

    #[test]
    fn refresh_extends_and_zero_deletes() {
        let mut t = AllocationTable::new();
        t.allocate(tuple(), relay(), scope(), 600, 1000).unwrap();
        let exp = t.refresh(&tuple(), 600, 1500).unwrap();
        assert_eq!(exp, 1500 + 600);
        assert_eq!(t.refresh(&tuple(), 0, 1600).unwrap(), 0);
        assert_eq!(t.relay_addr(&tuple(), 1600), None);
        assert_eq!(t.refresh(&tuple(), 600, 1600), Err(AllocError::Mismatch));
    }

    #[test]
    fn permissions_respect_lifetime() {
        let mut t = AllocationTable::new();
        t.allocate(tuple(), relay(), scope(), 3600, 0).unwrap();
        let peer: IpAddr = "192.0.2.9".parse().unwrap();
        assert!(!t.permitted(&tuple(), peer, 0));
        t.create_permission(&tuple(), peer, 100).unwrap();
        assert!(t.permitted(&tuple(), peer, 100 + PERMISSION_LIFETIME - 1));
        assert!(!t.permitted(&tuple(), peer, 100 + PERMISSION_LIFETIME + 1));
    }

    #[test]
    fn channel_bind_range_and_resolution() {
        let mut t = AllocationTable::new();
        t.allocate(tuple(), relay(), scope(), 3600, 0).unwrap();
        let peer: SocketAddr = "192.0.2.9:6000".parse().unwrap();
        assert_eq!(
            t.bind_channel(&tuple(), 0x3FFF, peer, 0),
            Err(AllocError::BadChannel)
        );
        t.bind_channel(&tuple(), 0x4001, peer, 0).unwrap();
        assert_eq!(t.channel_peer(&tuple(), 0x4001, 10), Some(peer));
        // ChannelBind also implies a permission for the peer IP.
        assert!(t.permitted(&tuple(), peer.ip(), 10));
        assert_eq!(t.channel_peer(&tuple(), 0x4001, CHANNEL_LIFETIME + 1), None);
    }

    #[test]
    fn gc_drops_expired_allocations() {
        let mut t = AllocationTable::new();
        t.allocate(tuple(), relay(), scope(), 600, 0).unwrap();
        assert_eq!(t.live_count(0), 1);
        assert_eq!(t.gc(601), 1); // expired → removed
        assert_eq!(t.live_count(601), 0);
    }
}
