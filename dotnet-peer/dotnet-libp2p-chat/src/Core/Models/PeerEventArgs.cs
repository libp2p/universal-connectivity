namespace Chat.Core.Models;

public class PeerEventArgs : EventArgs
{
    public string PeerId { get; }

    public PeerEventArgs(string peerId)
    {
        PeerId = peerId;
    }
} 