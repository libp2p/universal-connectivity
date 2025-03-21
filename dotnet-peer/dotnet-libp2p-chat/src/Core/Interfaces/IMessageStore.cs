using Chat.Core.Models;

namespace Chat.Core.Interfaces;

public interface IMessageStore
{
    Task AddMessageAsync(string room, ChatMessage message);
    Task<IEnumerable<ChatMessage>> GetMessagesAsync(string room);
    Task<IEnumerable<string>> GetRoomsAsync();
    Task ClearRoomAsync(string room);
}