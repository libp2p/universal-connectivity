using System.Text.Json.Serialization;

namespace Libp2pChat.Domain.Models;

/// <summary>
/// Represents a chat message exchanged between peers.
/// </summary>
public class ChatMessage
{
    /// <summary>
    /// The content of the message.
    /// </summary>
    [JsonPropertyName("Message")]
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// The unique identifier of the sender.
    /// </summary>
    [JsonPropertyName("SenderID")]
    public string SenderID { get; set; } = string.Empty;

    /// <summary>
    /// The nickname of the sender.
    /// </summary>
    [JsonPropertyName("SenderNick")]
    public string SenderNick { get; set; } = string.Empty;
    
    /// <summary>
    /// The timestamp when the message was created.
    /// </summary>
    [JsonIgnore]
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// Creates a new instance of the <see cref="ChatMessage"/> class.
    /// </summary>
    public ChatMessage() { }
    
    /// <summary>
    /// Creates a new instance of the <see cref="ChatMessage"/> class with specified properties.
    /// </summary>
    public ChatMessage(string message, string senderId, string senderNick)
    {
        Message = message;
        SenderID = senderId;
        SenderNick = senderNick;
    }
    
    /// <summary>
    /// Creates a system message.
    /// </summary>
    public static ChatMessage CreateSystemMessage(string message)
    {
        return new ChatMessage(message, "system", "system");
    }
} 