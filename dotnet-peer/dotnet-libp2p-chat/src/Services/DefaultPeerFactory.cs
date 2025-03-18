using Microsoft.Extensions.Logging;
using Nethermind.Libp2p.Core;

namespace Chat.Services;

/// <summary>
/// Default implementation of the peer factory
/// </summary>
public class DefaultPeerFactory : Nethermind.Libp2p.Core.IPeerFactory
{
    private readonly ILogger<DefaultPeerFactory> _logger;

    /// <summary>
    /// Initializes a new instance of the <see cref="DefaultPeerFactory"/> class
    /// </summary>
    /// <param name="logger">The logger instance</param>
    public DefaultPeerFactory(ILogger<DefaultPeerFactory> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public ILocalPeer Create(Identity identity)
    {
        _logger.LogInformation("Creating new local peer with identity: {Identity}", identity);
        return new LocalPeer(identity);
    }
} 