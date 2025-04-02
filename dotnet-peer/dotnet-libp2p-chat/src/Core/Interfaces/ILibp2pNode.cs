using Nethermind.Libp2p.Core;

namespace Chat.Core.Interfaces;

public interface ILibp2pNode
{
    Task StartAsync(CancellationToken cancellationToken = default);
    Task StopAsync();
    Task ConnectAsync(string multiaddress);
    Task JoinRoomAsync(string roomName);
    Task SendMessageAsync(string message);
    event EventHandler<string> MessageReceived;
}
