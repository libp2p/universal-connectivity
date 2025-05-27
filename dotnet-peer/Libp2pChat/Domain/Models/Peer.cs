namespace Libp2pChat.Domain.Models;

/// <summary>
/// Represents a peer in the libp2p network.
/// </summary>
public class Peer
{
    /// <summary>
    /// Gets the unique identifier of the peer.
    /// </summary>
    public string Id { get; }

    /// <summary>
    /// Gets or sets the display name of the peer.
    /// </summary>
    public string DisplayName { get; set; }

    /// <summary>
    /// Gets or sets the last time this peer was seen active.
    /// </summary>
    public DateTime LastSeen { get; set; }

    /// <summary>
    /// Gets the short version of the peer ID suitable for display.
    /// </summary>
    public string ShortId => Id.Length > 10 ? Id.Substring(0, 10) + "..." : Id;

    /// <summary>
    /// Creates a new instance of the <see cref="Peer"/> class.
    /// </summary>
    /// <param name="id">The peer identifier.</param>
    /// <param name="displayName">The display name for the peer.</param>
    public Peer(string id, string displayName)
    {
        Id = id;
        DisplayName = displayName;
        LastSeen = DateTime.UtcNow;
    }

    /// <summary>
    /// Updates the last seen timestamp to the current time.
    /// </summary>
    public void UpdateLastSeen()
    {
        LastSeen = DateTime.UtcNow;
    }

    /// <summary>
    /// Gets a formatted string indicating how long ago this peer was last seen.
    /// </summary>
    public string GetLastSeenFormatted()
    {
        TimeSpan sinceLastSeen = DateTime.UtcNow - LastSeen;
        return sinceLastSeen.TotalMinutes < 1
            ? $"{sinceLastSeen.TotalSeconds:0}s ago"
            : $"{sinceLastSeen.TotalMinutes:0.0}m ago";
    }

    /// <summary>
    /// Creates a generic libp2p peer.
    /// </summary>
    /// <param name="implementation">Optional implementation name (e.g., 'go', 'js', 'rust')</param>
    /// <returns>A new peer instance representing a libp2p peer</returns>
    public static Peer CreateLibp2pPeer(string implementation = "unknown")
    {
        return new Peer($"libp2p-{implementation}-{DateTime.UtcNow.Ticks % 10000}", $"libp2p-{implementation}");
    }
}