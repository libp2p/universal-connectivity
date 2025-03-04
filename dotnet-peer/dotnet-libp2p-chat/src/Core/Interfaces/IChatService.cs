using Chat.Core.Models;

namespace Chat.Core.Interfaces;

public interface IChatService
{
    IEnumerable<Room> GetAvailableRooms();
    Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName);
    Task SendMessageAsync(string roomName, ChatMessage message);
    event EventHandler<ChatMessage> MessageReceived;
}