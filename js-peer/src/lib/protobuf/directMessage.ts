/* eslint-disable import/export */
/* eslint-disable complexity */
/* eslint-disable @typescript-eslint/no-namespace */
/* eslint-disable @typescript-eslint/no-unnecessary-boolean-literal-compare */
/* eslint-disable @typescript-eslint/no-empty-interface */

import { type Codec, decodeMessage, type DecodeOptions, encodeMessage, enumeration, message } from 'protons-runtime'
import { alloc as uint8ArrayAlloc } from 'uint8arrays/alloc'
import type { Uint8ArrayList } from 'uint8arraylist'

export interface rpc {}

export namespace rpc {
  export interface DirectMessage {}

  export namespace DirectMessage {
    let _codec: Codec<DirectMessage>

    export const codec = (): Codec<DirectMessage> => {
      if (_codec == null) {
        _codec = message<DirectMessage>((obj, w, opts = {}) => {
          if (opts.lengthDelimited !== false) {
            w.fork()
          }

          if (opts.lengthDelimited !== false) {
            w.ldelim()
          }
        }, (reader, length, opts = {}) => {
          const obj: any = {}

          const end = length == null ? reader.len : reader.pos + length

          while (reader.pos < end) {
            const tag = reader.uint32()

            switch (tag >>> 3) {
              default: {
                reader.skipType(tag & 7)
                break
              }
            }
          }

          return obj
        })
      }

      return _codec
    }

    export const encode = (obj: Partial<DirectMessage>): Uint8Array => {
      return encodeMessage(obj, DirectMessage.codec())
    }

