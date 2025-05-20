using Libp2pChat.Application.Interfaces;
using Microsoft.Extensions.Logging;

namespace Libp2pChat.Infrastructure.Logging;

/// <summary>
/// Adapter that wraps ILogger to implement IAppLogger for backward compatibility.
/// </summary>
public class LoggerAdapter : IAppLogger
{
    private readonly ILogger _logger;

    /// <summary>
    /// Creates a new instance of the <see cref="LoggerAdapter"/> class.
    /// </summary>
    /// <param name="logger">The standard logger implementation.</param>
    public LoggerAdapter(ILogger logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public void LogInformation(string message) => _logger.LogInformation(message);

    /// <inheritdoc />
    public void LogWarning(string message) => _logger.LogWarning(message);

    /// <inheritdoc />
    public void LogError(string message) => _logger.LogError(message);

    /// <inheritdoc />
    public void LogError(string message, Exception exception) => _logger.LogError(exception, message);

    /// <inheritdoc />
    public void LogDebug(string message) => _logger.LogDebug(message);
}