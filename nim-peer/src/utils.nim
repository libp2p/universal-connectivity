import strutils

import libp2p

const
  ChatTopic*: string = "universal-connectivity"
  ChatFileTopic*: string = "universal-connectivity-file"
  PeerDiscoveryTopic*: string = "universal-connectivity-browser-peer-discovery"

const SanitizationRules = [
  ({'\0' .. '\31'}, ' '), # Control chars -> space
  ({'"'}, '\''), # Double quote -> single quote
  ({'/', '\\', ':', '|'}, '-'), # Slash, backslash, colon, pipe -> dash
  ({'*', '?', '<', '>'}, '_'), # Asterisk, question, angle brackets -> underscore
]

proc shortPeerId*(peerId: PeerId): string {.raises: [ValueError].} =
  let strPeerId = $peerId
  if strPeerId.len < 7:
    raise newException(ValueError, "PeerId too short")
  strPeerId[^7 ..^ 1]

proc sanitizeFileId*(fileId: string): string =
  ## Sanitize a filename for Windows, macOS, and Linux
  result = fileId
  for (chars, replacement) in SanitizationRules:
    for ch in chars:
      result = result.multiReplace(($ch, $replacement))
  result = result.strip()
  # Avoid reserved Windows filenames (CON, PRN, AUX, NUL, COM1..COM9, LPT1..LPT9)
  var reserved = @["CON", "PRN", "AUX", "NUL"]
  for i in 1 .. 9:
    reserved.add("COM" & $i)
    reserved.add("LPT" & $i)
  if result.toUpperAscii() in reserved:
    result = "_" & result
  # Avoid empty filenames
  if result.len == 0:
    result = "_"

proc seqnoToUint64*(bytes: seq[byte]): uint64 =
  if bytes.len != 8:
    return 0
  var seqno: uint64 = 0
  for i in 0 ..< 8:
    seqno = seqno or (uint64(bytes[i]) shl (8 * (7 - i)))
  seqno
