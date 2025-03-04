using Chat.Core.Models;

namespace Chat.Core.Interfaces;

public interface IUserInterface
{
    Task ShowMessageAsync(ChatMessage message);
    Task UpdateRoomListAsync(IEnumerable<Room> rooms);
    Task RunAsync(CancellationToken token);
}