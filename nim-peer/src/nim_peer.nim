{.push raises: [Exception].}

import tables, deques, strutils, os, streams
import std/sets

import libp2p, chronos, cligen, chronicles
import libp2p/protocols/kademlia
import libp2p/protocols/pubsub/rpc/message as pubsub_message
import libp2p/nameresolving/dnsresolver
import libp2p/nameresolving/nameresolver

from illwave as iw import nil, `[]`, `[]=`, `==`, width, height
from terminal import nil

import ./ui/root
import ./utils
import ./file_exchange

const
  KeyFile: string = "local.key"
  PeerIdFile: string = "local.peerid"
  MaxKeyLen: int = 4096
  ListenPort: int = 9093
  DiscoveryInterval = 10.seconds
  KadBootstrapPeerAddrs =
    ["/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"]

proc cleanup() {.noconv: (raises: []).} =
  try:
    iw.deinit()
  except:
    discard
  try:
    terminal.resetAttributes()
    terminal.showCursor()
    # Clear screen and move cursor to top-left
    stdout.write("\e[2J\e[H") # ANSI escape: clear screen & home
    stdout.flushFile()
    quit(130) # SIGINT conventional exit code
  except IOError as exc:
    echo "Unexpected error: " & exc.msg
    quit(1)

proc readKeyFile(
    filename: string
): PrivateKey {.raises: [OSError, IOError, ResultError[crypto.CryptoError]].} =
  let size = getFileSize(filename)

  if size == 0:
    raise newException(OSError, "Empty key file")

  var buf: seq[byte]
  buf.setLen(size)

  var fs = openFileStream(filename, fmRead)
  defer:
    fs.close()

  discard fs.readData(buf[0].addr, size.int)
  PrivateKey.init(buf).tryGet()

proc writeKeyFile(
    filename: string, key: PrivateKey
) {.raises: [OSError, IOError, ResultError[crypto.CryptoError]].} =
  var fs = openFileStream(filename, fmWrite)
  defer:
    fs.close()

  let buf = key.getBytes().tryGet()
  fs.writeData(buf[0].addr, buf.len)

proc loadOrCreateKey(rng: var HmacDrbgContext): PrivateKey =
  if fileExists(KeyFile):
    try:
      return readKeyFile(KeyFile)
    except:
      discard # overwrite file
  try:
    let k = PrivateKey.random(rng).tryGet()
    writeKeyFile(KeyFile, k)
    k
  except:
    echo "Could not create new key"
    quit(1)

proc roomToKadKey(room: string): Opt[Key] {.raises: [].} =
  var roomBytes = newSeq[byte](room.len)
  for i, ch in room:
    roomBytes[i] = byte(ord(ch))
  let digest = MultiHash.digest("sha2-256", roomBytes).valueOr:
    error "Could not derive Kad-DHT key for room", room = room, description = error
    return Opt.none(Key)
  Opt.some(digest.toKey())

proc kadBootstrapNodes(
    resolver: DnsResolver
): Future[seq[(PeerId, seq[MultiAddress])]] {.async.} =
  const PeerIdTag = "/p2p/"

  for addr in KadBootstrapPeerAddrs:
    let tagPos = addr.rfind(PeerIdTag)
    if tagPos < 0:
      error "Missing /p2p/ segment", address = addr
      continue

    let peerIdStr = addr[tagPos + PeerIdTag.len .. ^1]
    let peerId = PeerId.init(peerIdStr).valueOr:
      error "Invalid peer id", peerId = peerIdStr
      continue

    let baseAddr = addr[0 ..< tagPos]

    let maddr = MultiAddress.init(baseAddr).valueOr:
      error "Invalid multiaddr", address = baseAddr
      continue

    result.add((peerId, @[maddr]))

