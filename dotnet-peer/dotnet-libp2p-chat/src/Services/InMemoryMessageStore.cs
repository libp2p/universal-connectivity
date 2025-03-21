using Microsoft.Extensions.Logging;
using Chat.Core.Interfaces;
using Chat.Core.Models;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Chat.Services;

/// <summary>
/// An in-memory implementation of the message store
/// </summary>
public class InMemoryMessageStore : IMessageStore
{
    private readonly ILogger<InMemoryMessageStore> _logger;
    private readonly ConcurrentDictionary<string, List<ChatMessage>> _messages;

    /// <summary>
    /// Initializes a new instance of the <see cref="InMemoryMessageStore"/> class
    /// </summary>
    /// <param name="logger">The logger instance</param>
    public InMemoryMessageStore(ILogger<InMemoryMessageStore> logger)
    {
        _logger = logger;
        _messages = new ConcurrentDictionary<string, List<ChatMessage>>();
    }

    /// <inheritdoc />
    public Task AddMessageAsync(string room, ChatMessage message)
    {
        _logger.LogInformation("Adding message to room {Room}", room);
        
        _messages.AddOrUpdate(
            room,
            new List<ChatMessage> { message },
            (_, existingMessages) =>
            {
                existingMessages.Add(message);
                return existingMessages;
            });
        
        return Task.CompletedTask;
    }

    /// <inheritdoc />
    public Task<IEnumerable<ChatMessage>> GetMessagesAsync(string room)
    {
        _logger.LogInformation("Getting messages for room {Room}", room);
        
        if (_messages.TryGetValue(room, out var messages))
        {
            return Task.FromResult<IEnumerable<ChatMessage>>(messages);
        }
        
        return Task.FromResult(Enumerable.Empty<ChatMessage>());
    }

    /// <inheritdoc />
    public Task<IEnumerable<string>> GetRoomsAsync()
    {
        _logger.LogInformation("Getting all rooms");
        
        var rooms = _messages.Keys.ToList();
        return Task.FromResult<IEnumerable<string>>(rooms);
    }

    public Task ClearRoomAsync(string room)
    {
        if (_messages.TryGetValue(room, out var messages))
        {
            lock (messages)
            {
                messages.Clear();
            }
        }
        return Task.CompletedTask;
    }
}