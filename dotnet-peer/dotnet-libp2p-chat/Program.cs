using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;
using System.Text;
using System.Text.Json;
using Nethermind.Libp2p.Protocols.Pubsub;
using Nethermind.Libp2p.Protocols;
using System.Text.RegularExpressions;
using Nethermind.Libp2p;
using Chat.Protocols;
using Multiformats.Address;
using Multiformats.Address.Protocols;
using Chat.Core.Models;
using Chat.Core.Interfaces;
using Chat.Services;

// Filter out noisy logs
Regex omittedLogs = new(".*(MDnsDiscoveryProtocol|IpTcpProtocol).*");

// Set up services
var services = new ServiceCollection()
    .AddLibp2p(builder => builder
        .WithPubsub() // Enable PubSub for topic-based communication
        .AddAppLayerProtocol<Chat.ChatProtocol>()) // Add our custom protocol
    .AddLogging(builder =>
        builder.SetMinimumLevel(args.Contains("--trace") ? LogLevel.Trace : LogLevel.Information)
            .AddSimpleConsole(l =>
            {
                l.SingleLine = true;
                l.TimestampFormat = "[HH:mm:ss.fff]";
            }).AddFilter((_, type, lvl) => !omittedLogs.IsMatch(type!)))
    .AddSingleton<IMessageStore, InMemoryMessageStore>()
    .AddSingleton<ILibp2pNode, Libp2pService>()
    .BuildServiceProvider();

try
{
    var peerFactory = services.GetRequiredService<IPeerFactory>();
    var logger = services.GetRequiredService<ILoggerFactory>().CreateLogger("Chat");
    var ts = new CancellationTokenSource();
    var libp2pNode = services.GetRequiredService<ILibp2pNode>();

    // Handle Ctrl+C
    Console.CancelKeyPress += delegate { ts.Cancel(); };

    // Determine run mode based on arguments
    if (args.Length > 0)
    {
        // Dialing mode - connect to a specific peer
        if (args[0] == "-d" && args.Length > 1)
        {
            string peerAddress = args[1];
            await libp2pNode.StartAsync(ts.Token);
            await libp2pNode.ConnectToPeerAsync(peerAddress);

            // Chat loop
            Console.WriteLine("\n=== Connected to peer ===");
            Console.WriteLine("Type a message and press Enter to send");
            Console.WriteLine("Press Ctrl+C to exit");
            
            try
            {
                while (!ts.IsCancellationRequested)
                {
                    string? input = Console.ReadLine();
                    if (string.IsNullOrEmpty(input)) continue;
                    
                    await libp2pNode.BroadcastMessageAsync("public", input);
                }
            }
            catch (OperationCanceledException)
            {
                // Normal exit
            }
            
            await libp2pNode.StopAsync(ts.Token);
        }
        // Connect to the Go peer
        else if (args[0] == "-go")
        {
            string goAddr = args.Length > 1 
                ? args[1] 
                : "/ip4/127.0.0.1/tcp/5001"; // Default local go-peer address
            
            await libp2pNode.StartAsync(ts.Token);
            await libp2pNode.ConnectToPeerAsync(goAddr);

            // Chat loop
            Console.WriteLine("\n=== Connected to Go peer ===");
            Console.WriteLine("Type a message and press Enter to send");
            Console.WriteLine("Press Ctrl+C to exit");
            
            try
            {
                while (!ts.IsCancellationRequested)
                {
                    string? input = Console.ReadLine();
                    if (string.IsNullOrEmpty(input)) continue;
                    
                    await libp2pNode.BroadcastMessageAsync("public", input);
                }
            }
            catch (OperationCanceledException)
            {
                // Normal exit
            }
            
            await libp2pNode.StopAsync(ts.Token);
        }
        // Connect to the Rust peer
        else if (args[0] == "-rust")
        {
            string rustAddr = args.Length > 1 
                ? args[1] 
                : "/ip4/127.0.0.1/tcp/9090/p2p/QmYourRustPeerId"; // Default local rust-peer address
            
            await libp2pNode.StartAsync(ts.Token);
            await libp2pNode.ConnectToPeerAsync(rustAddr);

            // Chat loop
            Console.WriteLine("\n=== Connected to Rust peer ===");
            Console.WriteLine("Type a message and press Enter to send");
            Console.WriteLine("Press Ctrl+C to exit");
            
            try
            {
                while (!ts.IsCancellationRequested)
                {
                    string? input = Console.ReadLine();
                    if (string.IsNullOrEmpty(input)) continue;
                    
                    await libp2pNode.BroadcastMessageAsync("public", input);
                }
            }
            catch (OperationCanceledException)
            {
                // Normal exit
            }
            
            await libp2pNode.StopAsync(ts.Token);
        }
        else
        {
            // Server mode with specific options
            await libp2pNode.StartAsync(ts.Token);
            
            // Initialize and join the default room
            await libp2pNode.JoinRoomAsync("public");
            
            // Chat loop
            Console.WriteLine("\n=== Server started ===");
            Console.WriteLine("Type a message and press Enter to broadcast");
            Console.WriteLine("Press Ctrl+C to exit");
            
            try
            {
                while (!ts.IsCancellationRequested)
                {
                    string? input = Console.ReadLine();
                    if (string.IsNullOrEmpty(input)) continue;
                    
                    await libp2pNode.BroadcastMessageAsync("public", input);
                }
            }
            catch (OperationCanceledException)
            {
                // Normal exit
            }
            
            await libp2pNode.StopAsync(ts.Token);
        }
    }
    else
    {
        // Default server mode
        await libp2pNode.StartAsync(ts.Token);
        
        // Initialize and join the default room
        await libp2pNode.JoinRoomAsync("public");
        
        // Chat loop
        Console.WriteLine("\n=== Server started ===");
        Console.WriteLine("Type a message and press Enter to broadcast");
        Console.WriteLine("Press Ctrl+C to exit");
        
        try
        {
            while (!ts.IsCancellationRequested)
            {
                string? input = Console.ReadLine();
                if (string.IsNullOrEmpty(input)) continue;
                
                await libp2pNode.BroadcastMessageAsync("public", input);
            }
        }
        catch (OperationCanceledException)
        {
            // Normal exit
        }
        
        await libp2pNode.StopAsync(ts.Token);
    }
}
catch (Exception ex)
{
    var logger = services.GetRequiredService<ILogger<Program>>();
    logger.LogError(ex, "An error occurred while running the application.");
}
