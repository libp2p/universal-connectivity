import Blockies from 'react-18-blockies'
import { DocumentIcon } from '@heroicons/react/24/outline'
import type { ChatMessage } from '../api/client'

interface MessageItemProps {
  message: ChatMessage
  isOwn: boolean
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function MessageItem({ message, isOwn }: MessageItemProps) {
  const isFile = message.type === 'file_message' || message.type === 'file_shared'

  return (
    <div className={`flex items-end gap-2 ${isOwn ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className="flex-shrink-0 mb-1">
        <Blockies
          seed={message.sender_id}
          size={8}
          scale={4}
          className="rounded-full"
        />
      </div>

      <div className={`max-w-[70%] flex flex-col ${isOwn ? 'items-end' : 'items-start'}`}>
        {/* Sender name + time */}
        <div className={`flex items-center gap-1.5 mb-0.5 ${isOwn ? 'flex-row-reverse' : ''}`}>
          <span className="text-xs font-medium text-gray-600">{message.sender_nick}</span>
          <span className="text-xs text-gray-400">{formatTime(message.timestamp)}</span>
        </div>

        {/* Bubble */}
        {isFile ? (
          <div
            className={`flex items-center gap-2 rounded-2xl px-4 py-2 text-sm ${
              isOwn
                ? 'bg-indigo-600 text-white rounded-br-sm'
                : 'bg-gray-100 text-gray-900 rounded-bl-sm'
            }`}
          >
            <DocumentIcon className="h-4 w-4 flex-shrink-0" />
            <div className="min-w-0">
              <p className="font-medium truncate">{message.file_name ?? 'file'}</p>
              {message.file_size != null && (
                <p className={`text-xs ${isOwn ? 'text-indigo-200' : 'text-gray-500'}`}>
                  {(message.file_size / 1024).toFixed(1)} KB
                </p>
              )}
            </div>
          </div>
        ) : (
          <div
            className={`rounded-2xl px-4 py-2 text-sm break-words ${
              isOwn
                ? 'bg-indigo-600 text-white rounded-br-sm'
                : 'bg-gray-100 text-gray-900 rounded-bl-sm'
            }`}
          >
            {message.message}
          </div>
        )}
      </div>
    </div>
  )
}
