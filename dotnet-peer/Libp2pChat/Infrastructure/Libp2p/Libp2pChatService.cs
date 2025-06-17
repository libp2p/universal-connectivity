using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using Libp2pChat.Application.Interfaces;
using Libp2pChat.Domain.Models;
using Multiformats.Address;
using Nethermind.Libp2p;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols.Pubsub;
using System.Net;
using System.Net.Sockets;
using Microsoft.Extensions.Logging;

namespace Libp2pChat.Infrastructure.Libp2p;

/// <summary>
/// Implementation of the chat service using libp2p.
/// </summary>
public class Libp2pChatService : IChatService, IDisposable
{
    private readonly ILogger<Libp2pChatService> _logger;
    private readonly IPeerFactory _peerFactory;
    private readonly PubsubRouter _router;
    private readonly Identity _identity;
    private readonly string _topicName;
    private readonly ConcurrentDictionary<string, Peer> _knownPeers = new();
    private ILocalPeer? _localPeer;
    private ITopic? _topic;
    private CancellationTokenSource? _cancellationTokenSource;
    private bool _isStarted;
    private bool _isDisposed;
    private readonly string _listenAddress;
    private readonly int _port;
    private int _actualPort;

    /// <inheritdoc />
    public string PeerId => _identity.PeerId.ToString();

    /// <inheritdoc />
    public event EventHandler<ChatMessage>? MessageReceived;

    /// <inheritdoc />
    public event EventHandler<Peer>? PeerDiscovered;

    /// <summary>
    /// Creates a new instance of the chat service.
    /// </summary>
    public Libp2pChatService(
        ILogger<Libp2pChatService> logger,
        IPeerFactory peerFactory,
        PubsubRouter router,
        string topicName = "universal-connectivity",
        Identity? identity = null,
        int port = 0
    )
    {
        _logger = logger;
        _peerFactory = peerFactory;
        _router = router;
        _topicName = topicName;
        _identity = identity ?? new Identity();
        _listenAddress = "0.0.0.0";
        _port = port;
        _actualPort = port;
    }

    /// <inheritdoc />
    public string GetMultiaddress()
    {
        return $"/ip4/{_listenAddress}/tcp/{_actualPort}/p2p/{PeerId}";
    }

    /// <inheritdoc />
    public IReadOnlyCollection<Peer> GetKnownPeers()
    {
        return _knownPeers.Values.ToList().AsReadOnly();
    }