    export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<DirectMessage>): DirectMessage => {
      return decodeMessage(buf, DirectMessage.codec(), opts)
    }
  }

  export interface MessageData {
    clientVersion: string
    timestamp: bigint
    id: string
    nodeId: string
    nodePubKey: Uint8Array
    sign: Uint8Array
  }

  export namespace MessageData {
    let _codec: Codec<MessageData>

    export const codec = (): Codec<MessageData> => {
      if (_codec == null) {
        _codec = message<MessageData>((obj, w, opts = {}) => {
          if (opts.lengthDelimited !== false) {
            w.fork()
          }

          if ((obj.clientVersion != null && obj.clientVersion !== '')) {
            w.uint32(10)
            w.string(obj.clientVersion)
          }

          if ((obj.timestamp != null && obj.timestamp !== 0n)) {
            w.uint32(16)
            w.int64(obj.timestamp)
          }

          if ((obj.id != null && obj.id !== '')) {
            w.uint32(26)
            w.string(obj.id)
          }

          if ((obj.nodeId != null && obj.nodeId !== '')) {
            w.uint32(34)
            w.string(obj.nodeId)
          }

          if ((obj.nodePubKey != null && obj.nodePubKey.byteLength > 0)) {
            w.uint32(42)
            w.bytes(obj.nodePubKey)
          }

          if ((obj.sign != null && obj.sign.byteLength > 0)) {
            w.uint32(50)
            w.bytes(obj.sign)
          }

          if (opts.lengthDelimited !== false) {
            w.ldelim()
          }
        }, (reader, length, opts = {}) => {
          const obj: any = {
            clientVersion: '',
            timestamp: 0n,
            id: '',
            nodeId: '',
            nodePubKey: uint8ArrayAlloc(0),
            sign: uint8ArrayAlloc(0)
          }

          const end = length == null ? reader.len : reader.pos + length

          while (reader.pos < end) {
            const tag = reader.uint32()

            switch (tag >>> 3) {
              case 1: {
                obj.clientVersion = reader.string()
                break
              }
              case 2: {
                obj.timestamp = reader.int64()
                break
              }
              case 3: {
                obj.id = reader.string()
                break
              }
              case 4: {
                obj.nodeId = reader.string()
                break
              }
              case 5: {
                obj.nodePubKey = reader.bytes()
                break
              }
              case 6: {
                obj.sign = reader.bytes()
                break
              }
              default: {
                reader.skipType(tag & 7)
                break
              }
            }
          }

          return obj
        })
      }

      return _codec
    }

    export const encode = (obj: Partial<MessageData>): Uint8Array => {
      return encodeMessage(obj, MessageData.codec())
    }

    export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<MessageData>): MessageData => {
      return decodeMessage(buf, MessageData.codec(), opts)
    }
  }

  export enum Status {
    UNKNOWN = 'UNKNOWN',
    OK = 'OK',
    ERROR = 'ERROR'
  }

  enum __StatusValues {
    UNKNOWN = 0,
    OK = 200,
    ERROR = 500
  }

  export namespace Status {
    export const codec = (): Codec<Status> => {
      return enumeration<Status>(__StatusValues)
    }
  }

  export interface DirectMessageRequest {
    messageData?: rpc.MessageData
    message: string
  }

  export namespace DirectMessageRequest {
    let _codec: Codec<DirectMessageRequest>

    export const codec = (): Codec<DirectMessageRequest> => {
      if (_codec == null) {
        _codec = message<DirectMessageRequest>((obj, w, opts = {}) => {
          if (opts.lengthDelimited !== false) {
            w.fork()
          }

          if (obj.messageData != null) {
            w.uint32(10)
            rpc.MessageData.codec().encode(obj.messageData, w)
          }

          if ((obj.message != null && obj.message !== '')) {
            w.uint32(18)
            w.string(obj.message)
          }

          if (opts.lengthDelimited !== false) {
            w.ldelim()
          }
        }, (reader, length, opts = {}) => {
          const obj: any = {
            message: ''
          }

          const end = length == null ? reader.len : reader.pos + length

          while (reader.pos < end) {
            const tag = reader.uint32()

            switch (tag >>> 3) {
              case 1: {
                obj.messageData = rpc.MessageData.codec().decode(reader, reader.uint32(), {
                  limits: opts.limits?.messageData
                })
                break
              }
              case 2: {
                obj.message = reader.string()
                break
              }
              default: {
                reader.skipType(tag & 7)
                break
              }
            }
          }

          return obj
        })
      }

      return _codec
    }

    export const encode = (obj: Partial<DirectMessageRequest>): Uint8Array => {
      return encodeMessage(obj, DirectMessageRequest.codec())
    }

    export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<DirectMessageRequest>): DirectMessageRequest => {
      return decodeMessage(buf, DirectMessageRequest.codec(), opts)
    }
  }

  export interface DirectMessageResponse {
    messageData?: rpc.MessageData
    status: rpc.Status
    statusText?: string
  }

  export namespace DirectMessageResponse {
    let _codec: Codec<DirectMessageResponse>

    export const codec = (): Codec<DirectMessageResponse> => {
      if (_codec == null) {
        _codec = message<DirectMessageResponse>((obj, w, opts = {}) => {
          if (opts.lengthDelimited !== false) {
            w.fork()
          }

          if (obj.messageData != null) {
            w.uint32(10)
            rpc.MessageData.codec().encode(obj.messageData, w)
          }

          if (obj.status != null && __StatusValues[obj.status] !== 0) {
            w.uint32(16)
            rpc.Status.codec().encode(obj.status, w)
          }

          if (obj.statusText != null) {
            w.uint32(26)
            w.string(obj.statusText)
          }

          if (opts.lengthDelimited !== false) {
            w.ldelim()
          }
        }, (reader, length, opts = {}) => {
          const obj: any = {
            status: Status.UNKNOWN
          }

          const end = length == null ? reader.len : reader.pos + length

          while (reader.pos < end) {
            const tag = reader.uint32()

            switch (tag >>> 3) {
              case 1: {
                obj.messageData = rpc.MessageData.codec().decode(reader, reader.uint32(), {
                  limits: opts.limits?.messageData
                })
                break
              }
              case 2: {
                obj.status = rpc.Status.codec().decode(reader)
                break
              }
              case 3: {
                obj.statusText = reader.string()
                break
              }
              default: {
                reader.skipType(tag & 7)
                break
              }
            }
          }

          return obj
        })
      }

      return _codec
    }

    export const encode = (obj: Partial<DirectMessageResponse>): Uint8Array => {
      return encodeMessage(obj, DirectMessageResponse.codec())
    }

    export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<DirectMessageResponse>): DirectMessageResponse => {
      return decodeMessage(buf, DirectMessageResponse.codec(), opts)
    }
  }

  let _codec: Codec<rpc>

  export const codec = (): Codec<rpc> => {
    if (_codec == null) {
      _codec = message<rpc>((obj, w, opts = {}) => {
        if (opts.lengthDelimited !== false) {
          w.fork()
        }

        if (opts.lengthDelimited !== false) {
          w.ldelim()
        }
      }, (reader, length, opts = {}) => {
        const obj: any = {}

        const end = length == null ? reader.len : reader.pos + length

        while (reader.pos < end) {
          const tag = reader.uint32()

          switch (tag >>> 3) {
            default: {
              reader.skipType(tag & 7)
              break
            }
          }
        }

        return obj
      })
    }

    return _codec
  }

  export const encode = (obj: Partial<rpc>): Uint8Array => {
    return encodeMessage(obj, rpc.codec())
  }

  export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<rpc>): rpc => {
    return decodeMessage(buf, rpc.codec(), opts)
  }
}
