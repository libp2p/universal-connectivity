package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/ipfs/go-log/v2"

	"github.com/caddyserver/certmagic"
	p2pforge "github.com/ipshipyard/p2p-forge/client"
	"github.com/libp2p/go-libp2p"
	dht "github.com/libp2p/go-libp2p-kad-dht"
	pubsub "github.com/libp2p/go-libp2p-pubsub"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/p2p/discovery/mdns"
	"github.com/libp2p/go-libp2p/p2p/discovery/routing"
	discovery "github.com/libp2p/go-libp2p/p2p/discovery/util"
	relayv2 "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
	webtransport "github.com/libp2p/go-libp2p/p2p/transport/webtransport"
	"github.com/multiformats/go-multiaddr"

	quic "github.com/libp2p/go-libp2p/p2p/transport/quic"
	"github.com/libp2p/go-libp2p/p2p/transport/tcp"
	webrtc "github.com/libp2p/go-libp2p/p2p/transport/webrtc"
	ws "github.com/libp2p/go-libp2p/p2p/transport/websocket"
)

// DiscoveryInterval is how often we re-publish our mDNS records.
const DiscoveryInterval = time.Hour

// DiscoveryServiceTag is used in our mDNS advertisements to discover other chat peers.
const DiscoveryServiceTag = "universal-connectivity"

var SysMsgChan chan *ChatMessage

var logger = log.Logger("app")

// Borrowed from https://medium.com/rahasak/libp2p-pubsub-peer-discovery-with-kademlia-dht-c8b131550ac7
// NewDHT attempts to connect to a bunch of bootstrap peers and returns a new DHT.
// If you don't have any bootstrapPeers, you can use dht.DefaultBootstrapPeers or an empty list.
func NewDHT(ctx context.Context, host host.Host, bootstrapPeers []multiaddr.Multiaddr) (*dht.IpfsDHT, error) {

	kdht, err := dht.New(ctx, host,
		dht.BootstrapPeers(dht.GetDefaultBootstrapPeerAddrInfos()...),
		dht.Mode(dht.ModeAuto),
	)
	if err != nil {
		return nil, err
	}

	if err = kdht.Bootstrap(ctx); err != nil {
		return nil, err
	}

	return kdht, nil
}

// Borrowed from https://medium.com/rahasak/libp2p-pubsub-peer-discovery-with-kademlia-dht-c8b131550ac7
// Only used by Go peer to find each other.
// TODO: since this isn't implemented on the Rust or the JS side, can probably be removed
func Discover(ctx context.Context, h host.Host, dht *dht.IpfsDHT) {
	routingDiscovery := routing.NewRoutingDiscovery(dht)

	discovery.Advertise(ctx, routingDiscovery, DiscoveryServiceTag)

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:

			peers, err := discovery.FindPeers(ctx, routingDiscovery, DiscoveryServiceTag)
			if err != nil {
				panic(err)
			}

			for _, p := range peers {
				if p.ID == h.ID() {
					continue
				}
				if h.Network().Connectedness(p.ID) != network.Connected {
					_, err = h.Network().DialPeer(ctx, p.ID)
					if err != nil {
						LogMsgf("Failed to connect to peer (%s): %s", p.ID, err.Error())
						continue
					}
					LogMsgf("Connected to peer %s", p.ID.String())
				}
			}
		}
	}
}

func LogMsgf(f string, msg ...any) {
	SysMsgChan <- &ChatMessage{Message: fmt.Sprintf(f, msg...), SenderID: "system", SenderNick: "system"}
}

