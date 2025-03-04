using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;
using System.Text;
using System.Text.Json;
using Nethermind.Libp2p.Protocols.Pubsub;
using Nethermind.Libp2p.Protocols;
using System.Text.RegularExpressions;
using Nethermind.Libp2p;
using Chat.Core.Interfaces;
using Chat.Services;
using Chat.UI;
using Chat.UI.Themes;
using Nethermind.Libp2p.Core.Identity;
using Multiformats.Address;
using Multiformats.Address.Protocols;

var omittedLogs = new Regex(".*(MDnsDiscoveryProtocol|IpTcpProtocol).*");

var services = new ServiceCollection()
    .AddLibp2p(builder => builder.WithPubsub().AddAppLayerProtocol<ChatProtocol>())
    .AddLogging(builder =>
        builder.SetMinimumLevel(args.Contains("--trace") ? LogLevel.Trace : LogLevel.Information)
            .AddSimpleConsole(l =>
            {
                l.SingleLine = true;
                l.TimestampFormat = "[HH:mm:ss.fff]";
            }).AddFilter((_, type, lvl) => !omittedLogs.IsMatch(type!)))
    .AddSingleton<IMessageStore, InMemoryMessageStore>()
    .AddSingleton<IChatService, ChatService>()
    .AddSingleton<ITheme, DefaultTheme>()
    .BuildServiceProvider();

try
{
    var peerFactory = services.GetRequiredService<IPeerFactory>();
    var logger = services.GetRequiredService<ILoggerFactory>().CreateLogger("Chat");
    var ts = new CancellationTokenSource();

    // Handle Ctrl+C
    Console.CancelKeyPress += delegate { ts.Cancel(); };

    if (args.Length > 0 && args[0] == "-d")
    {
        // Client mode - dial a remote peer
        Multiaddress remoteAddr = new(args[1]);

        string addrTemplate = remoteAddr.Has<QUICv1>() ?
           "/ip4/0.0.0.0/udp/0/quic-v1" :
           "/ip4/0.0.0.0/tcp/0";

        var localPeer = peerFactory.Create();

        logger.LogInformation("Dialing {remote}", remoteAddr);
        var remotePeer = await localPeer.DialAsync(remoteAddr, ts.Token);

        await remotePeer.DialAsync<ChatProtocol>(ts.Token);
        
        // Keep the connection open until canceled
        await Task.Delay(-1, ts.Token);
        
        await remotePeer.DisconnectAsync();
    }
    else
    {
        // Server mode - listen for connections
        // Use fixed identity for testing (optional)
        Identity optionalFixedIdentity = new(Enumerable.Repeat((byte)42, 32).ToArray());
        var peer = peerFactory.Create(optionalFixedIdentity);

        // Choose transport based on arguments
        string addrTemplate = args.Contains("-quic") ?
            "/ip4/0.0.0.0/udp/{0}/quic-v1" :
            "/ip4/0.0.0.0/tcp/{0}";

        // Set port if specified
        string port = args.Length > 0 && args[0] == "-sp" ? args[1] : "0";
        
        // Log when peers connect
        peer.OnConnected += async newSession => 
            logger.LogInformation("A peer connected {remote}", newSession.RemoteAddress);

        // Start listening
        await peer.StartListenAsync(
            [string.Format(addrTemplate, port)],
            ts.Token);
        
        logger.LogInformation("Listener started at {address}", string.Join(", ", peer.ListenAddresses));

        // Set up PubSub if needed
        var router = services.GetRequiredService<PubsubRouter>();
        var topic = router.GetTopic("chat-room:awesome-chat-room");
        topic.OnMessage += (byte[] msg) =>
        {
            try
            {
                var chatMessage = JsonSerializer.Deserialize<ChatMessage>(Encoding.UTF8.GetString(msg));

                if (chatMessage is not null)
                {
                    Console.WriteLine("{0}: {1}", chatMessage.SenderNick, chatMessage.Message);
                }
            }
            catch
            {
                Console.Error.WriteLine("Unable to decode chat message");
            }
        };

        // Start mDNS discovery
        _ = services.GetRequiredService<MDnsDiscoveryProtocol>()
            .StartDiscoveryAsync(peer.ListenAddresses, token: ts.Token);

        await router.StartAsync(peer, token: ts.Token);

        // If UI is needed, use it
        if (!args.Contains("--no-ui"))
        {
            var ui = new ConsoleUI(
                services.GetRequiredService<ILogger<ConsoleUI>>(),
                services.GetRequiredService<ITheme>(),
                services.GetRequiredService<IChatService>(),
                router,
                peer.Identity.PeerId.ToString());

            await ui.RunAsync(ts.Token);
        }
        else
        {
            // Otherwise just wait until canceled
            await Task.Delay(-1, ts.Token);
        }

        await peer.DisconnectAsync();
    }
}
catch (Exception ex)
{
    var logger = services.GetRequiredService<ILogger<Program>>();
    logger.LogError(ex, "An error occurred while running the application.");
}

record ChatMessage(string Message, string SenderId, string SenderNick);
