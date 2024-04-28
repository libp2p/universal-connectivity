import { useEffect } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { P2P_PING_INTERVAL_MS } from '@/lib/constants/'

export const P2PPinger = () => {
  const { libp2p } = useLibp2pContext()

  useEffect(() => {
    const interval = setInterval(() => {
      const pingConnections = async () => {
        if (!libp2p) {
          return
        }

        const connections = libp2p.getConnections()

        const pingPromises = connections.map(async (conn) => {
          return await libp2p.services.ping
            .ping(conn.remotePeer)
            .then((rtt) => {
              console.log(`${conn.remotePeer}: ping rtt ${rtt}ms`)
            })
            .catch(async (err) => {
              if (err.message === 'protocol selection failed') {
                // might be relay / go peer / rust peer etc that doesn't support ping
                console.log(`${conn.remotePeer}: ping protocol not supported`)

                return
              }

              if (
                err.message.startsWith(
                  `Too many outbound protocol streams for protocol`,
                )
              ) {
                console.log(`${conn.remotePeer}: too many pings in flight`)
                return
              }

              console.log(
                `${conn.remotePeer} ping failed - hanging up connection`,
                err,
              )

              await libp2p.hangUp(conn.remotePeer)

              throw err // rethrow if you need to propagate error further or handle it differently
            })
        })

        try {
          await Promise.all(pingPromises)
        } catch (err) {
          // handle errors from failed pings if necessary
          console.error('One or more pings failed:', err)
        }
      }

      pingConnections()
    }, P2P_PING_INTERVAL_MS)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p])

  return <></>
}
