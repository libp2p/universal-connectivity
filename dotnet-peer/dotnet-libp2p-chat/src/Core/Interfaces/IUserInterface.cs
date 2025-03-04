using Chat.Core.Models;

namespace Chat.Core.Interfaces;

internal interface IUserInterface
{
    Task ShowMessageAsync(ChatMessage message);
    Task UpdateRoomListAsync(IEnumerable<Room> rooms);
}