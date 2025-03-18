using Microsoft.Extensions.Logging;
using Multiformats.Address;
using Nethermind.Libp2p.Core;
using Chat.Core.Interfaces;
using System.Collections.Concurrent;
using Chat.Core.Models;
using Nethermind.Libp2p.Protocols.Pubsub;

namespace Chat.Services;

public class Libp2pService : ILibp2pNode, IDisposable
{
    private readonly ILogger<Libp2pService> _logger;
    private readonly IMessageStore? _messageStore;
    private readonly Nethermind.Libp2p.Core.IPeerFactory _peerFactory;
    private readonly PubsubRouter _router;
    private ILocalPeer? _localPeer;
    private readonly ConcurrentDictionary<string, ISession> _peers;
    private ITopic? _topic;

    public event EventHandler<string>? MessageReceived;

    public Libp2pService(
        ILogger<Libp2pService> logger,
        Nethermind.Libp2p.Core.IPeerFactory peerFactory,
        IMessageStore? messageStore = null,
        PubsubRouter router = null)
    {
        _logger = logger;
        _peerFactory = peerFactory;
        _messageStore = messageStore;
        _router = router;
        _peers = new ConcurrentDictionary<string, ISession>();
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Starting libp2p node");

        Identity localPeerIdentity = new();
        string addr = $"/ip4/0.0.0.0/tcp/0/p2p/{localPeerIdentity.PeerId}";

        _localPeer = _peerFactory.Create(localPeerIdentity);
        await _localPeer.StartListenAsync([addr], cancellationToken);

        string peerId = _localPeer.Identity.PeerId.ToString();
        _logger.LogInformation("Local peer started with ID: {PeerId}", peerId);

        // Set up connection handler
        _localPeer.OnConnected += HandleNewConnection;

        _logger.LogInformation("Libp2p node started");
    }

    private void HandleNewConnection(ISession session)
    {
        var peerId = session.Id;
        _logger.LogInformation("New peer connected: {PeerId}", peerId);
        
        _peers.TryAdd(peerId, session);
        
        // Here we could automatically establish protocols with the connected peer
    }

    public async Task StopAsync()
    {
        _logger.LogInformation("Stopping libp2p node");

        foreach (var peer in _peers.Values)
        {
            try
            {
                await peer.DisconnectAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error disconnecting from peer");
            }
        }
        _peers.Clear();

        if (_localPeer != null)
        {
            await _localPeer.DisconnectAsync();
            _localPeer = null;
            _logger.LogInformation("Local peer stopped");
        }
    }

    public async Task BroadcastMessageAsync(string room, string message)
    {
        _logger.LogInformation("Broadcasting message to room {Room}", room);

        if (_messageStore != null)
        {
            var chatMessage = new ChatMessage(message, "dotnet-peer", DateTimeOffset.UtcNow);
            await _messageStore.AddMessageAsync(room, chatMessage);
        }

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Libp2p node not started");
        }

        // In a full implementation, this would publish to a PubSub topic
        _logger.LogInformation("Message broadcasted to room {Room}: {Message}", room, message);
    }

    public async Task JoinRoomAsync(string roomName)
    {
        if (_localPeer is null)
        {
            throw new InvalidOperationException("Local peer not started");
        }

        _topic = _router.GetTopic($"chat-room:{roomName}");
        _topic.OnMessage += OnMessageReceived;
        await _router.StartAsync(_localPeer);

        _logger.LogInformation("Joined room: {RoomName}", roomName);
    }

    public async Task SendMessageAsync(string message)
    {
        if (_topic is null)
        {
            throw new InvalidOperationException("Not joined to any room");
        }

        _topic.Publish(System.Text.Encoding.UTF8.GetBytes(message));
        _logger.LogInformation("Message sent: {Message}", message);
    }

    private void OnMessageReceived(byte[] msg)
    {
        string message = System.Text.Encoding.UTF8.GetString(msg);
        MessageReceived?.Invoke(this, message);
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
            var multiaddr = new Multiaddress(peerAddress);
            var remotePeer = await _localPeer.DialAsync(multiaddr);
            
            string peerId = remotePeer.Id;
            _peers.TryAdd(peerId, remotePeer);
            
            _logger.LogInformation("Connected to peer: {PeerId}", peerId);
            
            // Attempt to establish the chat protocol
            try
            {
                await remotePeer.DialAsync<Chat.ChatProtocol>();
                _logger.LogInformation("Chat protocol established with peer {PeerId}", peerId);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to establish chat protocol with peer {PeerId}", peerId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect to peer at {Address}", peerAddress);
            throw;
        }
    }

    public async Task ConnectAsync(string multiaddress)
    {
        if (_localPeer is null)
        {
            throw new InvalidOperationException("Local peer not started");
        }

        await _localPeer.ConnectAsync(multiaddress);
        _logger.LogInformation("Connected to peer: {Multiaddress}", multiaddress);
    }

    public async Task LeaveRoomAsync(string roomName)
    {
        if (_localPeer is null)
        {
            throw new InvalidOperationException("Local peer not started");
        }

        if (_topic is not null)
        {
            _topic.OnMessage -= OnMessageReceived;
            await _router.StopAsync();
            _topic = null;
            _logger.LogInformation("Left room: {RoomName}", roomName);
        }
    }

    public void Dispose()
    {
        StopAsync().GetAwaiter().GetResult();
    }
}
