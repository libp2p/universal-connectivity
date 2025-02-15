import { forComponent } from './logger'

const log = forComponent('message-store')
const DB_NAME = 'universal-connectivity'
const DB_VERSION = 1

export interface StoredMessage {
  hash: string
  content: any // matches existing message structure
}

export interface MessageHistoryEntry {
  timestamp: number
  topic: string
  messageHash: string
}

class MessageStore {
  private db: IDBDatabase | null = null

  async init() {
    if (this.db) return

    return new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onerror = () => {
        log('Error opening database:', request.error)
        reject(request.error)
      }

      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result

        // Store for actual message content
        if (!db.objectStoreNames.contains('messages')) {
          const messageStore = db.createObjectStore('messages', { keyPath: 'hash' })
          messageStore.createIndex('hash', 'hash', { unique: true })
        }

        // Store for topic-based message history
        if (!db.objectStoreNames.contains('messageHistory')) {
          const historyStore = db.createObjectStore('messageHistory', { keyPath: 'id', autoIncrement: true })
          historyStore.createIndex('topic', 'topic')
          historyStore.createIndex('timestamp', 'timestamp')
          historyStore.createIndex('topic_timestamp', ['topic', 'timestamp'])
        }
      }
    })
  }

  async storeMessage(topic: string, message: any): Promise<void> {
    if (!this.db) await this.init()

    // Generate hash from message content
    const msgBuffer = new TextEncoder().encode(JSON.stringify(message))
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(['messages', 'messageHistory'], 'readwrite')

      // Store the message
      const messageStore = tx.objectStore('messages')
      messageStore.put({ hash, content: message })

      // Store the history entry
      const historyStore = tx.objectStore('messageHistory')
      historyStore.put({
        timestamp: message.receivedAt,
        topic,
        messageHash: hash
      })

      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  }

  async getMessagesByTopic(topic: string, limit = 50): Promise<any[]> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(['messages', 'messageHistory'], 'readonly')
      const historyStore = tx.objectStore('messageHistory')
      const messageStore = tx.objectStore('messages')
      
      const index = historyStore.index('topic_timestamp')
      const messages: any[] = []

      // Get messages for topic, ordered by timestamp descending
      const request = index.openCursor([topic], 'prev')

      request.onsuccess = async () => {
        const cursor = request.result
        if (cursor && messages.length < limit) {
          // Get the actual message content
          const messageRequest = messageStore.get(cursor.value.messageHash)
          messageRequest.onsuccess = () => {
            if (messageRequest.result) {
              messages.push(messageRequest.result.content)
            }
          }
          cursor.continue()
        } else {
          resolve(messages)
        }
      }

      request.onerror = () => reject(request.error)
    })
  }
}

export const messageStore = new MessageStore()
