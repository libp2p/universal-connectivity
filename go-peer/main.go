package main

import (
	"context"
	"flag"
	"fmt"
	"math"
	"os"
	"strings"
	"time"

	"github.com/ipfs/go-log/v2"

	"github.com/caddyserver/certmagic"
	p2pforge "github.com/ipshipyard/p2p-forge/client"
	"github.com/libp2p/go-libp2p"
	pubsub "github.com/libp2p/go-libp2p-pubsub"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	rcmgr "github.com/libp2p/go-libp2p/p2p/host/resource-manager"
	relayv2 "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
	quic "github.com/libp2p/go-libp2p/p2p/transport/quic"
	"github.com/libp2p/go-libp2p/p2p/transport/tcp"
	webrtc "github.com/libp2p/go-libp2p/p2p/transport/webrtc"
	ws "github.com/libp2p/go-libp2p/p2p/transport/websocket"
	webtransport "github.com/libp2p/go-libp2p/p2p/transport/webtransport"
)

var SysMsgChan chan *ChatMessage

var logger = log.Logger("app")

func logDetailf(format string, args ...interface{}) {
	msg := fmt.Sprintf(format, args...)
	logger.Infof("🔍 %s", msg)
	if SysMsgChan != nil {
		select {
		case SysMsgChan <- &ChatMessage{Message: fmt.Sprintf("🔍 %s", msg), SenderID: "system", SenderNick: "system"}:
		default:
		}
	}
}

func logConnectionf(format string, args ...interface{}) {
	msg := fmt.Sprintf(format, args...)
	logger.Infof("🔗 %s", msg)
	if SysMsgChan != nil {
		select {
		case SysMsgChan <- &ChatMessage{Message: fmt.Sprintf("🔗 %s", msg), SenderID: "system", SenderNick: "system"}:
		default:
		}
	}
}

func logPubSubf(format string, args ...interface{}) {
	msg := fmt.Sprintf(format, args...)
	logger.Infof("📡 %s", msg)
	if SysMsgChan != nil {
		select {
		case SysMsgChan <- &ChatMessage{Message: fmt.Sprintf("📡 %s", msg), SenderID: "system", SenderNick: "system"}:
		default:
		}
	}
}

func logErrorf(format string, args ...interface{}) {
	msg := fmt.Sprintf(format, args...)
	logger.Errorf("❌ %s", msg)
	if SysMsgChan != nil {
		select {
		case SysMsgChan <- &ChatMessage{Message: fmt.Sprintf("❌ %s", msg), SenderID: "system", SenderNick: "system"}:
		default:
		}
	}
}

