import { useCallback } from "react"

interface Props {
  setInput: (input: string) => void
  input: string
  sendMessage: () => void
}

export const TextInput = ({ sendMessage, setInput, input }: Props) => {
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

  return (
    <input
      value={input}
      onKeyUp={handleKeyUp}
      onChange={handleInput}
      type="text"
      placeholder="Message"
      className="block w-full py-2 pl-4 mx-3 bg-gray-100 rounded-full outline-none focus:text-gray-700"
      name="message"
      required
    />
  )
}
