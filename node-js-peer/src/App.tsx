import React from 'react'
import ReactCurse, { Banner, useSize } from 'react-curse'
import { AppWrapper } from './context/index.js'
import { PeerList } from './components/peer-list.js'
import { layout } from './index.js'
import { SendMessage } from './components/send-message.js'
import Messages from './components/messages.js'

const App = () => {
  const dims = useSize()

  let title = 'Universal Connectivity Node.js Peer'

  if (dims.width < 140) {
    title = 'UC Node.js Peer'
  }

  if (dims.width < 50) {
    dims.width = 50
  }

  if (dims.height < 30) {
    dims.height = 30
  }

  return (
    <>
      <Banner>{title}</Banner>
      <Messages
        x={0}
        y={layout.bannerHeight}
        width={dims.width - layout.peerListWidth - layout.margin}
        height={dims.height - layout.bannerHeight - layout.inputHeight - layout.margin - layout.margin}
      />
      <PeerList
        x={dims.width - layout.peerListWidth}
        y={layout.bannerHeight}
        width={layout.peerListWidth - layout.margin}
        height={dims.height - layout.bannerHeight - layout.inputHeight - layout.margin - layout.margin}
      />
      <SendMessage
        x={0}
        y={dims.height - layout.inputHeight - layout.margin}
        width={dims.width - layout.margin}
        height={layout.inputHeight}
      />
    </>
  )
}

ReactCurse.render((
  <AppWrapper>
    <App />
  </AppWrapper>
))
