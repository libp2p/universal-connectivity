import React, { useEffect, useRef } from 'react'
import { useCallback } from 'react'

interface Props {
  setInput: (input: string) => void
  input: string
  sendMessage: () => void
  isDisabled: boolean
}

export const TextInput = ({
  sendMessage,
  setInput,
  input,
  isDisabled = false,
}: Props) => {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setInput(e.target.value)
    },
    [setInput],
  )

  const handleKeyUp = useCallback(
    async (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== 'Enter') {
        return
      }

      sendMessage()
    },
    [sendMessage],
  )

  useEffect(() => {
    // Check if the input is enabled and if the ref is attached
    if (!isDisabled && inputRef.current) {
      // Focus the input if it is enabled
      inputRef.current.focus()
    }
  }, [isDisabled])

  return (
    <input
      ref={inputRef}
      value={input}
      onKeyUp={handleKeyUp}
      onChange={handleInput}
      type="text"
      placeholder="Message"
      className="block w-full py-2 pl-4 mx-3 bg-gray-100 rounded-full outline-none focus:text-gray-700"
      name="message"
      required
      disabled={isDisabled}
    />
  )
}
