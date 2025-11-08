# Package

version       = "0.1.0"
author        = "Status Research & Development GmbH"
description   = "universal-connectivity nim peer"
license       = "MIT"
srcDir        = "src"
bin           = @["nim_peer"]


# Dependencies

requires "nim >= 2.2.0", "nimwave", "chronos", "chronicles", "libp2p", "illwill", "cligen", "stew"
