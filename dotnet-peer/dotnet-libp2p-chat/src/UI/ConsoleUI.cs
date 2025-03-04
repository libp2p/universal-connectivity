using System.Text;
using Chat.Core.Interfaces;
using Chat.Core.Models;
using Chat.UI.Themes;
using Microsoft.Extensions.Logging;
using System.Text.Json;
using Nethermind.Libp2p.Protocols.Pubsub;

namespace Chat.UI;

internal class ConsoleUI : IUserInterface
{
    private readonly ILogger<ConsoleUI> _logger;
    private readonly ITheme _theme;
    private readonly IChatService _chatService;
    private readonly PubsubRouter _router;
    private readonly ITopic _topic;
    private readonly string _peerId;
    private readonly string _nickName;

    public ConsoleUI(
        ILogger<ConsoleUI> logger,
        ITheme theme,
        IChatService chatService,
        PubsubRouter router,
        string peerId)
    {
        _logger = logger;
        _theme = theme;
        _chatService = chatService;
        _router = router;
        _topic = router.GetTopic("chat-room:awesome-chat-room");
        _peerId = peerId;
        _nickName = "libp2p-dotnet";
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        _theme.WriteWelcomeMessage();
        _theme.WriteHelpMessage();

        while (!cancellationToken.IsCancellationRequested)
        {
            Console.Write("default> ");
            var input = await Console.In.ReadLineAsync(cancellationToken);

            if (string.IsNullOrWhiteSpace(input))
            {
                continue;
            }

            if (input == "exit")
            {
                break;
            }

            if (input.StartsWith("/"))
            {
                await HandleCommand(input);
            }
            else
            {
                var message = new ChatMessage(input, _peerId, _nickName);
                var json = JsonSerializer.Serialize(message);
                _topic.Publish(Encoding.UTF8.GetBytes(json));
            }
        }
    }

    private async Task HandleCommand(string command)
    {
        var parts = command.Split(' ');
        var cmd = parts[0].ToLower();

        try
        {
            switch (cmd)
            {
                case "/help":
                    _theme.WriteHelpMessage();
                    break;
                case "/join":
                    if (parts.Length < 2)
                    {
                        _theme.WriteError("Usage: /join <room>");
                        break;
                    }
                    await _chatService.JoinRoomAsync(parts[1]);
                    break;
                case "/leave":
                    if (parts.Length < 2)
                    {
                        _theme.WriteError("Usage: /leave <room>");
                        break;
                    }
                    await _chatService.LeaveRoomAsync(parts[1]);
                    break;
                case "/connect":
                    if (parts.Length < 2)
                    {
                        _theme.WriteError("Usage: /connect <peer-address>");
                        break;
                    }
                    await _chatService.ConnectToPeerAsync(parts[1]);
                    break;
                default:
                    _theme.WriteError($"Unknown command: {cmd}");
                    break;
            }
        }
        catch (Exception ex)
        {
            _theme.WriteError($"Error executing command: {ex.Message}");
            _logger.LogError(ex, "Error executing command {Command}", command);
        }
    }

    public Task UpdateRoomListAsync(IEnumerable<Room> rooms)
    {
        Console.WriteLine(_theme.FormatRoomList(rooms.Select(r => r.Name)));
        return Task.CompletedTask;
    }

    public Task ShowMessageAsync(ChatMessage message)
    {
        Console.WriteLine(_theme.FormatMessage(message.SenderNick, message.Message));
        return Task.CompletedTask;
    }
}

// using System;
// using System.Threading;
// using System.Threading.Tasks;
// using Microsoft.Extensions.Logging;
// using Chat.Core;

// namespace Chat.UI;

// public class ConsoleUI : IUserInterface
// {
//     private readonly IChatRoom _chatRoom;
//     private readonly ILogger<ConsoleUI> _logger;
//     private readonly CancellationTokenSource _cts = new();

//     public ConsoleUI(IChatRoom chatRoom, ILogger<ConsoleUI> logger)
//     {
//         _chatRoom = chatRoom;
//         _logger = logger;
//     }

//     public async Task StartAsync(CancellationToken token)
//     {
//         _chatRoom.MessageReceived += OnMessageReceived;

//         try
//         {
//             await _chatRoom.JoinAsync("main", token);
//             _logger.LogInformation("Joined main chat room");

//             while (!token.IsCancellationRequested)
//             {
//                 var message = await Console.In.ReadLineAsync();
//                 if (string.IsNullOrEmpty(message)) continue;

//                 await _chatRoom.SendMessageAsync("main", message, token);
//             }
//         }
//         finally
//         {
//             await _chatRoom.LeaveAsync("main");
//             _chatRoom.MessageReceived -= OnMessageReceived;
//         }
//     }

//     public Task StopAsync()
//     {
//         _cts.Cancel();
//         return Task.CompletedTask;
//     }

//     private void OnMessageReceived(object? sender, ChatMessageEventArgs e)
//     {
//         Console.WriteLine($"[{e.From}]: {e.Message}");
//     }
// }