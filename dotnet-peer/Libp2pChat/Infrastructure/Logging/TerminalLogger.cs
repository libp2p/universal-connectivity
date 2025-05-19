using Libp2pChat.Application.Interfaces;
using Libp2pChat.Presentation.UI;
using Microsoft.Extensions.Logging;

namespace Libp2pChat.Infrastructure.Logging;

/// <summary>
/// A logger implementation that logs to the terminal UI.
/// </summary>
public class TerminalLogger : IAppLogger
{
    private readonly IChatUI _chatUI;
    private readonly string _category;
    
    /// <summary>
    /// Creates a new instance of the <see cref="TerminalLogger"/> class.
    /// </summary>
    /// <param name="chatUI">The chat UI.</param>
    /// <param name="category">The category name for the logger.</param>
    public TerminalLogger(IChatUI chatUI, string category)
    {
        _chatUI = chatUI;
        _category = category;
    }
    
    private void LogWithLevel(string level, string message)
    {
        string formattedMessage = $"[{DateTime.Now:HH:mm:ss.fff}] [{level}] {message}";
        _chatUI.AddLog(formattedMessage);
    }
    
    /// <inheritdoc />
    public void LogInformation(string message)
    {
        LogWithLevel("Info", message);
    }
    
    /// <inheritdoc />
    public void LogWarning(string message)
    {
        LogWithLevel("Warning", message);
    }
    
    /// <inheritdoc />
    public void LogError(string message)
    {
        LogWithLevel("Error", message);
    }
    
    /// <inheritdoc />
    public void LogError(string message, Exception exception)
    {
        LogWithLevel("Error", message);
        LogWithLevel("Error", $"Exception: {exception.Message}\nStack trace: {exception.StackTrace}");
    }
    
    /// <inheritdoc />
    public void LogDebug(string message)
    {
        LogWithLevel("Debug", message);
    }
}

/// <summary>
/// Factory for creating terminal loggers.
/// </summary>
public class TerminalLoggerFactory
{
    private readonly IChatUI _chatUI;
    private readonly ILoggerFactory _loggerFactory;
    
    /// <summary>
    /// Creates a new instance of the <see cref="TerminalLoggerFactory"/> class.
    /// </summary>
    /// <param name="chatUI">The chat UI.</param>
    /// <param name="loggerFactory">The logger factory.</param>
    public TerminalLoggerFactory(IChatUI chatUI, ILoggerFactory loggerFactory)
    {
        _chatUI = chatUI;
        _loggerFactory = loggerFactory;
    }
    
    /// <summary>
    /// Creates a new terminal logger for the specified category.
    /// </summary>
    /// <param name="category">The category name.</param>
    /// <returns>A new terminal logger.</returns>
    public IAppLogger CreateLogger(string category)
    {
        return new TerminalLogger(_chatUI, category);
    }
} 