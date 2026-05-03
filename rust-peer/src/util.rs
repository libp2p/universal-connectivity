use libp2p::{multiaddr::Protocol, Multiaddr, PeerId};
use quick_protobuf::reader::BytesReader;
use std::{convert::TryFrom, fmt, net::IpAddr};

/// Define protobuf wire types since they are no longer in quick-protobuf
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum WireType {
    /// Varint wire type
    Varint = 0,
    /// Fixed64 wire type
    Fixed64 = 1,
    /// Length-delimited wire type
    LengthDelimited = 2,
    /// Start group wire type
    StartGroup = 3,
    /// End group wire type
    EndGroup = 4,
    /// Fixed32 wire type
    Fixed32 = 5,
}

/// Error type for TryFrom conversion
#[derive(Debug)]
pub struct InvalidWireType(u32);

impl fmt::Display for InvalidWireType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Invalid wire type value: {}", self.0)
    }
}

impl std::error::Error for InvalidWireType {}

impl TryFrom<u32> for WireType {
    type Error = InvalidWireType;

    fn try_from(tag: u32) -> Result<Self, Self::Error> {
        // Extract wire type from the lower 3 bits
        let wire_type_value = tag & 0x07;

        match wire_type_value {
            0 => Ok(WireType::Varint),
            1 => Ok(WireType::Fixed64),
            2 => Ok(WireType::LengthDelimited),
            3 => Ok(WireType::StartGroup),
            4 => Ok(WireType::EndGroup),
            5 => Ok(WireType::Fixed32),
            invalid => Err(InvalidWireType(invalid)),
        }
    }
}

/// Decode an unknown protobuf message into a list of fields
pub fn decode_unknown_protobuf(bytes: &[u8]) -> anyhow::Result<Vec<String>> {
    let mut reader = BytesReader::from_bytes(bytes);
    let mut fields = Vec::new();

    // Read the next tag
    while let Ok(tag) = reader.next_tag(bytes) {
        // Extract field number and wire type
        let field_number = tag >> 3;
        let wire_type = WireType::try_from(tag).map_err(|e| {
            quick_protobuf::Error::Message(format!("Invalid wire type value: {}", e.0))
        })?;

        // Decode the value based on wire type
        let value = match wire_type {
            WireType::Varint => {
                let varint = reader.read_varint64(bytes)?;
                format!("int64: {}", varint) // Could also be int32, uint32, etc.
            }
            WireType::Fixed64 => {
                let fixed64 = reader.read_fixed64(bytes)?;
                format!("fixed64: {}", fixed64) // Could also be double
            }
            WireType::LengthDelimited => {
                let len = reader.read_varint32(bytes)? as usize;
                let data = reader.read_bytes(bytes)?;
                // Try to interpret as string; if it fails, treat as raw bytes
                match std::str::from_utf8(data) {
                    Ok(s) => format!("string: \"{}\"", s),
                    Err(_) => format!("bytes({}): {}", len, hex::encode(data)),
                }
            }
            WireType::Fixed32 => {
                let fixed32 = reader.read_fixed32(bytes)?;
                format!("fixed32: {}", fixed32) // Could also be float
            }
            WireType::StartGroup | WireType::EndGroup => {
                // Groups are deprecated and rare; skip for simplicity
                return Err(
                    quick_protobuf::Error::Message("Groups not supported".to_string()).into(),
                );
            }
        };

        fields.push(format!(
            "Field {} ({:?}): {}",
            field_number, wire_type, value
        ));
    }

    Ok(fields)
}

/// Pretty print a list of fields
pub fn pretty_print_fields(fields: &[String]) -> String {
    let mut output = String::new();
    output.push_str("Decoded Protobuf Message {\n");
    for field in fields {
        output.push_str("  ");
        output.push_str(field);
        output.push('\n');
    }
    output.push('}');
    output
}

/// Split the PeerId from a Multiaddr
pub fn split_peer_id(multiaddr: Multiaddr) -> Option<(Multiaddr, PeerId)> {
    let mut base_addr = Multiaddr::empty();
    let mut peer_id = None;

    // Iterate over the protocols in the Multiaddr
    for protocol in multiaddr.into_iter() {
        if let Protocol::P2p(id) = protocol {
            peer_id = Some(id);
            break; // Stop once we find the P2p component
        } else {
            base_addr.push(protocol); // Add non-P2p components to the base address
        }
    }

    peer_id.map(|id| (base_addr, id))
}

/// Extract the IP address from a Multiaddr
pub fn extract_ip_multiaddr(multiaddr: &Multiaddr) -> Option<Multiaddr> {
    let mut result = Multiaddr::empty();

    for component in multiaddr.into_iter() {
        match component {
            Protocol::Ip4(addr) => {
                result.push(Protocol::Ip4(addr));
                return Some(result);
            }
            Protocol::Ip6(addr) => {
                result.push(Protocol::Ip6(addr));
                return Some(result);
            }
            _ => continue,
        }
    }

    None
}

/// Check if a Multiaddr contains a private IP address
pub fn is_private_ip(multiaddr: &Multiaddr) -> bool {
    for component in multiaddr.into_iter() {
        match component {
            Protocol::Ip4(addr) => {
                return addr.is_private() ||    // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
                       addr.is_loopback() ||   // 127.0.0.0/8
                       addr.is_link_local() || // 169.254.0.0/16
                       addr.is_unspecified(); // 0.0.0.0
            }
            Protocol::Ip6(addr) => {
                return addr.is_loopback() ||    // ::1
                       addr.is_unspecified() || // ::
                       // Unique Local Address (fc00::/7 where 8th bit is 1)
                       (addr.segments()[0] & 0xfe00 == 0xfc00) ||
                       // Link-Local unicast (fe80::/10)
                       (addr.segments()[0] & 0xffc0 == 0xfe80);
            }
            _ => continue,
        }
    }
    false
}

/// Convert an IP address to a Multiaddr
pub fn ipaddr_to_multiaddr(ip: &IpAddr) -> Multiaddr {
    let multiaddr = match ip {
        IpAddr::V4(ipv4) => Multiaddr::empty().with(Protocol::Ip4(*ipv4)),
        IpAddr::V6(ipv6) => Multiaddr::empty().with(Protocol::Ip6(*ipv6)),
    };
    multiaddr
}
