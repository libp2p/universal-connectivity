using Chat.Core.Interfaces;
using Chat.Core.Models;
using Microsoft.Extensions.Logging;

namespace Chat.Services;

internal class ChatService : IChatService
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
            roomName, message.SenderId, message.Message);
    }

    public Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName)
        => _messageStore.GetMessagesAsync(roomName);

    public Task JoinRoomAsync(string room)
    {
        _logger.LogInformation("Joined room: {Room}", room);
        return Task.CompletedTask;
    }

    public Task LeaveRoomAsync(string room)
    {
        _logger.LogInformation("Left room: {Room}", room);
        return Task.CompletedTask;
    }

    public Task ConnectToPeerAsync(string peerAddress)
    {
        _logger.LogInformation("Connecting to peer: {PeerAddress}", peerAddress);
        return Task.CompletedTask;
    }
}