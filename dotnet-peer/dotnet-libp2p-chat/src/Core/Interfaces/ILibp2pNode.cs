public interface ILibp2pNode
{
    Task StartAsync(CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
    Task BroadcastMessageAsync(string room, string message);
    Task JoinRoomAsync(string room);
    Task LeaveRoomAsync(string room);
}
