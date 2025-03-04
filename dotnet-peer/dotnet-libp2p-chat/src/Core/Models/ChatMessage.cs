namespace Chat.Core.Models;

public record ChatMessage(string Username, string Content, DateTimeOffset Timestamp);