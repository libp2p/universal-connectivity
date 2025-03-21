using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols.Pubsub;
using Chat.Core.Models;

namespace Chat.Protocols;

public class UniversalPubSubHandler
{
    private readonly ILogger<UniversalPubSubHandler> _logger;
    private readonly PubsubRouter _router;
    private readonly string _localPeerId;
    private ITopic? _chatTopic;
    private ITopic? _fileTopic;
    private ITopic? _peerDiscoveryTopic;

    // Use the same topic names as in the js-peer's constants.ts
    private const string CHAT_TOPIC = "universal-connectivity";
    private const string CHAT_FILE_TOPIC = "universal-connectivity-file";
    private const string PUBSUB_PEER_DISCOVERY = "universal-connectivity-browser-peer-discovery";

    public UniversalPubSubHandler(
        ILogger<UniversalPubSubHandler> logger,
        PubsubRouter router,
        string localPeerId)
    {
        _logger = logger;
        _router = router;
        _localPeerId = localPeerId;
    }

    public async Task InitializeAsync(ILocalPeer peer, CancellationToken token = default)
    {
        // Start the PubSub router
        await _router.StartAsync(peer, token: token);
        
        // Subscribe to the main chat topic
        _chatTopic = _router.GetTopic(CHAT_TOPIC);
        _chatTopic.OnMessage += HandleChatMessage;
        _logger.LogInformation("Subscribed to chat topic: {Topic}", CHAT_TOPIC);
        
        // Subscribe to the file sharing topic
        _fileTopic = _router.GetTopic(CHAT_FILE_TOPIC);
        _fileTopic.OnMessage += HandleFileMessage;
        _logger.LogInformation("Subscribed to file topic: {Topic}", CHAT_FILE_TOPIC);
        
        // Subscribe to the peer discovery topic
        _peerDiscoveryTopic = _router.GetTopic(PUBSUB_PEER_DISCOVERY);
        _peerDiscoveryTopic.OnMessage += HandlePeerDiscoveryMessage;
        _logger.LogInformation("Subscribed to peer discovery topic: {Topic}", PUBSUB_PEER_DISCOVERY);

        // Announce ourselves on the peer discovery topic
        await AnnouncePresenceAsync();
    }
    
    private async Task AnnouncePresenceAsync()
    {
        if (_peerDiscoveryTopic == null) return;
        
        try
        {
            var announcement = new
            {
                PeerId = _localPeerId,
                Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                Type = "announce"
            };
            
            string json = JsonSerializer.Serialize(announcement);
            byte[] data = Encoding.UTF8.GetBytes(json);
            
            _peerDiscoveryTopic.Publish(data);
            _logger.LogInformation("Published peer announcement");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to announce presence");
        }
    }

    public async Task SendChatMessageAsync(string message, string nickname)
    {
        if (_chatTopic == null) return;
        
        try
        {
            var chatMessage = new ChatMessage(
                Guid.NewGuid().ToString(),
                message,
                _localPeerId,
                nickname ?? "dotnet-peer",
                DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            );
            
            string json = JsonSerializer.Serialize(chatMessage);
            byte[] data = Encoding.UTF8.GetBytes(json);
            
            _chatTopic.Publish(data);
            _logger.LogInformation("Published chat message: {Message}", message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send chat message");
        }
    }
    
    private void HandleChatMessage(byte[] data)
    {
        try
        {
            string message = Encoding.UTF8.GetString(data);
            _logger.LogDebug("Received chat message: {Message}", message);
            
            var chatMessage = JsonSerializer.Deserialize<ChatMessage>(message);
            
            // Skip our own messages
            if (chatMessage?.SenderId == _localPeerId)
                return;
                
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[PubSub] {chatMessage?.SenderNick ?? "Unknown"}: {chatMessage?.Message}");
            Console.ResetColor();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to handle chat message");
        }
    }
    
    private void HandleFileMessage(byte[] data)
    {
        try
        {
            string fileId = Encoding.UTF8.GetString(data);
            _logger.LogInformation("Received file announcement with ID: {FileId}", fileId);
            
            // In a full implementation, we would handle file sharing here
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"[File] File shared with ID: {fileId}");
            Console.ResetColor();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to handle file message");
        }
    }
    
    private void HandlePeerDiscoveryMessage(byte[] data)
    {
        try
        {
            string message = Encoding.UTF8.GetString(data);
            _logger.LogDebug("Received peer discovery message: {Message}", message);
            
            var discoveryMessage = JsonSerializer.Deserialize<DiscoveryMessage>(message);
            
            // Skip our own messages
            if (discoveryMessage?.PeerId == _localPeerId)
                return;
                
            _logger.LogInformation("Discovered peer: {PeerId}", discoveryMessage?.PeerId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to handle peer discovery message");
        }
    }
}

public record DiscoveryMessage(
    string PeerId,
    long Timestamp,
    string Type,
    string[]? Addresses = null); 