using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Chat.Core.Interfaces;
using Chat.Services;
using System;
using System.Threading;
using System.Threading.Tasks;
using Nethermind.Libp2p.Protocols.Pubsub;
using System.Text.RegularExpressions;

namespace Chat;

public class Program
{
    public static async Task Main(string[] args)
    {
        Regex omittedLogs = new(".*(MDnsDiscoveryProtocol|IpTcpProtocol).*");

        ServiceProvider serviceProvider = new ServiceCollection()
            .AddLibp2p(builder => builder.WithPubsub())
            .AddLogging(builder =>
                builder.SetMinimumLevel(args.Contains("--trace") ? LogLevel.Trace : LogLevel.Information)
                    .AddSimpleConsole(l =>
                    {
                        l.SingleLine = true;
                        l.TimestampFormat = "[HH:mm:ss.fff]";
                    }).AddFilter((_, type, lvl) => !omittedLogs.IsMatch(type!)))
            .AddSingleton<ILibp2pNode, Libp2pService>()
            .BuildServiceProvider();

        ILogger logger = serviceProvider.GetService<ILoggerFactory>()!.CreateLogger("Pubsub Chat");
        CancellationTokenSource ts = new();

        ILibp2pNode node = serviceProvider.GetService<ILibp2pNode>()!;
        node.MessageReceived += (_, msg) => Console.WriteLine($"Received: {msg}");

        await node.StartAsync(ts.Token);

        string nickName = "libp2p-dotnet";

        while (true)
        {
            string? msg = Console.ReadLine();

            if (string.IsNullOrWhiteSpace(msg))
            {
                continue;
            }

            if (msg.StartsWith("/connect "))
            {
                string multiaddress = msg["/connect ".Length..];
                await node.ConnectAsync(multiaddress);
            }
            else if (msg.StartsWith("/join "))
            {
                string roomName = msg["/join ".Length..];
                await node.JoinRoomAsync(roomName);
            }
            else if (msg == "/exit")
            {
                break;
            }
            else
            {
                await node.SendMessageAsync($"{nickName}: {msg}");
            }
        }

        ts.Cancel();
    }

    public static IHostBuilder CreateHostBuilder(string[] args) =>
        Host.CreateDefaultBuilder(args)
            .ConfigureServices((hostContext, services) =>
            {
                // Register services
                services.AddSingleton<IMessageStore, InMemoryMessageStore>();
                services.AddSingleton<IPeerFactory, DefaultPeerFactory>();
                services.AddSingleton<ILibp2pNode, Libp2pService>();
                services.AddHostedService<ChatHostedService>();
            })
            .ConfigureLogging(logging =>
            {
                logging.ClearProviders();
                logging.AddConsole();
                logging.SetMinimumLevel(LogLevel.Information);
            });
}

public class ChatHostedService : IHostedService
{
    private readonly ILogger<ChatHostedService> _logger;
    private readonly ILibp2pNode _libp2pNode;

    public ChatHostedService(
        ILogger<ChatHostedService> logger,
        ILibp2pNode libp2pNode)
    {
        _logger = logger;
        _libp2pNode = libp2pNode;
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Starting chat application");
        
        // Start the libp2p node
        await _libp2pNode.StartAsync(cancellationToken);
        
        // Join the default chat room
        await _libp2pNode.JoinRoomAsync("general");
        
        // Start the console input loop in a background task
        _ = Task.Run(() => RunConsoleLoopAsync(cancellationToken), cancellationToken);
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Stopping chat application");
        
        // Stop the libp2p node
        await _libp2pNode.StopAsync(cancellationToken);
    }

    private async Task RunConsoleLoopAsync(CancellationToken cancellationToken)
    {
        Console.WriteLine("Welcome to the .NET libp2p chat application!");
        Console.WriteLine("Type '/connect <multiaddress>' to connect to a peer");
        Console.WriteLine("Type '/exit' to quit");
        Console.WriteLine();

        var currentRoom = "general";
        Console.WriteLine($"Current room: {currentRoom}");

        while (!cancellationToken.IsCancellationRequested)
        {
            Console.Write("> ");
            var input = Console.ReadLine();
            
            if (string.IsNullOrEmpty(input))
                continue;

            if (input.StartsWith("/"))
            {
                var parts = input.Split(' ', 2);
                var command = parts[0].ToLowerInvariant();
                
                switch (command)
                {
                    case "/exit":
                        Environment.Exit(0);
                        break;
                    
                    case "/connect":
                        if (parts.Length < 2)
                        {
                            Console.WriteLine("Usage: /connect <multiaddress>");
                        }
                        else
                        {
                            try
                            {
                                await _libp2pNode.ConnectToPeerAsync(parts[1]);
                                Console.WriteLine($"Connected to peer: {parts[1]}");
                            }
                            catch (Exception ex)
                            {
                                Console.WriteLine($"Failed to connect: {ex.Message}");
                            }
                        }
                        break;

                    case "/join":
                        if (parts.Length < 2)
                        {
                            Console.WriteLine("Usage: /join <room>");
                        }
                        else
                        {
                            await _libp2pNode.LeaveRoomAsync(currentRoom);
                            currentRoom = parts[1];
                            await _libp2pNode.JoinRoomAsync(currentRoom);
                            Console.WriteLine($"Joined room: {currentRoom}");
                        }
                        break;
                    
                    default:
                        Console.WriteLine($"Unknown command: {command}");
                        break;
                }
            }
            else
            {
                // Broadcast the message to the current room
                await _libp2pNode.BroadcastMessageAsync(currentRoom, input);
            }
        }
    }
} 