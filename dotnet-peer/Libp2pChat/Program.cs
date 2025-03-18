using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Nethermind.Libp2p.Protocols.Pubsub;
using System.Text.RegularExpressions;
using Nethermind.Libp2p;
using Multiformats.Address;

Regex omittedLogs = new(".*(IpTcpProtocol).*");

ServiceProvider serviceProvider = new ServiceCollection()
    .AddLibp2p(builder => builder.WithPubsub())
    .AddLogging(builder =>
        builder.SetMinimumLevel(args.Contains("--trace") ? LogLevel.Trace : LogLevel.Information)
            .AddSimpleConsole(l =>
            {
                l.SingleLine = true;
                l.TimestampFormat = "[HH:mm:ss.fff]";
            }).AddFilter((_, type, lvl) => !omittedLogs.IsMatch(type!)))
    .BuildServiceProvider();

IPeerFactory peerFactory = serviceProvider.GetService<IPeerFactory>()!;
ILogger logger = serviceProvider.GetService<ILoggerFactory>()!.CreateLogger("Pubsub Chat");
CancellationTokenSource ts = new();

Identity localPeerIdentity = new();
string addrString = $"/ip4/0.0.0.0/tcp/0/p2p/{localPeerIdentity.PeerId}";
Multiaddress addr = Multiaddress.Decode(addrString);

ILocalPeer peer = peerFactory.Create(localPeerIdentity);

PubsubRouter router = serviceProvider.GetService<PubsubRouter>()!;
ITopic topic = router.GetTopic("universal-connectivity");
topic.OnMessage += (byte[] msg) =>
{
    try
    {
        // Debug the raw message
        string rawMessage = Encoding.UTF8.GetString(msg);
        Console.WriteLine($"Raw message received: {rawMessage}");
        
        // Try to deserialize
        ChatMessage? chatMessage = JsonSerializer.Deserialize<ChatMessage>(rawMessage);

        if (chatMessage is not null)
        {
            Console.WriteLine("{0}: {1}", chatMessage.SenderNick, chatMessage.Message);
        }
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Unable to decode chat message: {ex.Message}");
    }
};

await peer.StartListenAsync(new[] { addr }, ts.Token);
await router.StartAsync(peer, ts.Token);

// Display actual listening addresses after startup
Console.WriteLine("Peer started with ID: {0}", localPeerIdentity.PeerId);
Console.WriteLine("Listening on:");
foreach (var listenAddr in peer.ListenAddresses)
{
    Console.WriteLine("  {0}", listenAddr);
}
Console.WriteLine("Share these addresses with other peers to connect");
Console.WriteLine("Chat room: universal-connectivity");

string nickName = "libp2p-dotnet";

while (true)
{
    string? msg = Console.ReadLine();

    if (string.IsNullOrWhiteSpace(msg))
    {
        continue;
    }

    if (msg == "exit")
    {
        break;
    }

    // Create chat message
    var chatMessage = new ChatMessage
    {
        Message = msg,
        SenderID = peer.Identity.PeerId.ToString(),
        SenderNick = nickName
    };

    // Serialize to JSON
    string jsonMessage = JsonSerializer.Serialize(chatMessage);
    Console.WriteLine($"Sending message: {jsonMessage}");
    
    // Publish raw message as string (like Go does)
    topic.Publish(Encoding.UTF8.GetBytes(jsonMessage));
}

ts.Cancel();

// Updated to match Go peer's field names exactly
public class ChatMessage
{
    [JsonPropertyName("Message")]
    public string Message { get; set; } = string.Empty;
    
    [JsonPropertyName("SenderID")]
    public string SenderID { get; set; } = string.Empty;
    
    [JsonPropertyName("SenderNick")]
    public string SenderNick { get; set; } = string.Empty;
}
