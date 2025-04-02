using System.Text.Json.Serialization;

namespace Chat.Core.Models;

// This class can be used for strongly-typed serialization/deserialization
public record ChatMessage(
    [property: JsonPropertyName("msgId")] string MsgId,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("senderId")] string SenderId,
    [property: JsonPropertyName("senderNick")] string SenderNick,
    [property: JsonPropertyName("receivedAt")] long ReceivedAt = 0)
{
    // Constructor for backward compatibility
    public ChatMessage(string message, string senderNick, DateTimeOffset timestamp) 
        : this(Guid.NewGuid().ToString(), message, "dotnet-peer", senderNick, timestamp.ToUnixTimeMilliseconds())
    {
    }
}