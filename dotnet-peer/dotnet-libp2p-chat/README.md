# .NET libp2p Chat Application

A simple chat application built with .NET 8 and Nethermind.Libp2p that demonstrates peer-to-peer communication using libp2p protocols.

## Features

- Real-time peer-to-peer messaging
- Automatic peer discovery using mDNS
- JSON message format
- Console-based UI

## Prerequisites

- .NET 8 SDK
- Windows, macOS, or Linux operating system

## Getting Started

1. Clone this repository
2. Navigate to the project directory
3. Build and run the application:

```bash
dotnet build
dotnet run
```

For detailed debug logging, use the `--trace` flag:

```bash
dotnet run -- --trace
```

## How to Use

1. The application will start and automatically connect to other peers on the local network.
2. Type your message and press Enter to send it to all connected peers.
3. Type `exit` to quit the application.

## Technical Details

- Uses Nethermind.Libp2p for libp2p protocol implementation
- PubSub for message broadcasting
- mDNS for peer discovery
- Messages are serialized using JSON

## Project Structure

- `Program.cs` - Main application code
- `dotnet-libp2p-chat.csproj` - Project file with dependencies

## Dependencies

- Microsoft.Extensions.DependencyInjection
- Microsoft.Extensions.Logging
- Nethermind.Libp2p
- Nethermind.Libp2p.Protocols.Pubsub

## Troubleshooting

- If no peers are found, ensure you are on the same local network.
- Check that UDP multicast is enabled on your network.
- Verify that your firewall allows the application to communicate.

## License

MIT
