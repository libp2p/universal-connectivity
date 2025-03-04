using System.Text;
using Chat.Core.Interfaces;
using Chat.Core.Models;
using Chat.UI.Themes;
using Microsoft.Extensions.Logging;

namespace Chat.UI;

public class ConsoleUI : IUserInterface
{
    private readonly IChatService _chatService;
    private readonly ILibp2pNode _node;
    private readonly ITheme _theme;
    private readonly ILogger<ConsoleUI> _logger;
    private string _currentRoom = "default";

    public ConsoleUI(
        IChatService chatService,
        ILibp2pNode node,
        ITheme theme,
        ILogger<ConsoleUI> logger)
    {
        _chatService = chatService;
        _node = node;
        _theme = theme;
        _logger = logger;
    }

    public async Task ShowMessageAsync(ChatMessage message)
    {
        var formattedMessage = _theme.FormatMessage(message.Username, message.Content);
        Console.WriteLine(formattedMessage);
        await Task.CompletedTask;
    }

    public async Task UpdateRoomListAsync(IEnumerable<Room> rooms)
    {
        var roomNames = rooms.Select(r => r.Name);
        var formattedRooms = _theme.FormatRoomList(roomNames);
        Console.WriteLine(formattedRooms);
        await Task.CompletedTask;
    }

    public async Task RunAsync(CancellationToken token)
    {
        Console.Clear();
        Console.WriteLine(_theme.FormatSystemMessage("Welcome to Libp2p Chat!"));
        Console.WriteLine(_theme.FormatHelp());
        Console.WriteLine();

        _chatService.MessageReceived += async (sender, message) =>
        {
            await ShowMessageAsync(message);
        };

        while (!token.IsCancellationRequested)
        {
            try
            {
                Console.Write($"{_currentRoom}> ");
                var input = await Console.In.ReadLineAsync();
                if (string.IsNullOrEmpty(input)) continue;

                if (input.StartsWith("/"))
                {
                    await HandleCommand(input);
                }
                else
                {
                    var message = new ChatMessage("User", input, DateTimeOffset.UtcNow);
                    await _chatService.SendMessageAsync(_currentRoom, message);
                    await _node.BroadcastMessageAsync(_currentRoom, input);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing user input");
                Console.WriteLine(_theme.FormatErrorMessage(ex.Message));
            }
        }
    }

    private async Task HandleCommand(string command)
    {
        var parts = command.Split(' ', 2);
        var cmd = parts[0].ToLower();
        var arg = parts.Length > 1 ? parts[1] : string.Empty;

        try
        {
            switch (cmd)
            {
                case "/join":
                    if (string.IsNullOrEmpty(arg))
                    {
                        Console.WriteLine(_theme.FormatErrorMessage("Room name required"));
                        break;
                    }
                    await _node.JoinRoomAsync(arg);
                    _currentRoom = arg;
                    Console.WriteLine(_theme.FormatSystemMessage($"Joined room: {arg}"));
                    break;

                case "/leave":
                    if (string.IsNullOrEmpty(arg))
                    {
                        Console.WriteLine(_theme.FormatErrorMessage("Room name required"));
                        break;
                    }
                    await _node.LeaveRoomAsync(arg);
                    if (_currentRoom == arg) _currentRoom = "default";
                    Console.WriteLine(_theme.FormatSystemMessage($"Left room: {arg}"));
                    break;

                case "/rooms":
                    var rooms = _chatService.GetAvailableRooms();
                    await UpdateRoomListAsync(rooms);
                    break;

                case "/help":
                    Console.WriteLine(_theme.FormatHelp());
                    break;

                default:
                    Console.WriteLine(_theme.FormatErrorMessage($"Unknown command: {cmd}"));
                    break;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine(_theme.FormatErrorMessage($"Error executing command: {ex.Message}"));
        }
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