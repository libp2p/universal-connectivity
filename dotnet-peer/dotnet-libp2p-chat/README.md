# Universal Connectivity - .NET libp2p Chat

A cross-platform, peer-to-peer chat application built with .NET 8 and libp2p, demonstrating interoperability with other libp2p implementations.

## Overview

This project is part of the Universal Connectivity initiative, which aims to demonstrate interoperability between different libp2p implementations across various programming languages and platforms. This .NET implementation provides a console-based chat application that can communicate with other libp2p peers, including those written in JavaScript, Rust, Go, and other languages.

## Features

- **Peer-to-Peer Communication**: Direct messaging between peers without a central server
- **Multiple Transport Protocols**: Support for TCP and QUIC transports
- **PubSub Messaging**: Group chat functionality using libp2p's publish-subscribe system
- **Peer Discovery**: Automatic peer discovery using mDNS
- **Interactive Console UI**: User-friendly console interface for sending and receiving messages
- **Cross-Language Compatibility**: Interoperates with libp2p implementations in other languages

## Prerequisites

- [.NET 8.0 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) or later
- Basic understanding of peer-to-peer networking concepts

## Installation

Clone the repository and build the project:

```bash
git clone https://github.com/yourusername/universal-connectivity.git
cd universal-connectivity/dotnet-peer/dotnet-libp2p-chat
dotnet build
```

## Usage

### Running as a Server (Listener)

To start the application in listening mode:

```bash
dotnet run -- --trace
```

This will start a libp2p node that listens for incoming connections. The application will display your peer's multiaddress, which other peers can use to connect to you.

### Running as a Client (Dialer)

To connect to another peer:

```bash
dotnet run -- -d /ip4/127.0.0.1/tcp/PORT/p2p/PEER_ID --trace
```

Replace `PORT` with the port number and `PEER_ID` with the peer ID from the peer you want to connect to.

### Additional Command-Line Options

- `-sp PORT`: Specify a port to listen on (e.g., `-sp 5001`)
- `-quic`: Use QUIC transport instead of TCP
- `--trace`: Enable detailed logging

### Chat Commands

Once connected, you can:
- Type a message and press Enter to send it
- Type `exit` to close the connection

## Architecture

The application is built using the following components:

- **Nethermind.Libp2p**: Core libp2p implementation for .NET
- **ChatProtocol**: Custom protocol implementation for handling chat messages
- **ConsoleReader**: Non-blocking console input handler
- **Libp2pService**: Service for managing libp2p node lifecycle and connections
- **PubSub**: Publish-subscribe system for group messaging

## Project Structure

```
dotnet-libp2p-chat/
├── Program.cs                 # Main entry point
├── Chat.csproj                # Project file with dependencies
├── src/
│   ├── Core/                  # Core interfaces and models
│   │   ├── Interfaces/        # Interface definitions
│   │   └── Models/            # Data models
│   ├── Services/              # Service implementations
│   │   ├── Libp2pService.cs   # libp2p node management
│   │   ├── ChatService.cs     # Chat functionality
│   │   └── MessageStore.cs    # Message storage
│   └── UI/                    # User interface components
│       ├── ConsoleUI.cs       # Console UI implementation
│       └── Themes/            # UI themes
└── Properties/                # Project properties
```

## Interoperability

This application is designed to work with other libp2p implementations, including:

- JavaScript (browser and Node.js)
- Rust
- Go
- Python

To test interoperability, you can run peers implemented in different languages and connect them to each other.

## Development

### Adding New Features

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Running Tests

```bash
dotnet test
```

## Troubleshooting

### Common Issues

1. **Connection Refused Error**:
   - Ensure the server is running
   - Check if the port is correct
   - Verify there are no firewall issues

2. **Multiaddress Parsing Error**:
   - Ensure the multiaddress format is correct
   - Check for typos in the peer ID or port

3. **Protocol Negotiation Failure**:
   - Verify both peers are using compatible protocol versions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

*This project is part of the Universal Connectivity initiative, demonstrating interoperability between different libp2p implementations.*
