import { prefixLogger, enable } from '@libp2p/logger'

const prefix = `ui`

export const { forComponent } = prefixLogger(prefix)
export { enable }