func main() {
	// parse some flags to set our nickname and the room to join
	nickFlag := flag.String("nick", "", "nickname to use in chat. will be generated if empty")
	idPath := flag.String("identity", "identity.key", "path to the private key (PeerID) file")
	headless := flag.Bool("headless", false, "run without chat UI")

	var addrsToConnectTo stringSlice
	flag.Var(&addrsToConnectTo, "connect", "address to connect to (can be used multiple times)")

	flag.Parse()

	log.SetLogLevel("app", "debug")

	ctx := context.Background()

	// Create a channel to signal when the cert is loaded
	certLoaded := make(chan bool, 1)

	// Initialize the certificate manager
	certManager, err := p2pforge.NewP2PForgeCertMgr(
		p2pforge.WithCertificateStorage(&certmagic.FileStorage{Path: "p2p-forge-certs"}),
		p2pforge.WithUserAgent("go-libp2p/example/autotls"),
		p2pforge.WithCAEndpoint(p2pforge.DefaultCAEndpoint),
		p2pforge.WithOnCertLoaded(func() { certLoaded <- true }), // Signal when cert is loaded
		p2pforge.WithLogger(logger.Desugar().Sugar().Named("autotls")),
	)
	if err != nil {
		panic(err)
	}

	// Start the cert manager
	logger.Info("Starting cert manager")
	err = certManager.Start()
	if err != nil {
		panic(err)
	}
	defer certManager.Stop()

	// Load identity key
	privk, err := LoadIdentity(*idPath)
	if err != nil {
		panic(err)
	}

	// Configure libp2p options with AutoTLS
	opts := []libp2p.Option{
		libp2p.Identity(privk),
		libp2p.NATPortMap(),
		libp2p.ListenAddrStrings(
			"/ip4/0.0.0.0/tcp/9095",
			"/ip4/0.0.0.0/udp/9095/quic-v1",
			"/ip4/0.0.0.0/udp/9095/quic-v1/webtransport",
			"/ip4/0.0.0.0/udp/9095/webrtc-direct",
			"/ip6/::/tcp/9095",
			"/ip6/::/udp/9095/quic-v1",
			"/ip6/::/udp/9095/quic-v1/webtransport",
			"/ip6/::/udp/9095/webrtc-direct",
			fmt.Sprintf("/ip4/0.0.0.0/tcp/9095/tls/sni/*.%s/ws", p2pforge.DefaultForgeDomain),
			fmt.Sprintf("/ip6/::/tcp/9095/tls/sni/*.%s/ws", p2pforge.DefaultForgeDomain),
		),

		libp2p.Transport(webtransport.New),
		libp2p.Transport(quic.NewTransport),
		libp2p.Transport(tcp.NewTCPTransport),
		libp2p.Transport(webrtc.New),

		// Share the same TCP listener between the TCP and WS transports
		libp2p.ShareTCPListener(),

		// Configure the WS transport with the AutoTLS cert manager
		libp2p.Transport(ws.New, ws.WithTLSConfig(certManager.TLSConfig())),

		libp2p.UserAgent("universal-connectivity/go-peer"),

		libp2p.AddrsFactory(certManager.AddressFactory()),
	}

	// Create a new libp2p Host
	h, err := libp2p.New(opts...)
	if err != nil {
		panic(err)
	}

	certManager.ProvideHost(h)

	logger.Info("Host created with PeerID: ", h.ID())

	resources := relayv2.DefaultResources()
	resources.MaxReservations = 256
	_, err = relayv2.New(h, relayv2.WithResources(resources))
	if err != nil {
		panic(err)
	}

	// create a new PubSub service using the GossipSub router
	ps, err := pubsub.NewGossipSub(ctx, h)
	if err != nil {
		panic(err)
	}

	// use the nickname from the cli flag, or a default if blank
	nick := *nickFlag
	if len(nick) == 0 {
		nick = defaultNick(h.ID())
	}

	// join the chat room
	cr, err := JoinChatRoom(ctx, h, ps, nick)
	if err != nil {
		panic(err)
	}
	SysMsgChan = cr.SysMessages

	// setup DHT with empty discovery peers
	// so this will be a discovery peer for others
	// this peer should run on cloud(with public ip address)
	dht, err := NewDHT(ctx, h, nil)
	if err != nil {
		panic(err)
	}

	// setup peer discovery
	go Discover(ctx, h, dht)

	// setup local mDNS discovery
	if err := setupDiscovery(h); err != nil {
		panic(err)
	}

	if len(addrsToConnectTo) > 0 {
		for _, addr := range addrsToConnectTo {
			// convert to a peer.AddrInfo struct
			peerinfo, err := peer.AddrInfoFromString(addr)
			if err != nil {
				LogMsgf("Failed to parse multiaddr: %s", err.Error())
				continue
			}

			// connect to the peer
			if err := h.Connect(ctx, *peerinfo); err != nil {
				LogMsgf("Failed to connect to peer: %s", err.Error())
				continue
			}
		}
	}

	LogMsgf("PeerID: %s", h.ID().String())
	for _, addr := range h.Addrs() {
		if *headless {
			logger.Infof("Listening on: %s/p2p/%s", addr.String(), h.ID())
		} else {
			LogMsgf("Listening on: %s/p2p/%s", addr.String(), h.ID())
		}
	}

	go func() {
		<-certLoaded
		for _, addr := range h.Addrs() {
			if *headless {
				logger.Infof("Listening on: %s/p2p/%s", addr.String(), h.ID())
			} else {
				LogMsgf("Listening on: %s/p2p/%s", addr.String(), h.ID())
			}
		}
	}()

	if *headless {
		select {}
	} else {
		// draw the UI
		ui := NewChatUI(cr)
		if err = ui.Run(); err != nil {
			printErr("error running text UI: %s", err)
		}
	}
}

// printErr is like fmt.Printf, but writes to stderr.
func printErr(m string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, m, args...)
}

// defaultNick generates a nickname based on the $USER environment variable and
// the last 8 chars of a peer ID.
func defaultNick(p peer.ID) string {
	return fmt.Sprintf("%s-%s", os.Getenv("USER"), shortID(p))
}

// shortID returns the last 8 chars of a base58-encoded peer id.
func shortID(p peer.ID) string {
	str := p.String()
	return str[len(str)-8:]
}

// discoveryNotifee gets notified when we find a new peer via mDNS discovery
type discoveryNotifee struct {
	h host.Host
}

// HandlePeerFound connects to peers discovered via mDNS. Once they're connected,
// the PubSub system will automatically start interacting with them if they also
// support PubSub.
func (n *discoveryNotifee) HandlePeerFound(pi peer.AddrInfo) {
	LogMsgf("discovered new peer %s", pi.ID.String())
	err := n.h.Connect(context.Background(), pi)
	if err != nil {
		LogMsgf("error connecting to peer %s: %s", pi.ID.String(), err)
	}
}

// setupDiscovery creates an mDNS discovery service and attaches it to the libp2p Host.
// This lets us automatically discover peers on the same LAN and connect to them.
func setupDiscovery(h host.Host) error {
	// setup mDNS discovery to find local peers
	s := mdns.NewMdnsService(h, DiscoveryServiceTag, &discoveryNotifee{h: h})
	return s.Start()
}
