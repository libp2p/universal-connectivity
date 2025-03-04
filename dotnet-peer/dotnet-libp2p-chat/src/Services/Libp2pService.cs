using Chat.Core.Interfaces;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Chat.Core.Models;
using Nethermind.Libp2p.Core;
using System.Collections.Concurrent;
using Nethermind.Libp2p.Protocols;
using System.Collections.ObjectModel;
using Nethermind.Libp2p.Core.Discovery;
using Nethermind.Libp2p.Core.Utils;
using Nethermind.Libp2p.Core.Protocols;
using Nethermind.Libp2p.Core.Multiaddress;
using Nethermind.Libp2p.Core.Identity;
using Nethermind.Libp2p.Core.PeerRouting;
using System.Text;

public class SimplePeerDiscoveryProtocol : IDiscoveryProtocol
{
    private readonly ILogger<SimplePeerDiscoveryProtocol> _logger;
    private readonly ILocalPeer _peer;
    private readonly ConcurrentDictionary<string, List<Multiaddress>> _discoveredPeers;
    private readonly TimeSpan _discoveryInterval = TimeSpan.FromSeconds(30);
    private CancellationTokenSource? _cts;

    public event EventHandler<PeerEventArgs>? OnAddPeer;
    public event EventHandler<PeerEventArgs>? OnRemovePeer;

    public SimplePeerDiscoveryProtocol(ILocalPeer peer, ILogger<SimplePeerDiscoveryProtocol>? logger = null)
    {
        _peer = peer;
        _logger = logger ?? NullLogger<SimplePeerDiscoveryProtocol>.Instance;
        _discoveredPeers = new ConcurrentDictionary<string, List<Multiaddress>>();
    }

    public Task StartDiscoveryAsync(IReadOnlyList<Multiaddress> localPeerAddrs, CancellationToken token = default)
    {
        _cts = CancellationTokenSource.CreateLinkedTokenSource(token);
        _ = RunDiscoveryLoopAsync(_cts.Token);
        return Task.CompletedTask;
    }

    public async Task DiscoverAsync(Multiaddress multiaddr, CancellationToken token = default)
    {
        try
        {
            var peerId = multiaddr.GetPeerId();
            if (!_discoveredPeers.ContainsKey(peerId))
            {
                _discoveredPeers.TryAdd(peerId, new List<Multiaddress> { multiaddr });
                OnAddPeer?.Invoke(this, new PeerEventArgs(peerId));
                _logger.LogInformation("Discovered new peer: {PeerId}", peerId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error discovering peer from multiaddr {Multiaddr}", multiaddr);
        }
    }

    private async Task RunDiscoveryLoopAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            try
            {
                // In a real implementation, this would attempt to discover peers
                // through various means (DHT, mDNS, etc.)
                await Task.Delay(_discoveryInterval, token);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in discovery loop");
            }
        }
    }

    public void BanPeer()
    {
        // Not implementing ban functionality for basic discovery
    }

    public Task StopDiscoveryAsync(CancellationToken token = default)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = null;
        return Task.CompletedTask;
    }
}

public class Libp2pService : ILibp2pNode, IDisposable
{
    private readonly ILogger<Libp2pService> _logger;
    private readonly IMessageStore _messageStore;
    private readonly IServiceProvider _serviceProvider;
    private ILocalPeer? _localPeer;
    private readonly ConcurrentDictionary<string, IRemotePeer> _peers;
    private readonly ChatProtocol _chatProtocol;
    private SimplePeerDiscoveryProtocol? _peerDiscovery;

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
        var identity = Identity.Generate();
        _localPeer = factory.Create(identity);

        if (_localPeer == null)
        {
            throw new InvalidOperationException("Failed to create libp2p peer");
        }

        // Initialize peer discovery
        _peerDiscovery = new SimplePeerDiscoveryProtocol(_localPeer, _logger);
        _peerDiscovery.OnAddPeer += OnPeerDiscovered;

        // Start discovery with default local address
        var localAddr = new Multiaddress("/ip4/127.0.0.1/tcp/5001");
        await _peerDiscovery.StartDiscoveryAsync(new[] { localAddr }, cancellationToken);

        // Log the peer ID
        _logger.LogInformation("Peer ID: {PeerId}", _localPeer.Identity.PeerId);
        _logger.LogInformation("To connect to this peer, use: /ip4/127.0.0.1/tcp/5001/p2p/{PeerId}", _localPeer.Identity.PeerId);

        _logger.LogInformation("Libp2p node started");
    }

    private void OnPeerDiscovered(object? sender, PeerEventArgs e)
    {
        _logger.LogInformation("New peer discovered: {PeerId}", e.PeerId);
        // Here you could automatically connect to the discovered peer if desired
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Stopping libp2p node");

        if (_peerDiscovery != null)
        {
            await _peerDiscovery.StopDiscoveryAsync(cancellationToken);
        }

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
            var multiaddr = new Multiaddress(peerAddress);
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
    private static readonly ConsoleReader Reader = new();
    private readonly ConsoleColor _defaultConsoleColor = Console.ForegroundColor;
    
    public string Id => _protocolId;

    public async Task HandleAsync(IChannel channel, IPeerContext context)
    {
        Console.Write("> ");
        
        // Task for reading messages from the network
        _ = Task.Run(async () =>
        {
            try
            {
                while (true)
                {
                    var buffer = new byte[1024];
                    var sequence = await channel.ReadAsync(buffer.Length);
                    if (sequence.IsEmpty) break;
                    
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("{0}", Encoding.UTF8.GetString(sequence.ToArray())
                        .Replace("\r", "").Replace("\n\n", ""));
                    Console.ForegroundColor = _defaultConsoleColor;
                    Console.Write("> ");
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Connection closed: {0}", ex.Message);
                Console.ForegroundColor = _defaultConsoleColor;
            }
        });
        
        // Task for sending messages from console input
        try
        {
            for (;;)
            {
                string line = await Reader.ReadLineAsync();
                if (line == "exit")
                {
                    return;
                }
                
                Console.Write("> ");
                byte[] buf = Encoding.UTF8.GetBytes(line + "\n\n");
                await channel.WriteAsync(new ReadOnlySequence<byte>(buf));
            }
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("Error sending message: {0}", ex.Message);
            Console.ForegroundColor = _defaultConsoleColor;
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
