using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using Terminal.Gui;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols.Pubsub;
using Multiformats.Address;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Collections.Concurrent;
using Libp2pChat.Application.Interfaces;
using Libp2pChat.Application.Services;
using Libp2pChat.Infrastructure.Libp2p;
using Libp2pChat.Infrastructure.Logging;
using Libp2pChat.Presentation.UI;

namespace Libp2pChat;

/// <summary>
/// Entry point for the Libp2p Chat application.
/// </summary>
public class Program
{
    /// <summary>
    /// Main entry point.
    /// </summary>
    /// <param name="args">Command-line arguments.</param>
    /// <returns>A task representing the asynchronous operation.</returns>
    public static async Task Main(string[] args)
    {
        try
        {
            // Check console environment
            Console.WriteLine("Starting Libp2p Chat Application...");
            Console.WriteLine($"Console window size: {Console.WindowWidth}x{Console.WindowHeight}");
            Console.WriteLine($"OS: {Environment.OSVersion}");
            Console.WriteLine($".NET Version: {Environment.Version}");
            
            // Set up dependency injection
            var serviceProvider = ConfigureServices();
            
            // Get the application service
            var appService = serviceProvider.GetRequiredService<ChatApplicationService>();
            
            // Handle application domain unhandled exceptions
            AppDomain.CurrentDomain.UnhandledException += (sender, e) =>
            {
                var logger = serviceProvider.GetRequiredService<IAppLogger>();
                logger.LogError($"Unhandled exception: {e.ExceptionObject}");
                
                // Also log to console in case the UI is not available
                Console.WriteLine($"Unhandled exception: {e.ExceptionObject}");
            };
            
            // Run the application
            await appService.RunAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Fatal error: {ex.Message}");
            Console.WriteLine(ex.StackTrace);
        }
    }
    
    /// <summary>
    /// Configures the dependency injection container.
    /// </summary>
    /// <returns>The configured service provider.</returns>
    private static IServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();
        
        // Register libp2p services
        services.AddLibp2p(builder => builder.WithPubsub());
        
        // Register logging
        services.AddLogging(builder =>
        {
            builder.SetMinimumLevel(LogLevel.Debug)
                .AddFilter("Nethermind.Libp2p", LogLevel.Debug)
                .AddSimpleConsole(options =>
                {
                    options.SingleLine = true;
                    options.TimestampFormat = "[HH:mm:ss.fff] ";
                });
        });
        
        // Register UI
        services.AddSingleton<IChatUI, TerminalUI>();
        
        // Register application services
        services.AddSingleton<ChatApplicationService>();
        
        // Create service provider to resolve services used during registration
        var tempProvider = services.BuildServiceProvider();
        
        // Register infrastructure services that require resolved dependencies
        services.AddSingleton<IChatService>(sp =>
        {
            var logger = sp.GetRequiredService<IAppLogger>();
            var peerFactory = sp.GetRequiredService<IPeerFactory>();
            var router = sp.GetRequiredService<PubsubRouter>();
            
            return new Libp2pChatService(logger, peerFactory, router);
        });
        
        // Register logger that requires UI
        services.AddSingleton<IAppLogger>(sp =>
        {
            var chatUI = sp.GetRequiredService<IChatUI>();
            var loggerFactory = sp.GetRequiredService<ILoggerFactory>();
            
            var terminalLoggerFactory = new TerminalLoggerFactory(chatUI, loggerFactory);
            return terminalLoggerFactory.CreateLogger("Libp2pChat");
        });
        
        // Configure logging provider to forward libp2p logs to our UI
        services.Configure<LoggerFilterOptions>(options =>
        {
            options.MinLevel = LogLevel.Debug;
            options.AddFilter("Nethermind.Libp2p", LogLevel.Debug);
        });
        
        // Dispose the temporary provider
        tempProvider.Dispose();
        
        // Build the final service provider
        return services.BuildServiceProvider();
    }
}
