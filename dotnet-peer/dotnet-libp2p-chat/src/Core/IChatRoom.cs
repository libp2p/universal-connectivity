using System;
using System.Threading;
using System.Threading.Tasks;

namespace Chat.Core;

public interface IChatRoom
{
    Task JoinAsync(string topic, CancellationToken token);
    Task LeaveAsync(string topic);
    Task SendMessageAsync(string topic, string message, CancellationToken token);
    event EventHandler<ChatMessageEventArgs> MessageReceived;
}

public class ChatMessageEventArgs : EventArgs
{
    public string From { get; }
    public string Message { get; }
    public string Topic { get; }

    public ChatMessageEventArgs(string from, string message, string topic)
    {
        From = from;
        Message = message;
        Topic = topic;
    }
}