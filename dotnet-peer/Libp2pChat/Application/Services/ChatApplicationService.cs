using Libp2pChat.Application.Interfaces;
using Libp2pChat.Domain.Models;
using Libp2pChat.Presentation.UI;


namespace Libp2pChat.Application.Services;

/// <summary>
/// Application service that coordinates the chat components.
/// </summary>
public class ChatApplicationService : IDisposable
{
    private readonly IChatService _chatService;
    private readonly IChatUI _chatUI;
    private readonly IAppLogger _logger;
    private readonly CancellationTokenSource _cancellationTokenSource;
    private bool _isDisposed;
    
    /// <summary>
    /// Creates a new instance of the <see cref="ChatApplicationService"/> class.
    /// </summary>
    /// <param name="chatService">The chat service.</param>
    /// <param name="chatUI">The chat UI.</param>
    /// <param name="logger">The application logger.</param>
    public ChatApplicationService(IChatService chatService, IChatUI chatUI, IAppLogger logger)
    {
        _chatService = chatService;
        _chatUI = chatUI;
        _logger = logger;
        _cancellationTokenSource = new CancellationTokenSource();
    }
    
    /// <summary>
    /// Starts the chat application.
    /// </summary>
    /// <returns>A task representing the asynchronous operation.</returns>
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
                    _logger.LogInformation($"Peer ID: {peerId}");
                    _logger.LogInformation($"Multiaddress: {multiaddress}");
                    
                    // Add welcome messages directly to the chat area
                    _chatUI.AddChatMessage("Welcome to Libp2p Chat!");
                    _chatUI.AddChatMessage("You can exchange messages with other libp2p peers.");
                    _chatUI.AddChatMessage("Use the 'Send' button or press Enter to send messages.");
                    _chatUI.AddChatMessage("Press Ctrl+Q to exit.");
                    
                    // Add help information
                    _logger.LogInformation("\n[Help] GO PEER CONNECTION INSTRUCTIONS:");
                    _logger.LogInformation($"[Help] Connect using the following command:");
                    _logger.LogInformation($"[Help] ./go-peer --connect /ip4/127.0.0.1/tcp/9096/p2p/{peerId}");
                    _logger.LogInformation("[Help] Ensure ports and peer IDs match as configured.");
                }
                catch (Exception ex)
                {
                    _logger.LogError("Error in background task", ex);
                }
            });
            
            // Run the UI on the main thread
            _chatUI.Run();
        }
        catch (Exception ex)
        {
            _logger.LogError("Error starting chat application", ex);
            throw;
        }
    }
    
    /// <summary>
    /// Stops the chat application.
    /// </summary>
    /// <returns>A task representing the asynchronous operation.</returns>
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
            _logger.LogError("Error stopping chat application", ex);
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
    /// <param name="disposing">Whether to dispose managed resources.</param>
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
            _logger.LogError("Error handling received message", ex);
        }
    }
    
    private void OnPeerDiscovered(object? sender, Peer peer)
    {
        try
        {
            _chatUI.AddPeer(peer);
            _logger.LogInformation($"Peer discovered: {peer.Id} ({peer.DisplayName})");
        }
        catch (Exception ex)
        {
            _logger.LogError("Error handling peer discovery", ex);
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
            _logger.LogError("Error sending message", ex);
        }
    }
    
    private async void OnExitRequested(object? sender, EventArgs e)
    {
        try
        {
            await StopAsync();
            
            // Exit the application
            Terminal.Gui.Application.RequestStop();
        }
        catch (Exception ex)
        {
            _logger.LogError("Error handling exit request", ex);
        }
    }
} 