namespace Chat.Core.Models;

internal record ChatMessage(string Message, string SenderId, string SenderNick, string RoomName = "default");