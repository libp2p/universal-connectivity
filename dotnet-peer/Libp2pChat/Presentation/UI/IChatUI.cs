using Libp2pChat.Domain.Models;

namespace Libp2pChat.Presentation.UI;

/// <summary>
/// Defines the operations for a chat user interface.
/// </summary>
public interface IChatUI
{
    /// <summary>
    /// Adds a message to the chat.
    /// </summary>
    /// <param name="message">The message to add.</param>
    void AddChatMessage(string message);
    
    /// <summary>
    /// Adds a message to the chat.
    /// </summary>
    /// <param name="chatMessage">The chat message to add.</param>
    void AddChatMessage(ChatMessage chatMessage);
    
    /// <summary>
    /// Adds a log message.
    /// </summary>
    /// <param name="message">The message to log.</param>
    void AddLog(string message);
    
    /// <summary>
    /// Adds a peer to the peers list.
    /// </summary>
    /// <param name="peer">The peer to add.</param>
    void AddPeer(Peer peer);
    
    /// <summary>
    /// Updates the information displayed about the local peer.
    /// </summary>
    /// <param name="peerId">The peer ID.</param>
    /// <param name="multiaddress">The multiaddress.</param>
    void UpdatePeerInfo(string peerId, string multiaddress);
    
    /// <summary>
    /// Initializes the UI.
    /// </summary>
    void Initialize();
    
    /// <summary>
    /// Runs the UI.
    /// </summary>
    void Run();
    
    /// <summary>
    /// Triggered when a message is sent from the UI.
    /// </summary>
    event EventHandler<string> MessageSent;
    
    /// <summary>
    /// Triggered when the UI is exited.
    /// </summary>
    event EventHandler ExitRequested;
} 