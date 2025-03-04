// using System.Collections.ObjectModel;
// using Microsoft.Extensions.Logging;
// using Multiformats.Address;
// using Nethermind.Libp2p.Core;
// using Chat.Core;

// namespace Chat.Services;

// public class PeerManager : IPeerManager
// {
//     private readonly ILocalPeer _localPeer;
//     private readonly ILogger<PeerManager> _logger;

//     public PeerManager(ILocalPeer localPeer, ILogger<PeerManager> logger)
//     {
//         _localPeer = localPeer;
//         _logger = logger;
//     }

//     public async Task StartAsync(CancellationToken token)
//     {
//         await _localPeer.StartListenAsync(["/ip4/0.0.0.0/tcp/0"], token);
//         _logger.LogInformation("Listening on {Addresses}", string.Join(", ", _localPeer.ListenAddresses));
//     }

//     public async Task StopAsync()
//     {
//         if (_listener != null)
//         {
//             await _listener.DisposeAsync();
//         }
//     }

//     public async Task<bool> ConnectToPeerAsync(string address, CancellationToken token)
//     {
//         try
//         {
//             var multiaddress = Multiaddress.Decode(address);
//             var remotePeer = await _localPeer.DialAsync(multiaddress);
//             await remotePeer.DialAsync<ChatProtocol>(token);
//             _logger.LogInformation("Connected to peer: {Address}", address);
//             return true;
//         }
//         catch (Exception ex)
//         {
//             _logger.LogError(ex, "Failed to connect to peer: {Address}", address);
//             return false;
//         }
//     }

//     public IEnumerable<string> GetListenAddresses()
//     {
//         return _listener?.Addresses.Select(a => a.ToString()) ?? Enumerable.Empty<string>();
//     }
// }