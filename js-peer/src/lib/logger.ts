import { prefixLogger } from '@libp2p/logger'

const prefix = `ui`

export const { forComponent } = prefixLogger(prefix)
