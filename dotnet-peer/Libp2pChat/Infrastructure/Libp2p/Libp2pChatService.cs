using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using Libp2pChat.Application.Interfaces;
using Libp2pChat.Domain.Models;
using Multiformats.Address;
using Nethermind.Libp2p;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols.Pubsub;

namespace Libp2pChat.Infrastructure.Libp2p;

/// <summary>
/// Implementation of the chat service using libp2p.
/// </summary>
public class Libp2pChatService : IChatService, IDisposable
{
    private readonly IAppLogger _logger;
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
    
    /// <inheritdoc />
    public string PeerId => _identity.PeerId.ToString();
    
    /// <inheritdoc />
    public event EventHandler<ChatMessage>? MessageReceived;
    
    /// <inheritdoc />
    public event EventHandler<Peer>? PeerDiscovered;
    
    /// <summary>
    /// Creates a new instance of the <see cref="Libp2pChatService"/> class.
    /// </summary>
    /// <param name="logger">The application logger.</param>
    /// <param name="peerFactory">The peer factory.</param>
    /// <param name="router">The pubsub router.</param>
    /// <param name="topicName">The topic name to use for chat messages.</param>
    /// <param name="identity">The identity to use. If null, a new identity will be generated.</param>
    public Libp2pChatService(
        IAppLogger logger,
        IPeerFactory peerFactory,
        PubsubRouter router,
        string topicName = "universal-connectivity",
        Identity? identity = null)
    {
        _logger = logger;
        _peerFactory = peerFactory;
        _router = router;
        _topicName = topicName;
        _identity = identity ?? new Identity();
        _listenAddress = "0.0.0.0";
    }
    
    /// <inheritdoc />
    public string GetMultiaddress()
    {
        return $"/ip4/{_listenAddress}/tcp/9096/p2p/{PeerId}";
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
            
            _logger.LogDebug($"Message sent: {message}");
        }
        catch (Exception ex)
        {
            _logger.LogError("Failed to send message", ex);
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
            // Create local peer
            _localPeer = _peerFactory.Create(_identity);
            
            // Create multiaddresses to listen on
            var localAddress = Multiaddress.Decode($"/ip4/127.0.0.1/tcp/9096/p2p/{PeerId}");
            var allIfacesAddress = Multiaddress.Decode($"/ip4/{_listenAddress}/tcp/9096/p2p/{PeerId}");
            
            // Start listening for peer connections
            _logger.LogInformation("Starting peer listener...");
            await _localPeer.StartListenAsync(new[] { localAddress, allIfacesAddress }, _cancellationTokenSource.Token);
            _logger.LogInformation("Peer listener started successfully");
            _logger.LogInformation($"Listening on: {localAddress}");
            _logger.LogInformation($"Listening on: {allIfacesAddress}");
            
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
            _logger.LogInformation($"Peer ID: {PeerId}");
            _logger.LogInformation($"GO PEER CONNECTION COMMAND:");
            _logger.LogInformation($"./go-peer --connect /ip4/127.0.0.1/tcp/9096/p2p/{PeerId}");
        }
        catch (Exception ex)
        {
            _logger.LogError("Failed to start chat service", ex);
            await StopAsync();
            throw;
        }
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
            _logger.LogError("Error while stopping chat service", ex);
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
    /// <param name="disposing">Whether to dispose managed resources.</param>
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
            _logger.LogDebug($"Raw message received: {raw}");
            
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
                        _logger.LogWarning($"Received invalid JSON message structure: {raw}");
                    }
                }
                catch (JsonException ex)
                {
                    _logger.LogError($"JSON parsing error: {ex.Message}");
                    
                    // Treat as plain text
                    var plainTextMessage = new ChatMessage(raw, "unknown", "peer");
                    MessageReceived?.Invoke(this, plainTextMessage);
                }
            }
            else
            {
                // Plain text message (likely from Go peer)
                var plainTextMessage = new ChatMessage(raw, "unknown", "peer");
                
                // Add Go peer to known peers
                var goPeer = Peer.CreateGoPeer();
                _knownPeers.TryAdd(goPeer.Id, goPeer);
                PeerDiscovered?.Invoke(this, goPeer);
                
                MessageReceived?.Invoke(this, plainTextMessage);
                _logger.LogInformation("Detected Go peer from message");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError("Error handling message", ex);
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
                _logger.LogInformation($"New peer discovered: {peerId} ({newPeer.DisplayName})");
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
                    _logger.LogDebug($"Known peers: {_knownPeers.Count}");
                    
                    // Clean up inactive peers (not seen in last 5 minutes)
                    DateTime cutoff = DateTime.UtcNow.AddMinutes(-5);
                    foreach (var (peerId, peer) in _knownPeers)
                    {
                        if (peer.LastSeen < cutoff)
                        {
                            if (_knownPeers.TryRemove(peerId, out _))
                            {
                                _logger.LogInformation($"Removed inactive peer: {peerId}");
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError("Error in peer cleanup task", ex);
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
            _logger.LogError("Peer cleanup task failed", ex);
        }
    }
} 