    /// <inheritdoc />
    public async Task SendMessageAsync(string message)
    {
        if (!_isStarted)
            throw new InvalidOperationException("The chat service has not been started.");

        if (_topic == null)
            throw new InvalidOperationException("The chat topic is not available.");

        try
        {
            // Send as plain text for compatibility with other implementations
            byte[] data = Encoding.UTF8.GetBytes(message);
            _topic.Publish(data);

            _logger.LogDebug("Message sent: {Message}", message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send message");
            throw;
        }
    }

    /// <inheritdoc />
    public async Task StartAsync(CancellationToken cancellationToken)
    {
        if (_isStarted)
            return;

        _logger.LogInformation("Starting chat service...");
        _cancellationTokenSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

        try
        {
            _localPeer = _peerFactory.Create(_identity);

            if (_port == 0)
            {
                _actualPort = GetRandomAvailablePort();
                _logger.LogInformation("Using random port: {Port}", _actualPort);
            }
            else
            {
                _actualPort = _port;
            }

            // Create multiaddresses to listen on
            var allIfacesAddress = Multiaddress.Decode($"/ip4/{_listenAddress}/tcp/{_actualPort}/p2p/{PeerId}");

            // Start listening for peer connections
            _logger.LogInformation("Starting peer listener...");
            await _localPeer.StartListenAsync(new[] { allIfacesAddress }, _cancellationTokenSource.Token);
            _logger.LogInformation("Peer listener started successfully");
            _logger.LogInformation("Listening on: {Address}", allIfacesAddress);

            // Get topic and subscribe to messages
            _topic = _router.GetTopic(_topicName);
            _topic.OnMessage += HandleMessageReceived;

            // Start router
            _logger.LogInformation("Starting pubsub router...");
            await _router.StartAsync(_localPeer, _cancellationTokenSource.Token);
            _logger.LogInformation("Pubsub router started successfully");

            // Start cleanup task
            _ = Task.Run(RunPeerCleanupTask, _cancellationTokenSource.Token);

            _isStarted = true;

            _logger.LogInformation("Chat service started successfully");
            _logger.LogInformation("Peer ID: {PeerId}", PeerId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start chat service");
            await StopAsync();
            throw;
        }
    }

    /// <summary>
    /// Gets a random available port.
    /// </summary>
    private int GetRandomAvailablePort()
    {
        using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        socket.Bind(new IPEndPoint(IPAddress.Any, 0));
        var endPoint = (IPEndPoint)socket.LocalEndPoint!;
        return endPoint.Port;
    }

    /// <inheritdoc />
    public async Task StopAsync()
    {
        if (!_isStarted)
            return;

        _logger.LogInformation("Stopping chat service...");

        try
        {
            if (_topic != null)
            {
                _topic.OnMessage -= HandleMessageReceived;
            }

            if (_cancellationTokenSource != null)
            {
                if (!_cancellationTokenSource.IsCancellationRequested)
                    _cancellationTokenSource.Cancel();

                _cancellationTokenSource.Dispose();
                _cancellationTokenSource = null;
            }

            _isStarted = false;
            _logger.LogInformation("Chat service stopped");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error while stopping chat service");
            throw;
        }
    }

    /// <inheritdoc />
    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    /// <summary>
    /// Disposes resources.
    /// </summary>
    protected virtual void Dispose(bool disposing)
    {
        if (_isDisposed)
            return;

        if (disposing)
        {
            _cancellationTokenSource?.Dispose();
        }

        _isDisposed = true;
    }

    private void HandleMessageReceived(byte[] data)
    {
        try
        {
            if (data == null || data.Length == 0)
            {
                _logger.LogWarning("Received empty message data");
                return;
            }

            string raw = Encoding.UTF8.GetString(data).Trim();
            _logger.LogDebug("Raw message received: {Message}", raw);

            // Check if the message is JSON or plain text
            bool isJsonMessage = raw.StartsWith("{");
            if (isJsonMessage)
            {
                try
                {
                    // Try to deserialize as a ChatMessage
                    var chatMessage = JsonSerializer.Deserialize<ChatMessage>(raw);
                    if (chatMessage != null && !string.IsNullOrEmpty(chatMessage.Message))
                    {
                        // Don't process messages from ourselves
                        if (chatMessage.SenderID == PeerId)
                            return;

                        // Track peer
                        UpdateOrAddPeer(chatMessage.SenderID, chatMessage.SenderNick);

                        // Raise event
                        MessageReceived?.Invoke(this, chatMessage);
                    }
                    else
                    {
                        _logger.LogWarning("Received invalid JSON message structure: {Message}", raw);
                    }
                }
                catch (JsonException ex)
                {
                    _logger.LogError(ex, "JSON parsing error: {Message}", ex.Message);

                    var plainTextMessage = new ChatMessage(raw, "unknown", "peer");
                    MessageReceived?.Invoke(this, plainTextMessage);
                }
            }
            else
            {
                var plainTextMessage = new ChatMessage(raw, "unknown", "peer");
                MessageReceived?.Invoke(this, plainTextMessage);
                _logger.LogInformation("Received plain text message from peer");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling message");
        }
    }

    private void UpdateOrAddPeer(string peerId, string nickname)
    {
        if (string.IsNullOrEmpty(peerId))
            return;

        if (_knownPeers.TryGetValue(peerId, out var existingPeer))
        {
            existingPeer.UpdateLastSeen();

            if (!string.IsNullOrEmpty(nickname) && existingPeer.DisplayName != nickname)
            {
                existingPeer.DisplayName = nickname;
            }
        }
        else
        {
            var newPeer = new Peer(peerId, string.IsNullOrEmpty(nickname) ? "unknown" : nickname);
            if (_knownPeers.TryAdd(peerId, newPeer))
            {
                PeerDiscovered?.Invoke(this, newPeer);
                _logger.LogInformation("New peer discovered: {PeerId} ({DisplayName})", peerId, newPeer.DisplayName);
            }
        }
    }

    private async Task RunPeerCleanupTask()
    {
        try
        {
            while (!_cancellationTokenSource!.Token.IsCancellationRequested)
            {
                try
                {
                    _logger.LogDebug("Known peers: {Count}", _knownPeers.Count);

                    // Clean up inactive peers (not seen in last 5 minutes)
                    DateTime cutoff = DateTime.UtcNow.AddMinutes(-5);
                    foreach (var (peerId, peer) in _knownPeers)
                    {
                        if (peer.LastSeen < cutoff)
                        {
                            if (_knownPeers.TryRemove(peerId, out _))
                            {
                                _logger.LogInformation("Removed inactive peer: {PeerId}", peerId);
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in peer cleanup task");
                }

                // Check every 30 seconds
                await Task.Delay(TimeSpan.FromSeconds(30), _cancellationTokenSource.Token);
            }
        }
        catch (OperationCanceledException)
        {
            // Expected when token is canceled
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Peer cleanup task failed");
        }
    }
}