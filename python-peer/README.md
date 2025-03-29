# Python libp2p Universal Connectivity

This is a Python implementation of the Universal Connectivity chat application, demonstrating libp2p's capabilities in establishing peer-to-peer connections across different platforms and languages.

## Features

- Cross-platform connectivity with JS, Go, and Rust implementations
- Support for multiple transport protocols:
  - WebRTC Direct
  - TCP
  - (WebTransport and QUIC support planned for future releases)
- PubSub using GossipSub for group messaging
- Direct messaging between peers
- File sharing capabilities
- Peer discovery using mDNS and DHT

## Getting Started

### Prerequisites

- Python 3.8 or later

### Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the application

Start the Python peer:

```bash
python main.py
```

Optional arguments:
- `--nick NAME`: Set your nickname (default: generated from peer ID)
- `--identity PATH`: Path to identity key file (default: identity.key)
- `--connect ADDR`: Multiaddr to connect to (can be repeated for multiple peers)

## Architecture

The Python peer implementation consists of several key components:

1. **Node Configuration**: Setup of the libp2p node with appropriate transports and protocols
2. **Chat Room**: Implementation of the GossipSub-based group chat
3. **Direct Messaging**: Protocol for peer-to-peer direct messages
4. **File Exchange**: Protocol for sharing files between peers
5. **UI**: Terminal-based user interface

## Integration with Other Implementations

This Python implementation is compatible with the JS, Go, and Rust peers in the Universal Connectivity project. It can:

- Connect to bootstrap nodes
- Discover peers via mDNS and DHT
- Exchange messages via GossipSub
- Send direct messages to peers
- Share files with peers

## Development

See the `CONTRIBUTING.md` file for guidelines on contributing to this project.

## License

This project is licensed under the dual MIT/Apache-2.0 license - see the LICENSE-MIT and LICENSE-APACHE files for details.