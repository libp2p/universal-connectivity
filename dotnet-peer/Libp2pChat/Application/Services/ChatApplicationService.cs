using Libp2pChat.Application.Interfaces;
using Libp2pChat.Domain.Models;
using Libp2pChat.Presentation.UI;
using Microsoft.Extensions.Logging;

namespace Libp2pChat.Application.Services;

/// <summary>
/// Application service that coordinates the chat components.
/// </summary>
public class ChatApplicationService : IDisposable
{
    private readonly IChatService _chatService;
    private readonly IChatUI _chatUI;
    private readonly ILogger<ChatApplicationService> _logger;
    private readonly CancellationTokenSource _cancellationTokenSource;
    private bool _isDisposed;

    /// <summary>
    /// Creates a new instance of the chat application service.
    /// </summary>
    public ChatApplicationService(IChatService chatService, IChatUI chatUI, ILogger<ChatApplicationService> logger)
    {
        _chatService = chatService;
        _chatUI = chatUI;
        _logger = logger;
        _cancellationTokenSource = new CancellationTokenSource();
    }

    /// <summary>
    /// Starts the chat application.
    /// </summary>
    public async Task RunAsync()
    {
        try
        {
            // Initialize the UI
            _chatUI.Initialize();

            // Wire up events
            _chatService.MessageReceived += OnMessageReceived;
            _chatService.PeerDiscovered += OnPeerDiscovered;
            _chatUI.MessageSent += OnMessageSent;
            _chatUI.ExitRequested += OnExitRequested;

            // Start the chat service in a background task
            _ = Task.Run(async () =>
            {
                try
                {
                    // Start the chat service
                    _logger.LogInformation("Starting chat application...");
                    await _chatService.StartAsync(_cancellationTokenSource.Token);

                    // Update the UI with peer info
                    string peerId = _chatService.PeerId;
                    string multiaddress = _chatService.GetMultiaddress();
                    _chatUI.UpdatePeerInfo(peerId, multiaddress);

                    // Log connection info
                    _logger.LogInformation("Peer ID: {PeerId}", peerId);
                    _logger.LogInformation("Multiaddress: {Multiaddress}", multiaddress);

                    // Add welcome messages directly to the chat area
                    _chatUI.AddChatMessage("Welcome to Libp2p Chat!");
                    _chatUI.AddChatMessage("You can exchange messages with other libp2p peers.");
                    _chatUI.AddChatMessage("Use the 'Send' button or press Enter to send messages.");
                    _chatUI.AddChatMessage("Press Ctrl+Q to exit.");

                    // Add help information
                    _logger.LogInformation("\n[Help] CONNECTION INSTRUCTIONS:");
                    _logger.LogInformation("[Help] Connect to this peer using your libp2p client:");
                    _logger.LogInformation("[Help] Multiaddress: {Multiaddress}", multiaddress);
                    _logger.LogInformation("[Help] For localhost connections: /ip4/127.0.0.1/tcp/{Port}/p2p/{PeerId}", multiaddress.Split('/')[4], peerId);
                    _logger.LogInformation("[Help] Use the above multiaddress with your libp2p client's connect command.");
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in background task");
                }
            });

            // Run the UI on the main thread
            _chatUI.Run();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error starting chat application");
            throw;
        }
    }

    /// <summary>
    /// Stops the chat application.
    /// </summary>
    public async Task StopAsync()
    {
        try
        {
            _logger.LogInformation("Stopping chat application...");

            if (!_cancellationTokenSource.IsCancellationRequested)
                _cancellationTokenSource.Cancel();

            await _chatService.StopAsync();

            _logger.LogInformation("Chat application stopped");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping chat application");
            throw;
        }
    }

    /// <inheritdoc />
    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    /// <summary>
    /// Disposes resources.
    /// </summary>
    protected virtual void Dispose(bool disposing)
    {
        if (_isDisposed)
            return;

        if (disposing)
        {
            // Unwire events
            _chatService.MessageReceived -= OnMessageReceived;
            _chatService.PeerDiscovered -= OnPeerDiscovered;
            _chatUI.MessageSent -= OnMessageSent;
            _chatUI.ExitRequested -= OnExitRequested;

            // Dispose cancellation token source
            _cancellationTokenSource.Dispose();

            // Dispose other disposables
            if (_chatService is IDisposable disposableService)
                disposableService.Dispose();

            if (_chatUI is IDisposable disposableUI)
                disposableUI.Dispose();
        }

        _isDisposed = true;
    }

    private void OnMessageReceived(object? sender, ChatMessage message)
    {
        try
        {
            _chatUI.AddChatMessage(message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling received message");
        }
    }

    private void OnPeerDiscovered(object? sender, Peer peer)
    {
        try
        {
            _chatUI.AddPeer(peer);
            _logger.LogInformation("Peer discovered: {PeerId} ({DisplayName})", peer.Id, peer.DisplayName);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling peer discovery");
        }
    }

    private async void OnMessageSent(object? sender, string message)
    {
        try
        {
            await _chatService.SendMessageAsync(message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending message");
        }
    }

    private async void OnExitRequested(object? sender, EventArgs e)
    {
        try
        {
            await StopAsync();

            Terminal.Gui.Application.RequestStop();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling exit request");
        }
    }
}