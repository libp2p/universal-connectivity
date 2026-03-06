{.push raises: [Exception].}

import tables, deques, strutils, os, streams
import std/sets

import libp2p, chronos, cligen, chronicles
import libp2p/protocols/kademlia
from libp2p/protocols/pubsub/rpc/message import Message

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

proc seedKadRoutingTable(kad: KadDHT, switch: Switch) {.raises: [].} =
  var peers: seq[(PeerId, seq[MultiAddress])]
  for peerId, addrs in switch.peerStore[AddressBook].book.pairs:
    if peerId == switch.peerInfo.peerId or addrs.len == 0:
      continue
    peers.add((peerId, addrs))

  if peers.len > 0:
    kad.updatePeers(peers)

proc discoverPeersWithKad(switch: Switch, kad: KadDHT, room: string) {.
    async: (raises: [CancelledError])
.} =
  let roomKey = roomToKadKey(room)
  if roomKey.isNone():
    return

  while true:
    seedKadRoutingTable(kad, switch)

    # announce ourselves as a provider for this room and query for other providers
    await kad.addProvider(roomKey.get())
    let providers = await kad.getProviders(roomKey.get())

    for provider in providers.items:
      let peerId = PeerId.init(provider.id).valueOr:
        continue
      if peerId == switch.peerInfo.peerId or switch.isConnected(peerId):
        continue
      if provider.addrs.len == 0:
        continue

      try:
        await switch.connect(peerId, provider.addrs)
        info "Connected to peer via Kad-DHT", peerId = $peerId
      except CancelledError as exc:
        raise exc
      except DialFailedError as exc:
        debug "Failed to connect to discovered peer", peerId = $peerId, description = exc.msg

    await sleepAsync(DiscoveryInterval)

proc start(
    addrs: Opt[MultiAddress], headless: bool, room: string, port: int
) {.async: (raises: [CancelledError]).} =
  # Handle Ctrl+C
  setControlCHook(cleanup)

  # Pick the correct string type for your Chronicles version
  when declared(OutStr):
    type WriterStr = OutStr
  else:
    type WriterStr = LogOutputStr

  # Early (bootstrap) writer: mirror logs to stdout so nothing is dropped
  defaultChroniclesStream.output.writer =
    proc (lvl: LogLevel, rec: WriterStr) {.closure, gcsafe, raises: [].} =
      let s = cast[string](rec)
      try:
        for line in s.splitLines():
          stdout.writeLine(line)
        stdout.flushFile()
      except IOError:
        discard


  var rng = newRng()

  let switch =
    try:
      SwitchBuilder
      .new()
      .withRng(rng)
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
  let kad = KadDHT.new(switch)

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

  # wait so that gossipsub can form mesh
  await sleepAsync(3.seconds)

  # topic handlers
  # chat and file handlers actually need to be validators instead of regular handlers
  # validators allow us to get information about which peer sent a message
  let onChatMsg = proc(
      topic: string, msg: Message
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
      topic: string, msg: Message
  ): Future[ValidationResult] {.async, gcsafe.} =
    let fileId = sanitizeFileId(cast[string](msg.data))
    # this will only work if we're connected to `fromPeer` (since we don't have kad-dht)
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
  gossip.subscribe(ChatFileTopic, nil)
  gossip.addValidator(ChatFileTopic, onNewFile)

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
  for peerId in switch.peerStore[AddressBook].book.keys:
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
    waitFor start(addrs, headless, room, port)
  except CancelledError:
    echo "Operation cancelled"

when isMainModule:
  dispatch cli,
    help = {
      "connect": "full multiaddress (with /p2p/ peerId) of the node to connect to",
      "room": "Room name",
      "port": "TCP listen port",
      "headless": "No UI, can only receive messages",
    }