func LogMsgf(f string, msg ...any) {
	if SysMsgChan != nil {
		select {
		case SysMsgChan <- &ChatMessage{Message: fmt.Sprintf(f, msg...), SenderID: "system", SenderNick: "system"}:
		default:
		}
	}
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
	
	logDetailf("Starting Universal Connectivity Go Peer...")
	logDetailf("Flags - nick: %s, identity: %s, headless: %v", *nickFlag, *idPath, *headless)
	logDetailf("Connect addresses: %v", []string(addrsToConnectTo))

	ctx := context.Background()

	// Create a channel to signal when the cert is loaded
	certLoaded := make(chan bool, 1)

	logDetailf("Initializing certificate manager...")
	// Initialize the certificate manager
	certManager, err := p2pforge.NewP2PForgeCertMgr(
		p2pforge.WithCertificateStorage(&certmagic.FileStorage{Path: "p2p-forge-certs"}),
		p2pforge.WithUserAgent("go-libp2p/example/autotls"),
		p2pforge.WithCAEndpoint(p2pforge.DefaultCAEndpoint),
		p2pforge.WithOnCertLoaded(func() { 
			logDetailf("Certificate loaded successfully")
			certLoaded <- true 
		}), // Signal when cert is loaded
		p2pforge.WithLogger(logger.Desugar().Sugar().Named("autotls")),
	)
	if err != nil {
		logErrorf("Failed to create certificate manager: %v", err)
		panic(err)
	}

	// Start the cert manager
	logDetailf("Starting certificate manager...")
	err = certManager.Start()
	if err != nil {
		logErrorf("Failed to start certificate manager: %v", err)
		panic(err)
	}
	defer certManager.Stop()

	// Load identity key
	logDetailf("Loading identity key from: %s", *idPath)
	privk, err := LoadIdentity(*idPath)
	if err != nil {
		logErrorf("Failed to load identity key: %v", err)
		panic(err)
	}
	
	logDetailf("Identity key loaded successfully")

	logDetailf("Identity key loaded successfully")

	// Configure libp2p options with AutoTLS
	logDetailf("Configuring libp2p host options...")
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
		libp2p.ResourceManager(getResourceManager()),
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
	logDetailf("Creating libp2p host...")
	h, err := libp2p.New(opts...)
	if err != nil {
		logErrorf("Failed to create libp2p host: %v", err)
		panic(err)
	}

	certManager.ProvideHost(h)

	logConnectionf("Host created with PeerID: %s", h.ID())
	
	resources := relayv2.DefaultResources()
	resources.MaxReservations = 256
	_, err = relayv2.New(h, relayv2.WithResources(resources))
	if err != nil {
		logErrorf("Failed to create relay service: %v", err)
		panic(err)
	}
	logDetailf("Relay service initialized")

	// create a new PubSub service using the GossipSub router
	logPubSubf("📡 Initializing PubSub with GossipSub...")
	logPubSubf("📋 Default GossipSub protocols: /meshsub/1.0.0, /meshsub/1.1.0")
	ps, err := pubsub.NewGossipSub(ctx, h)
	if err != nil {
		logErrorf("Failed to create GossipSub: %v", err)
		panic(err)
	}
	logPubSubf("✅ GossipSub initialized successfully")
	
	// Log GossipSub configuration
	logPubSubf("📊 GossipSub router ready for protocol negotiation")

	// Setup detailed connection event handlers with protocol inspection (now that ps is available)
	h.Network().Notify(&network.NotifyBundle{
		ConnectedF: func(n network.Network, c network.Conn) {
			logConnectionf("✅ Connected to peer: %s", c.RemotePeer())
			logConnectionf("   Local addr: %s", c.LocalMultiaddr())
			logConnectionf("   Remote addr: %s", c.RemoteMultiaddr())
			
			// Log protocol negotiation details
			go func() {
				// Give a moment for protocol negotiation to start
				time.Sleep(100 * time.Millisecond)
				
				// Check supported protocols on this connection
				logConnectionf("🔍 Inspecting protocols for peer: %s", c.RemotePeer())
				
				// Get the peer's supported protocols
				protocols, err := h.Peerstore().GetProtocols(c.RemotePeer())
				if err != nil {
					logConnectionf("❌ Failed to get protocols for peer %s: %v", c.RemotePeer(), err)
				} else {
					logConnectionf("📋 Peer %s supports %d protocols:", c.RemotePeer(), len(protocols))
					for i, protocol := range protocols {
						logConnectionf("   %d: %s", i+1, protocol)
						if strings.Contains(string(protocol), "meshsub") || strings.Contains(string(protocol), "gossipsub") {
							logPubSubf("🎯 Found PubSub protocol: %s", protocol)
						}
					}
				}
				
				// Check streams on this connection
				streams := c.GetStreams()
				logConnectionf("📊 Connection has %d active streams:", len(streams))
				for i, stream := range streams {
					protocol := stream.Protocol()
					logConnectionf("   Stream %d: Protocol=%s", i+1, protocol)
					if strings.Contains(string(protocol), "meshsub") || strings.Contains(string(protocol), "gossipsub") {
						logPubSubf("🎯 PubSub stream found: %s", protocol)
					}
				}
				
				// Start monitoring GossipSub handshake
				go monitorGossipSubHandshake(ctx, h, ps, c.RemotePeer())
			}()
		},
		DisconnectedF: func(n network.Network, c network.Conn) {
			logConnectionf("❌ Disconnected from peer: %s", c.RemotePeer())
		},
	})

	// use the nickname from the cli flag, or a default if blank
	nick := *nickFlag
	if len(nick) == 0 {
		nick = defaultNick(h.ID())
	}
	logDetailf("Using nickname: %s", nick)

	// join the chat room
	logPubSubf("Joining chat room...")
	cr, err := JoinChatRoom(ctx, h, ps, nick)
	if err != nil {
		logErrorf("Failed to join chat room: %v", err)
		panic(err)
	}
	SysMsgChan = cr.SysMessages
	logPubSubf("Successfully joined chat room as '%s'", nick)

	// Connect to specified peers
	if len(addrsToConnectTo) > 0 {
		logConnectionf("Connecting to %d specified peer(s)...", len(addrsToConnectTo))
		for i, addr := range addrsToConnectTo {
			logConnectionf("Connecting to peer %d/%d: %s", i+1, len(addrsToConnectTo), addr)
			// convert to a peer.AddrInfo struct
			peerinfo, err := peer.AddrInfoFromString(addr)
			if err != nil {
				logErrorf("Failed to parse multiaddr '%s': %v", addr, err)
				continue
			}
			logConnectionf("Parsed peer info: ID=%s, Addrs=%v", peerinfo.ID, peerinfo.Addrs)

			// connect to the peer
			logConnectionf("Attempting connection to peer: %s", peerinfo.ID)
			if err := h.Connect(ctx, *peerinfo); err != nil {
				logErrorf("Failed to connect to peer %s: %v", peerinfo.ID, err)
				continue
			}
			logConnectionf("✅ Successfully connected to peer: %s", peerinfo.ID)
		}
	} else {
		logDetailf("No peers specified to connect to")
	}

	// Start background monitoring
	go func() {
		ticker := time.NewTicker(time.Second * 30)
		defer ticker.Stop()
		
		// Initial status
		time.Sleep(2 * time.Second) // Give time for initial setup
		logDetailf("=== Initial Status Report ===")
		connectedPeers := h.Network().Peers()
		logDetailf("Connected peers: %d", len(connectedPeers))
		for _, peerID := range connectedPeers {
			conns := h.Network().ConnsToPeer(peerID)
			logDetailf("  - Peer %s (%d connections)", shortID(peerID), len(conns))
			for i, conn := range conns {
				logDetailf("    Conn %d: %s -> %s", i+1, conn.LocalMultiaddr(), conn.RemoteMultiaddr())
			}
		}
		
		// Initial PubSub status
		allPubsubPeers := ps.ListPeers("") 
		logPubSubf("Initial total PubSub peers: %d", len(allPubsubPeers))
		for _, peerID := range allPubsubPeers {
			logPubSubf("  - Initial PubSub peer ID: %s (short: %s)", peerID, shortID(peerID))
		}
		
		// Periodic status updates
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				logDetailf("=== Periodic Status Report ===")
				connectedPeers := h.Network().Peers()
				logDetailf("Connected peers: %d", len(connectedPeers))
				
				// Get all PubSub peers (total)
				allPubsubPeers := ps.ListPeers("") 
				logPubSubf("Total PubSub peers: %d", len(allPubsubPeers))
				for _, peerID := range allPubsubPeers {
					logPubSubf("  - PubSub peer ID: %s (short: %s)", peerID, shortID(peerID))
				}
				
				// Get PubSub peers on specific topic
				pubsubPeers := ps.ListPeers("universal-connectivity")
				logPubSubf("PubSub peers on topic 'universal-connectivity': %d", len(pubsubPeers))
				for _, peerID := range pubsubPeers {
					logPubSubf("  - Topic peer: %s", shortID(peerID))
				}
				
				// Resource manager stats
				rm := h.Network().ResourceManager()
				rm.ViewSystem(
					func(rs network.ResourceScope) error {
						stat := rs.Stat()
						logDetailf("Resource stats - Conns: %d, Streams: %d, Memory: %d", 
							stat.NumConnsInbound+stat.NumConnsOutbound,
							stat.NumStreamsInbound+stat.NumStreamsOutbound,
							stat.Memory)
						return nil
					},
				)
			}
		}
	}()

	logDetailf("PeerID: %s", h.ID().String())
	logDetailf("Short ID: %s", shortID(h.ID()))
	
	logDetailf("=== Listening Addresses ===")
	for i, addr := range h.Addrs() {
		fullAddr := fmt.Sprintf("%s/p2p/%s", addr.String(), h.ID())
		if *headless {
			logger.Infof("Address %d: %s", i+1, fullAddr)
		} else {
			LogMsgf("Address %d: %s", i+1, fullAddr)
		}
		logDetailf("  %d: %s", i+1, fullAddr)
	}

	go func() {
		<-certLoaded
		logDetailf("=== Additional Addresses After Cert Load ===")
		for i, addr := range h.Addrs() {
			fullAddr := fmt.Sprintf("%s/p2p/%s", addr.String(), h.ID())
			if *headless {
				logger.Infof("Post-cert Address %d: %s", i+1, fullAddr)
			} else {
				LogMsgf("Post-cert Address %d: %s", i+1, fullAddr)
			}
			logDetailf("  Post-cert %d: %s", i+1, fullAddr)
		}
	}()

	logDetailf("✅ Go peer initialization complete - ready for connections")

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

