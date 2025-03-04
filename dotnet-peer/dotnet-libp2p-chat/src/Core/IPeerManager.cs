using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace Chat.Core;

public interface IPeerManager
{
    Task StartAsync(CancellationToken token);
    Task StopAsync();
    Task<bool> ConnectToPeerAsync(string multiaddr, CancellationToken token);
    IEnumerable<string> GetListenAddresses();
}