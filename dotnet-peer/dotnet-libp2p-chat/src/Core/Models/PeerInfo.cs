namespace Chat.Core.Models;

public class PeerInfo
{
    public required string PeerId { get; init; }
    public required List<string> Addresses { get; init; }
} 