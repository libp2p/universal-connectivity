using Nethermind.Libp2p.Core;

namespace Chat.Core.Interfaces
{
    /// <summary>
    /// Factory for creating libp2p peers
    /// </summary>
    public interface IPeerFactory
    {
        /// <summary>
        /// Creates a new local peer with the given identity
        /// </summary>
        /// <param name="identity">The identity to use for the peer</param>
        /// <returns>A new local peer instance</returns>
        ILocalPeer Create(Identity identity);
    }
} 