// creates and returns a libp2p resource manager with very permissive limits.
// This resource manager is configured with maximum values for most limits to prevent resource constraints
// from blocking connections and streams.
//
// Note: Using maximum values for limits could lead to resource exhaustion.
func getResourceManager() network.ResourceManager {
	baseLimits := rcmgr.BaseLimit{
		Streams:         math.MaxInt,
		StreamsInbound:  math.MaxInt,
		StreamsOutbound: math.MaxInt,
		Conns:           math.MaxInt,
		ConnsInbound:    1000,
		ConnsOutbound:   math.MaxInt,
		FD:              math.MaxInt,
		Memory:          math.MaxInt64,
	}

	scl := rcmgr.ScalingLimitConfig{
		SystemBaseLimit:       baseLimits,
		TransientBaseLimit:    baseLimits,
		ServiceBaseLimit:      baseLimits,
		ServicePeerBaseLimit:  baseLimits,
		ProtocolBaseLimit:     baseLimits,
		ProtocolPeerBaseLimit: baseLimits,
		PeerBaseLimit:         baseLimits,
		ConnBaseLimit:         baseLimits,
		StreamBaseLimit:       baseLimits,
	}
	cl := scl.Scale(0, 0)
	rcmgr, err := rcmgr.NewResourceManager(rcmgr.NewFixedLimiter(cl))
	if err != nil {
		panic(err)
	}
	return rcmgr
}

