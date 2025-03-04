using Chat.Core.Models;

namespace Chat.Core.Interfaces;

internal interface IChatService
{
    IEnumerable<Room> GetAvailableRooms();
    Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName);
    Task SendMessageAsync(string roomName, ChatMessage message);
    event EventHandler<ChatMessage> MessageReceived;
    Task JoinRoomAsync(string room);
    Task LeaveRoomAsync(string room);
    Task ConnectToPeerAsync(string peerAddress);
}