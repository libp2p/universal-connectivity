import os
import libp2p, chronos, chronicles, stew/byteutils

const
  MaxFileSize: int = 1024 # 1KiB
  MaxFileIdSize: int = 1024 # 1KiB
  FileExchangeCodec*: string = "/universal-connectivity-file/1"

type FileExchange* = ref object of LPProtocol

proc new*(T: typedesc[FileExchange]): T =
  proc handle(conn: Connection, proto: string) {.async: (raises: [CancelledError]).} =
    try:
      let fileId = string.fromBytes(await conn.readLp(MaxFileIdSize))
      # filename is /tmp/{fileid}
      let filename = getTempDir().joinPath(fileId)
      if filename.fileExists:
        let fileContent = cast[seq[byte]](readFile(filename))
        await conn.writeLp(fileContent)
    except CancelledError as e:
      raise e
    except CatchableError as e:
      error "Exception in handler", error = e.msg
    finally:
      await conn.close()

  return T.new(codecs = @[FileExchangeCodec], handler = handle)

proc requestFile*(
    p: FileExchange, conn: Connection, fileId: string
): Future[seq[byte]] {.async.} =
  await conn.writeLp(cast[seq[byte]](fileId))
  await conn.readLp(MaxFileSize)
