using Chat.Core.Interfaces;
using Chat.Core.Models;

namespace Chat.Services;

public class InMemoryMessageStore : IMessageStore
{
    private readonly Dictionary<string, List<ChatMessage>> _messages = new();
    private const int MaxMessages = 50;

    public Task AddMessageAsync(string roomName, ChatMessage message)
    {
        if (!_messages.ContainsKey(roomName))
            _messages[roomName] = new List<ChatMessage>();

        _messages[roomName].Add(message);
        if (_messages[roomName].Count > MaxMessages)
            _messages[roomName].RemoveAt(0);

        return Task.CompletedTask;
    }

    public Task<IEnumerable<ChatMessage>> GetMessagesAsync(string roomName)
    {
        if (!_messages.ContainsKey(roomName))
            return Task.FromResult(Enumerable.Empty<ChatMessage>());

        return Task.FromResult(_messages[roomName].AsEnumerable());
    }

    public Task ClearRoomAsync(string roomName)
    {
        if (_messages.ContainsKey(roomName))
            _messages[roomName].Clear();

        return Task.CompletedTask;
    }
}