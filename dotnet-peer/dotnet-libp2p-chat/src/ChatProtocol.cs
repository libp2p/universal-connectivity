using System;
using System.Text;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols;
using Chat.Core.Models;
using System.IO.Pipelines;

namespace Chat;

/// <summary>
/// Implementation of a simple chat protocol over libp2p
/// </summary>
public class ChatProtocol : IProtocol
{
    private readonly ILogger<ChatProtocol> _logger;
    private const string PROTOCOL_ID = "/chat/1.0.0";

    /// <summary>
    /// Gets the protocol identifier
    /// </summary>
    public string Id => PROTOCOL_ID;

    /// <summary>
    /// Initializes a new instance of the <see cref="ChatProtocol"/> class
    /// </summary>
    /// <param name="logger">The logger instance</param>
    public ChatProtocol(ILogger<ChatProtocol> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Handles an incoming message stream from a remote peer
    /// </summary>
    /// <param name="stream">The duplex stream to handle</param>
    /// <param name="cancellationToken">A token to monitor for cancellation requests</param>


    public string Name => "chat/1.0.0";

    public Task OnConnectedAsync(ISession session)
    {
        _logger.LogInformation("New peer connected: {PeerId}", session.RemotePeer.PeerId);
        
        // The actual message handling will be done through PubSub
        // This method just logs the connection
        return Task.CompletedTask;
    }
}

// Compatible with the message format used by the other peers
public record ChatMessage(
    string MsgId,
    string Message,
    string SenderId,
    string SenderNick,
    long ReceivedAt = 0)
{
    public ChatMessage(string msgId, string message, string senderId, string senderNick)
        : this(msgId, message, senderId, senderNick, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())
    {
    }
}