// checkGossipSubMeshStatus checks the GossipSub mesh status for a specific peer
func checkGossipSubMeshStatus(ps *pubsub.PubSub, peerID peer.ID, topic string) {
	logPubSubf("🔍 Checking GossipSub mesh status for peer: %s", peerID)
	logPubSubf("🔍 Checking topic: %s", topic)
	
	// Get all peers in the pubsub network
	peers := ps.ListPeers("")
	logPubSubf("📡 Total PubSub peers in network: %d", len(peers))
	
	for i, p := range peers {
		logPubSubf("  Peer %d: %s", i+1, p)
		if p == peerID {
			logPubSubf("  ✅ Found target peer in PubSub network")
		}
	}
	
	// Get peers for the specific topic
	topicPeers := ps.ListPeers(topic)
	logPubSubf("📡 Peers subscribed to topic '%s': %d", topic, len(topicPeers))
	
	foundInTopic := false
	for i, p := range topicPeers {
		logPubSubf("  Topic peer %d: %s", i+1, p)
		if p == peerID {
			logPubSubf("  ✅ Target peer is subscribed to topic!")
			foundInTopic = true
		}
	}
	
	if !foundInTopic {
		logPubSubf("  ❌ Target peer is NOT subscribed to topic")
		logPubSubf("  🔧 Possible reasons:")
		logPubSubf("     1. Peer hasn't completed GossipSub handshake")
		logPubSubf("     2. Peer hasn't subscribed to the topic yet")  
		logPubSubf("     3. GossipSub mesh formation still in progress")
	}
}

// monitorGossipSubHandshake monitors the GossipSub handshake process
func monitorGossipSubHandshake(ctx context.Context, h host.Host, ps *pubsub.PubSub, peerID peer.ID) {
	logPubSubf("🤝 Starting GossipSub handshake monitor for peer: %s", peerID)
	
	// Monitor for up to 30 seconds
	timeout := time.After(30 * time.Second)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-timeout:
			logPubSubf("⏰ GossipSub handshake monitor timeout for peer: %s", peerID)
			return
		case <-ctx.Done():
			return
		case <-ticker.C:
			// Check if peer appears in PubSub mesh
			peers := ps.ListPeers("")
			for _, p := range peers {
				if p == peerID {
					logPubSubf("🎉 Peer %s successfully joined PubSub mesh!", peerID)
					
					// Check topic subscription
					time.Sleep(1 * time.Second)
					checkGossipSubMeshStatus(ps, peerID, "universal-connectivity")
					return
				}
			}
			logPubSubf("⏳ Still waiting for peer %s to join PubSub mesh...", peerID)
		}
	}
}
