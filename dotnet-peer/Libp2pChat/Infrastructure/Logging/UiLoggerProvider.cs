using System;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;
using Libp2pChat.Presentation.UI;

namespace Libp2pChat.Infrastructure.Logging;

/// <summary>
/// Logger implementation that sends log messages to the chat UI.
/// </summary>
public class UiLogger : ILogger
{
    private readonly string _categoryName;
    private readonly IChatUI _chatUI;

    /// <summary>
    /// Creates a new instance of <see cref="UiLogger"/>.
    /// </summary>
    /// <param name="categoryName">The category name for the logger.</param>
    /// <param name="chatUI">The chat UI.</param>
    public UiLogger(string categoryName, IChatUI chatUI)
    {
        _categoryName = categoryName;
        _chatUI = chatUI;
    }

    /// <inheritdoc />
    public IDisposable BeginScope<TState>(TState state)
    {
        return NullScope.Instance;
    }

    /// <inheritdoc />
    public bool IsEnabled(LogLevel logLevel)
    {
        return logLevel != LogLevel.None;
    }

    /// <inheritdoc />
    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception exception, Func<TState, Exception, string> formatter)
    {
        if (!IsEnabled(logLevel))
        {
            return;
        }

        string message = formatter(state, exception);
        string shortCategory = GetShortCategoryName(_categoryName);
        string levelString = GetLogLevelString(logLevel);
        string formattedMessage = $"[{DateTime.Now:HH:mm:ss.fff}] [{levelString}] [{shortCategory}] {message}";

        _chatUI.AddLog(formattedMessage);

        if (exception != null)
        {
            _chatUI.AddLog($"[{DateTime.Now:HH:mm:ss.fff}] [{levelString}] Exception: {exception.Message}");
        }
    }

    private string GetShortCategoryName(string categoryName)
    {
        // Get the last part of the category name (e.g., "Sample.App.Controllers.HomeController" -> "HomeController")
        int lastDotIndex = categoryName.LastIndexOf('.');
        return lastDotIndex != -1 ? categoryName.Substring(lastDotIndex + 1) : categoryName;
    }

    private string GetLogLevelString(LogLevel logLevel)
    {
        return logLevel switch
        {
            LogLevel.Trace => "TRACE",
            LogLevel.Debug => "DEBUG",
            LogLevel.Information => "INFO",
            LogLevel.Warning => "WARN",
            LogLevel.Error => "ERROR",
            LogLevel.Critical => "CRIT",
            _ => logLevel.ToString().ToUpper(),
        };
    }

    private class NullScope : IDisposable
    {
        public static readonly NullScope Instance = new();

        private NullScope()
        {
        }

        public void Dispose()
        {
        }
    }
}

/// <summary>
/// Creates UiLogger instances that send logs to the chat UI.
/// </summary>
public class UiLoggerProvider : ILoggerProvider
{
    private readonly IChatUI _chatUI;

    /// <summary>
    /// Creates a new instance of <see cref="UiLoggerProvider"/>.
    /// </summary>
    /// <param name="chatUI">The chat UI to log to.</param>
    public UiLoggerProvider(IChatUI chatUI)
    {
        _chatUI = chatUI;
    }

    /// <inheritdoc />
    public ILogger CreateLogger(string categoryName)
    {
        return new UiLogger(categoryName, _chatUI);
    }

    /// <inheritdoc />
    public void Dispose()
    {
        // No resources to dispose
    }
}

/// <summary>
/// Extension methods for adding UI logger to the logging builder.
/// </summary>
public static class UiLoggerExtensions
{
    /// <summary>
    /// Adds a UI logger that logs to the chat UI.
    /// </summary>
    /// <param name="builder">The logging builder.</param>
    /// <returns>The logging builder for chaining.</returns>
    public static ILoggingBuilder AddUiLogger(this ILoggingBuilder builder)
    {
        builder.Services.AddSingleton<ILoggerProvider>(sp =>
        {
            var chatUI = sp.GetRequiredService<IChatUI>();
            return new UiLoggerProvider(chatUI);
        });

        return builder;
    }
}