proc discoverPeersWithKad(
    switch: Switch, kad: KadDHT, room: string
) {.async: (raises: []).} =
  let roomKey = roomToKadKey(room).valueOr:
    error "Unable to convert room to kad key"
    return

  try:
    while true:
      # announce ourselves as a provider for this room and query for other providers
      await kad.addProvider(roomKey)
      var providers: HashSet[Provider]
      try:
        providers = await kad.getProviders(roomKey)
      except LPStreamError as exc:
        debug "Kad provider lookup stream error", description = exc.msg
        await sleepAsync(DiscoveryInterval)
        continue

      for provider in providers.items:
        let peerId = PeerId.init(provider.id).valueOr:
          continue
        if peerId == switch.peerInfo.peerId or switch.isConnected(peerId):
          continue
        if provider.addrs.len == 0:
          continue

        try:
          await switch.connect(peerId, provider.addrs)
          info "Kad Connected to peer via Kad-DHT", peerId = $peerId
        except DialFailedError as exc:
          debug "Failed to connect to discovered peer",
            peerId = $peerId, description = exc.msg

      await sleepAsync(DiscoveryInterval)
  except CancelledError:
    discard

proc start(
    addrs: Opt[MultiAddress], headless: bool, room: string, port: int
) {.async.} =
  # Handle Ctrl+C
  setControlCHook(cleanup)

  # Pick the correct string type for your Chronicles version
  when declared(OutStr):
    type WriterStr = OutStr
  else:
    type WriterStr = LogOutputStr

  # Early (bootstrap) writer: mirror logs to stdout so nothing is dropped
  defaultChroniclesStream.output.writer = proc(
      lvl: LogLevel, rec: WriterStr
  ) {.closure, gcsafe, raises: [].} =
    let s = cast[string](rec)
    try:
      for line in s.splitLines():
        stdout.writeLine(line)
      stdout.flushFile()
    except IOError:
      discard

  var rng = newRng()
  let nameResolver = DnsResolver.new(@[initTAddress("1.1.1.1:53")])

  let switch =
    try:
      SwitchBuilder
      .new()
      .withRng(rng)
      .withNameResolver(nameResolver)
      .withTcpTransport()
      .withAddresses(@[MultiAddress.init("/ip4/0.0.0.0/tcp/" & $port).tryGet()])
      .withYamux()
      .withNoise()
      .withPrivateKey(loadOrCreateKey(rng[]))
      .build()
    except LPError as exc:
      echo "Could not start switch: " & $exc.msg
      quit(1)
    except Exception as exc:
      echo "Could not start switch: " & $exc.msg
      quit(1)

  try:
    writeFile(PeerIdFile, $switch.peerInfo.peerId)
  except IOError as exc:
    error "Could not write PeerId to file", description = exc.msg

  let (gossip, fileExchange) =
    try:
      (GossipSub.init(switch = switch, triggerSelf = true), FileExchange.new())
    except InitializationError as exc:
      echo "Could not initialize gossipsub: " & $exc.msg
      quit(1)
  let kad = KadDHT.new(switch, bootstrapNodes = await kadBootstrapNodes(nameResolver))

  try:
    switch.mount(kad)
    switch.mount(gossip)
    switch.mount(fileExchange)
    await switch.start()
  except LPError as exc:
    echo "Could start switch: " & $exc.msg

  info "Started switch", peerId = $switch.peerInfo.peerId

  let
    recvQ = newAsyncQueue[string]()
    peerQ = newAsyncQueue[(PeerId, PeerEventKind)]()
    systemQ = newAsyncQueue[string]()

  # if --connect was specified, connect to peer
  if addrs.isSome():
    try:
      discard await switch.connect(addrs.get())
    except Exception as exc:
      error "Connection error", description = exc.msg

  asyncSpawn discoverPeersWithKad(switch, kad, room)

  # topic handlers
  # chat and file handlers actually need to be validators instead of regular handlers
  # validators allow us to get information about which peer sent a message
  let onChatMsg = proc(
      topic: string, msg: pubsub_message.Message
  ): Future[ValidationResult] {.async, gcsafe.} =
    let strMsg = cast[string](msg.data)
    await recvQ.put(shortPeerId(msg.fromPeer) & ": " & strMsg)
    await systemQ.put("Received message")
    await systemQ.put("    Source: " & $msg.fromPeer)
    await systemQ.put("    Topic: " & $topic)
    await systemQ.put("    Seqno: " & $seqnoToUint64(msg.seqno))
    await systemQ.put(" ") # empty line
    return ValidationResult.Accept

  # when a new file is announced, download it
  let onNewFile = proc(
      topic: string, msg: pubsub_message.Message
  ): Future[ValidationResult] {.async, gcsafe.} =
    let fileId = sanitizeFileId(cast[string](msg.data))
    # File transfer still requires a direct stream to the announcing peer.
    let conn = await switch.dial(msg.fromPeer, FileExchangeCodec)
    let filePath = getTempDir() / fileId
    let fileContents = await fileExchange.requestFile(conn, fileId)
    writeFile(filePath, fileContents)
    await conn.close()
    # Save file in /tmp/fileId
    await systemQ.put("Downloaded file to " & filePath)
    await systemQ.put(" ") # empty line
    return ValidationResult.Accept

  # when a new peer is announced
  let onNewPeer = proc(topic: string, data: seq[byte]) {.async, gcsafe.} =
    let peerId = PeerId.init(data).valueOr:
      error "Could not parse PeerId from data", data = $data
      return
    await peerQ.put((peerId, PeerEventKind.Joined))

  # register validators and handlers

  # receive chat messages
  gossip.subscribe(room, nil)
  gossip.addValidator(room, onChatMsg)

  # receive files offerings
  gossip.subscribe(FileChatTopic, nil)
  gossip.addValidator(FileChatTopic, onNewFile)

  # receive newly connected peers through gossipsub
  gossip.subscribe(PeerDiscoveryTopic, onNewPeer)

  let onPeerJoined = proc(
      peer: PeerId, peerEvent: PeerEvent
  ) {.gcsafe, async: (raises: [CancelledError]).} =
    await peerQ.put((peer, PeerEventKind.Joined))

  let onPeerLeft = proc(
      peer: PeerId, peerEvent: PeerEvent
  ) {.gcsafe, async: (raises: [CancelledError]).} =
    await peerQ.put((peer, PeerEventKind.Left))

  # receive newly connected peers through direct connections
  switch.addPeerEventHandler(onPeerJoined, PeerEventKind.Joined)
  switch.addPeerEventHandler(onPeerLeft, PeerEventKind.Left)

  # add already connected peers
  for peerId in switch.connectedPeers(Direction.Out):
    await peerQ.put((peerId, PeerEventKind.Joined))

  for peerId in switch.connectedPeers(Direction.In):
    await peerQ.put((peerId, PeerEventKind.Joined))

  if headless:
    runForever()
  else:
    try:
      await runUI(gossip, room, recvQ, peerQ, systemQ, switch.peerInfo.peerId)
    except Exception as exc:
      error "Unexpected error", description = exc.msg
    finally:
      if switch != nil:
        await switch.stop()
      try:
        cleanup()
      except:
        discard

proc cli(connect = "", room = ChatTopic, port = ListenPort, headless = false) =
  var addrs = Opt.none(MultiAddress)
  if connect.len > 0:
    addrs = Opt.some(MultiAddress.init(connect).get())
  try:
    waitFor noCancel(start(addrs, headless, room, port))
  except CatchableError as exc:
    echo "Operation failed: " & exc.msg

when isMainModule:
  dispatch cli,
    help = {
      "connect": "full multiaddress (with /p2p/ peerId) of the node to connect to",
      "room": "Room name",
      "port": "TCP listen port",
      "headless": "No UI, can only receive messages",
    }
