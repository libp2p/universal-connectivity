using Chat.Core.Interfaces;
using Microsoft.Extensions.Logging;
using Chat.Core.Models;
using Nethermind.Libp2p.Core;
using System.Collections.Concurrent;
using Nethermind.Libp2p.Protocols;
using System.Collections.ObjectModel;
using Nethermind.Libp2p.Stack;
using Nethermind.Libp2p.Core.Discovery;

public class Libp2pService : ILibp2pNode, IDisposable
{
    private readonly ILogger<Libp2pService> _logger;
    private readonly IMessageStore _messageStore;
    private readonly IServiceProvider _serviceProvider;
    private ILocalPeer? _localPeer;
    private readonly ConcurrentDictionary<string, IRemotePeer> _peers;
    private readonly ChatProtocol _chatProtocol;

    public Libp2pService(
        ILogger<Libp2pService> logger,
        IMessageStore messageStore,
        IServiceProvider serviceProvider)
    {
        _logger = logger;
        _messageStore = messageStore;
        _serviceProvider = serviceProvider;
        _peers = new ConcurrentDictionary<string, IRemotePeer>();
        _chatProtocol = new ChatProtocol();
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Starting libp2p node");

        var factory = new PeerFactory(_serviceProvider);
        var identity = new Identity();
        _localPeer = factory.Create(identity);

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Failed to create libp2p peer");
        }

        // Log the peer ID
        _logger.LogInformation("Peer ID: {PeerId}", _localPeer.Identity.PeerId);
        _logger.LogInformation("To connect to this peer, use: /ip4/127.0.0.1/tcp/5001/p2p/{PeerId}", _localPeer.Identity.PeerId);

        _logger.LogInformation("Libp2p node started");
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Stopping libp2p node");

        foreach (var peer in _peers.Values)
        {
            await peer.DisconnectAsync();
        }
        _peers.Clear();

        _localPeer = null;
    }

    public async Task BroadcastMessageAsync(string room, string message)
    {
        _logger.LogInformation("Broadcasting message to room {Room}", room);

        var chatMessage = new ChatMessage("System", message, DateTimeOffset.UtcNow);
        await _messageStore.AddMessageAsync(room, chatMessage);

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Libp2p node not started");
        }

        // Broadcast to all connected peers
        foreach (var peer in _peers.Values)
        {
            try
            {
                var protocol = new ChatProtocol();
                await peer.DialAsync<ChatProtocol>(CancellationToken.None);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to broadcast message to peer");
            }
        }
    }

    public Task JoinRoomAsync(string room)
    {
        _logger.LogInformation("Joining room {Room}", room);
        // In libp2p, rooms are typically implemented as PubSub topics
        // For this basic implementation, we'll just maintain room state locally
        return Task.CompletedTask;
    }

    public Task LeaveRoomAsync(string room)
    {
        _logger.LogInformation("Leaving room {Room}", room);
        return Task.CompletedTask;
    }

    public async Task ConnectToPeerAsync(string peerAddress)
    {
        _logger.LogInformation("Connecting to peer at {Address}", peerAddress);

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Libp2p node not started");
        }

        try
        {
            var multiaddr = new Multiaddr(peerAddress);
            var remotePeer = await _localPeer.DialAsync(multiaddr);
            await remotePeer.DialAsync<ChatProtocol>(CancellationToken.None);
            _peers.TryAdd(remotePeer.Identity.PeerId, remotePeer);
            _logger.LogInformation("Connected to peer: {PeerId}", remotePeer.Identity.PeerId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect to peer");
            throw;
        }
    }

    public async Task SendMessageToPeerAsync(string peerId, string message)
    {
        _logger.LogInformation("Sending message to peer {PeerId}", peerId);

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Libp2p node not started");
        }

        if (!_peers.TryGetValue(peerId, out var peer))
        {
            throw new InvalidOperationException($"Not connected to peer {peerId}");
        }

        try
        {
            var protocol = new ChatProtocol();
            await peer.DialAsync<ChatProtocol>(CancellationToken.None);
            // Message will be handled by the ChatProtocol.HandleAsync method
            _logger.LogInformation("Message sent to peer {PeerId}", peerId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send message to peer");
            throw;
        }
    }

    public void Dispose()
    {
        StopAsync(CancellationToken.None).Wait();
    }
}

public class ChatProtocol : IProtocol
{
    private readonly string _protocolId = "/chat/1.0.0";
    public string Id => _protocolId;

    public async Task HandleAsync(IChannel channel, IPeerContext context)
    {
        try
        {
            var cts = new CancellationTokenSource();
            while (!cts.Token.IsCancellationRequested)
            {
                var buffer = new byte[1024];
                var sequence = await channel.ReadAsync(buffer.Length);
                if (sequence.IsEmpty) break;

                await channel.WriteAsync(sequence);
            }
        }
        catch (Exception)
        {
        }
    }

    public Task ListenAsync(IChannel channel, IChannelFactory? channelFactory, IPeerContext context)
    {
        return HandleAsync(channel, context);
    }

    public Task DialAsync(IChannel channel, IChannelFactory? channelFactory, IPeerContext context)
    {
        return HandleAsync(channel, context);
    }
}
