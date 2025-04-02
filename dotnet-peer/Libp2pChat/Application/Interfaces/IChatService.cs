using Libp2pChat.Domain.Models;

namespace Libp2pChat.Application.Interfaces;

/// <summary>
/// Defines the operations for a chat service.
/// </summary>
public interface IChatService
{
    /// <summary>
    /// Gets the current peer ID.
    /// </summary>
    string PeerId { get; }
    
    /// <summary>
    /// Gets the multiaddress for this peer.
    /// </summary>
    string GetMultiaddress();
    
    /// <summary>
    /// Gets the list of currently known peers.
    /// </summary>
    IReadOnlyCollection<Peer> GetKnownPeers();
    
    /// <summary>
    /// Sends a message to all peers.
    /// </summary>
    /// <param name="message">The message to send.</param>
    /// <returns>A task representing the asynchronous operation.</returns>
    Task SendMessageAsync(string message);
    
    /// <summary>
    /// Event raised when a new message is received.
    /// </summary>
    event EventHandler<ChatMessage> MessageReceived;
    
    /// <summary>
    /// Event raised when a peer is detected.
    /// </summary>
    event EventHandler<Peer> PeerDiscovered;
    
    /// <summary>
    /// Starts the chat service.
    /// </summary>
    /// <param name="cancellationToken">The cancellation token.</param>
    /// <returns>A task representing the asynchronous operation.</returns>
    Task StartAsync(CancellationToken cancellationToken);
    
    /// <summary>
    /// Stops the chat service.
    /// </summary>
    /// <returns>A task representing the asynchronous operation.</returns>
    Task StopAsync();
} 