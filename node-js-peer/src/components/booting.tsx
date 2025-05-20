import React from 'react'
import { Text } from 'react-curse'

interface Props {
  error?: string
}

export function Booting({ error }: Props) {
  if (error) {
    return (
      <Text>Failed to start - {error}</Text>
    )
  }

  return (
    <Text>...libp2p is starting</Text>
  )
}
