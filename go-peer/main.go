package main

import (
	"context"
	"crypto/tls"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"sync"
	"time"

	"github.com/libp2p/go-libp2p"
	dht "github.com/libp2p/go-libp2p-kad-dht"
	pubsub "github.com/libp2p/go-libp2p-pubsub"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/p2p/discovery/mdns"
	"github.com/libp2p/go-libp2p/p2p/discovery/routing"
	discovery "github.com/libp2p/go-libp2p/p2p/discovery/util"
	quicTransport "github.com/libp2p/go-libp2p/p2p/transport/quic"
	ws "github.com/libp2p/go-libp2p/p2p/transport/websocket"
	webtransport "github.com/libp2p/go-libp2p/p2p/transport/webtransport"
	"github.com/multiformats/go-multiaddr"
)

// DiscoveryInterval is how often we re-publish our mDNS records.
const DiscoveryInterval = time.Hour

// DiscoveryServiceTag is used in our mDNS advertisements to discover other chat peers.
const DiscoveryServiceTag = "universal-connectivity"

var SysMsgChan chan *ChatMessage

// Borrowed from https://medium.com/rahasak/libp2p-pubsub-peer-discovery-with-kademlia-dht-c8b131550ac7
// NewDHT attempts to connect to a bunch of bootstrap peers and returns a new DHT.
// If you don't have any bootstrapPeers, you can use dht.DefaultBootstrapPeers or an empty list.
func NewDHT(ctx context.Context, host host.Host, bootstrapPeers []multiaddr.Multiaddr) (*dht.IpfsDHT, error) {
	var options []dht.Option

	// if no bootstrap peers give this peer act as a bootstraping node
	// other peers can use this peers ipfs address for peer discovery via dht
	if len(bootstrapPeers) == 0 {
		options = append(options, dht.Mode(dht.ModeServer))
	}

	options = append(options, dht.ProtocolPrefix("/universal-connectivity/lan"))

	kdht, err := dht.New(ctx, host, options...)
	if err != nil {
		return nil, err
	}

	if err = kdht.Bootstrap(ctx); err != nil {
		return nil, err
	}

	var wg sync.WaitGroup
	for _, peerAddr := range bootstrapPeers {
		peerinfo, _ := peer.AddrInfoFromP2pAddr(peerAddr)

		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := host.Connect(ctx, *peerinfo); err != nil {
				LogMsgf("Error while connecting to node %q: %-v", peerinfo, err)
			} else {
				LogMsgf("Connection established with bootstrap node: %q", *peerinfo)
			}
		}()
	}
	wg.Wait()

	return kdht, nil
}

// Borrowed from https://medium.com/rahasak/libp2p-pubsub-peer-discovery-with-kademlia-dht-c8b131550ac7
func Discover(ctx context.Context, h host.Host, dht *dht.IpfsDHT, rendezvous string) {
	routingDiscovery := routing.NewRoutingDiscovery(dht)

	discovery.Advertise(ctx, routingDiscovery, rendezvous)

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:

			peers, err := discovery.FindPeers(ctx, routingDiscovery, rendezvous)
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
					LogMsgf("Connected to peer %s", p.ID.Pretty())
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
	roomFlag := flag.String("room", "universal-connectivity", "name of chat room to join")
	idPath := flag.String("identity", "identity.key", "path to the private key (PeerID) file")
	certPath := flag.String("tls-cert-path", "", "path to the tls cert file (for websockets)")
	keyPath := flag.String("tls-key-path", "", "path to the tls key file (for websockets")
	useLogger := flag.Bool("logger", false, "write logs to file")
	headless := flag.Bool("headless", false, "run without chat UI")

	var addrsToConnectTo stringSlice
	flag.Var(&addrsToConnectTo, "connect", "address to connect to (can be used multiple times)")

	flag.Parse()

	if *useLogger {
		f, err := os.OpenFile("log.txt", os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
		if err != nil {
			log.Println("failed to open log file", err)
			log.SetOutput(ioutil.Discard)
		} else {
			defer f.Close()
			log.SetOutput(f)
		}
	} else {
		log.SetOutput(ioutil.Discard)
	}

	ctx := context.Background()

	// load our private key to generate the same peerID each time
	privk, err := LoadIdentity(*idPath)
	if err != nil {
		panic(err)
	}

	// TLS stuff
	var opts []libp2p.Option

	if *certPath != "" && *keyPath != "" {
		certs := make([]tls.Certificate, 1)
		certs[0], err = tls.LoadX509KeyPair(*certPath, *keyPath)
		if err != nil {
			panic(err)
		}

		opts = append(opts,
			libp2p.Transport(ws.New, ws.WithTLSConfig(&tls.Config{Certificates: certs})),
			libp2p.ListenAddrStrings("/ip4/0.0.0.0/tcp/0/ws"),
		)
	}

	opts = append(opts,
		libp2p.Identity(privk),
		libp2p.Transport(quicTransport.NewTransport),
		libp2p.Transport(webtransport.New),
		libp2p.ListenAddrStrings("/ip4/0.0.0.0/udp/9095/quic-v1", "/ip4/0.0.0.0/udp/9095/quic-v1/webtransport"),
	)

	// create a new libp2p Host with lots of options
	h, err := libp2p.New(opts...)
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

	// join the room from the cli flag, or the flag default
	room := *roomFlag

	// join the chat room
	cr, err := JoinChatRoom(ctx, h, ps, nick, room)
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
	go Discover(ctx, h, dht, "universal-connectivity")

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
			fmt.Printf("Listening on: %s/p2p/%s\n", addr.String(), h.ID())
		} else {
			LogMsgf("Listening on: %s/p2p/%s", addr.String(), h.ID())
		}
	}

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
	pretty := p.Pretty()
	return pretty[len(pretty)-8:]
}

// discoveryNotifee gets notified when we find a new peer via mDNS discovery
type discoveryNotifee struct {
	h host.Host
}

// HandlePeerFound connects to peers discovered via mDNS. Once they're connected,
// the PubSub system will automatically start interacting with them if they also
// support PubSub.
func (n *discoveryNotifee) HandlePeerFound(pi peer.AddrInfo) {
	LogMsgf("discovered new peer %s", pi.ID.Pretty())
	err := n.h.Connect(context.Background(), pi)
	if err != nil {
		LogMsgf("error connecting to peer %s: %s", pi.ID.Pretty(), err)
	}
}

// setupDiscovery creates an mDNS discovery service and attaches it to the libp2p Host.
// This lets us automatically discover peers on the same LAN and connect to them.
func setupDiscovery(h host.Host) error {
	// setup mDNS discovery to find local peers
	s := mdns.NewMdnsService(h, DiscoveryServiceTag, &discoveryNotifee{h: h})
	return s.Start()
}
