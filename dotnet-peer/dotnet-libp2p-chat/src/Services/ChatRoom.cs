// using System;
// using System.Threading;
// using System.Threading.Tasks;
// using Microsoft.Extensions.Logging;
// using Chat.Core;

// namespace Chat.Services;

// public class ChatRoom : IChatRoom
// {
//     private readonly ILogger<ChatRoom> _logger;
//     private readonly IPeerManager _peerManager;

//     public event EventHandler<ChatMessageEventArgs>? MessageReceived;

//     public ChatRoom(ILogger<ChatRoom> logger, IPeerManager peerManager)
//     {
//         _logger = logger;
//         _peerManager = peerManager;
//     }

//     public async Task JoinAsync(string topic, CancellationToken token)
//     {
//         _logger.LogInformation("Joining chat room: {topic}", topic);
//         // Implementation will come later
//     }

//     public async Task LeaveAsync(string topic)
//     {
//         _logger.LogInformation("Leaving chat room: {topic}", topic);
//         // Implementation will come later
//     }

//     public async Task SendMessageAsync(string topic, string message, CancellationToken token)
//     {
//         _logger.LogInformation("Sending message to {topic}: {message}", topic, message);
//         MessageReceived?.Invoke(this, new ChatMessageEventArgs("me", message, topic));
//     }
// }