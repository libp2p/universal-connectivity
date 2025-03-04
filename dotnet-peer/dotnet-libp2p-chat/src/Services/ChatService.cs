using Chat.Core.Interfaces;
using Chat.Core.Models;
using Microsoft.Extensions.Logging;

namespace Chat.Services;

public class ChatService : IChatService
{
    private readonly IMessageStore _messageStore;
    private readonly ILogger<ChatService> _logger;
    private readonly List<Room> _rooms;

    public event EventHandler<ChatMessage>? MessageReceived;

    public ChatService(IMessageStore messageStore, ILogger<ChatService> logger)
    {
        _messageStore = messageStore;
        _logger = logger;
        _rooms = new List<Room>
        {
            new("general", "General discussion"),
            new("tech", "Technical chat"),
            new("random", "Random topics")
        };
    }

    public IEnumerable<Room> GetAvailableRooms() => _rooms;

    public async Task SendMessageAsync(string roomName, ChatMessage message)
    {
        await _messageStore.AddMessageAsync(roomName, message);
        MessageReceived?.Invoke(this, message);
        _logger.LogInformation("Message sent to {Room} by {User}: {Message}", 
            roomName, message.Username, message.Content);
    }

    public Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName)
        => _messageStore.GetMessagesAsync(roomName);
}