using System.Text;
using Chat.Core.Interfaces;
using Chat.Core.Models;
using Chat.UI.Themes;
using Microsoft.Extensions.Logging;

namespace Chat.UI;

public class ConsoleUI : IUserInterface
{
    private readonly IChatService _chatService;
    private readonly ITheme _theme;
    private readonly ILogger<ConsoleUI> _logger;

    public ConsoleUI(IChatService chatService, ITheme theme, ILogger<ConsoleUI> logger)
    {
        _chatService = chatService;
        _theme = theme;
        _logger = logger;
    }

    public async Task ShowMessageAsync(ChatMessage message)
    {
        var formattedMessage = _theme.FormatMessage(message.Username, message.Content);
        Console.WriteLine(formattedMessage);
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.ResetColor();
        await Task.CompletedTask;
    }

    public async Task UpdateRoomListAsync(IEnumerable<Room> rooms)
    {
        var roomNames = rooms.Select(r => r.Name);
        var formattedRooms = _theme.FormatRoomList(roomNames);
        Console.WriteLine(formattedRooms);
        Console.BackgroundColor = ConsoleColor.DarkGray;
        Console.ForegroundColor = ConsoleColor.White;
        Console.WriteLine(formattedRooms);
        Console.ResetColor();
        await Task.CompletedTask;
    }

    public async Task RunAsync(CancellationToken token)
    {
        _chatService.MessageReceived += async (sender, message) =>
        {
            await ShowMessageAsync(message);
        };

        while (!token.IsCancellationRequested)
        {
            try
            {
                var input = await Console.In.ReadLineAsync();
                if (string.IsNullOrEmpty(input)) continue;

                if (input.StartsWith("/"))
                {
                    await HandleCommand(input);
                }
                else
                {
                    // Default to sending message in current room
                    var message = new ChatMessage("User", input, DateTimeOffset.UtcNow);
                    await _chatService.SendMessageAsync("default", message);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing user input");
                Console.WriteLine(_theme.FormatSystemMessage($"Error: {ex.Message}"));
            }
        }
    }

    private async Task HandleCommand(string command)
    {
        var parts = command.Split(' ', 2);
        switch (parts[0].ToLower())
        {
            case "/rooms":
                var rooms = _chatService.GetAvailableRooms();
                await UpdateRoomListAsync(rooms);
                break;
            default:
                Console.WriteLine(_theme.FormatSystemMessage($"Unknown command: {parts[0]}"));
                break;
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