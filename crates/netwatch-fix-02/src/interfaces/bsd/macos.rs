use super::{MessageType, RoutingStack, WireFormat};

// Hardcoded based on the generated values here: https://cs.opensource.google/go/x/net/+/master:route/zsys_darwin.go
const SIZEOF_IF_MSGHDR_DARWIN15: usize = 0x70;
const SIZEOF_IFA_MSGHDR_DARWIN15: usize = 0x14;
const SIZEOF_IFMA_MSGHDR_DARWIN15: usize = 0x10;
const SIZEOF_IF_MSGHDR2_DARWIN15: usize = 0xa0;
const SIZEOF_IFMA_MSGHDR2_DARWIN15: usize = 0x14;
const SIZEOF_IF_DATA_DARWIN15: usize = 0x60;
const SIZEOF_IF_DATA64_DARWIN15: usize = 0x80;

const SIZEOF_RT_MSGHDR_DARWIN15: usize = 0x5c;
const SIZEOF_RT_MSGHDR2_DARWIN15: usize = 0x5c;
const SIZEOF_RT_METRICS_DARWIN15: usize = 0x38;

const SIZEOF_SOCKADDR_STORAGE: usize = 0x80;
pub(super) const SIZEOF_SOCKADDR_INET: usize = 0x10;
pub(super) const SIZEOF_SOCKADDR_INET6: usize = 0x1c;

pub(super) fn probe_routing_stack() -> RoutingStack {
    let rtm_version = libc::RTM_VERSION;

    let rtm = WireFormat {
        ext_off: 36,
        body_off: SIZEOF_RT_MSGHDR_DARWIN15,
        typ: MessageType::Route,
    };
    let rtm2 = WireFormat {
        ext_off: 36,
        body_off: SIZEOF_RT_MSGHDR2_DARWIN15,
        typ: MessageType::Route,
    };
    let ifm = WireFormat {
        ext_off: 16,
        body_off: SIZEOF_IF_MSGHDR_DARWIN15,
        typ: MessageType::Interface,
    };
    let ifm2 = WireFormat {
        ext_off: 32,
        body_off: SIZEOF_IF_MSGHDR2_DARWIN15,
        typ: MessageType::Interface,
    };
    let ifam = WireFormat {
        ext_off: SIZEOF_IFA_MSGHDR_DARWIN15,
        body_off: SIZEOF_IFA_MSGHDR_DARWIN15,
        typ: MessageType::InterfaceAddr,
    };
    let ifmam = WireFormat {
        ext_off: SIZEOF_IFMA_MSGHDR_DARWIN15,
        body_off: SIZEOF_IFMA_MSGHDR_DARWIN15,
        typ: MessageType::InterfaceMulticastAddr,
    };
    let ifmam2 = WireFormat {
        ext_off: SIZEOF_IFMA_MSGHDR2_DARWIN15,
        body_off: SIZEOF_IFMA_MSGHDR2_DARWIN15,
        typ: MessageType::InterfaceMulticastAddr,
    };

    let wire_formats = [
        (libc::RTM_ADD, rtm),
        (libc::RTM_DELETE, rtm),
        (libc::RTM_CHANGE, rtm),
        (libc::RTM_GET, rtm),
        (libc::RTM_LOSING, rtm),
        (libc::RTM_REDIRECT, rtm),
        (libc::RTM_MISS, rtm),
        (libc::RTM_LOCK, rtm),
        (libc::RTM_RESOLVE, rtm),
        (libc::RTM_NEWADDR, ifam),
        (libc::RTM_DELADDR, ifam),
        (libc::RTM_IFINFO, ifm),
        (libc::RTM_NEWMADDR, ifmam),
        (libc::RTM_DELMADDR, ifmam),
        (libc::RTM_IFINFO2, ifm2),
        (libc::RTM_NEWMADDR2, ifmam2),
        (libc::RTM_GET2, rtm2),
    ]
    .into_iter()
    .collect();

    RoutingStack {
        rtm_version,
        wire_formats,
        kernel_align: 4,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sockaddr_inet_is_16_bytes() {
        assert_eq!(SIZEOF_SOCKADDR_INET, 16);
    }

    #[test]
    fn sockaddr_inet6_is_28_bytes() {
        assert_eq!(SIZEOF_SOCKADDR_INET6, 28);
    }

    #[test]
    fn rt_msghdr_size_matches_darwin15() {
        assert_eq!(SIZEOF_RT_MSGHDR_DARWIN15, 0x5c);
    }

    #[test]
    fn if_msghdr2_larger_than_if_msghdr() {
        assert!(SIZEOF_IF_MSGHDR2_DARWIN15 > SIZEOF_IF_MSGHDR_DARWIN15);
    }

    #[test]
    fn probe_routing_stack_has_17_wire_formats() {
        let rs = probe_routing_stack();
        assert_eq!(rs.wire_formats.len(), 17);
    }

    #[test]
    fn probe_routing_stack_kernel_align_is_4() {
        let rs = probe_routing_stack();
        assert_eq!(rs.kernel_align, 4);
    }
}
