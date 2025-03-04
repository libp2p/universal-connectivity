using Chat.Core.Models;

namespace Chat.Core.Interfaces;

public interface IMessageStore
{
    Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName);
    Task AddMessageAsync(string roomName, ChatMessage message);
}