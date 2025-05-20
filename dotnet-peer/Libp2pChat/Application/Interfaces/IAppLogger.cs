namespace Libp2pChat.Application.Interfaces;

/// <summary>
/// Legacy interface for application logging. Use Microsoft.Extensions.Logging.ILogger instead for new code.
/// </summary>
public interface IAppLogger
{
    /// <summary>Logs an informational message.</summary>
    void LogInformation(string message);
    
    /// <summary>Logs a warning message.</summary>
    void LogWarning(string message);
    
    /// <summary>Logs an error message.</summary>
    void LogError(string message);
    
    /// <summary>Logs an error message with an exception.</summary>
    void LogError(string message, Exception exception);
    
    /// <summary>Logs a debug message.</summary>
    void LogDebug(string message);
} 