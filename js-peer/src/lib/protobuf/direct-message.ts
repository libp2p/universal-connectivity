/* eslint-disable import/export */
/* eslint-disable complexity */
/* eslint-disable @typescript-eslint/no-namespace */
/* eslint-disable @typescript-eslint/no-unnecessary-boolean-literal-compare */
/* eslint-disable @typescript-eslint/no-empty-interface */

import { type Codec, decodeMessage, type DecodeOptions, encodeMessage, enumeration, message } from 'protons-runtime'
import type { Uint8ArrayList } from 'uint8arraylist'

export interface dm {}

export namespace dm {
  export interface DirectMessage {}

  export namespace DirectMessage {
    let _codec: Codec<DirectMessage>

    export const codec = (): Codec<DirectMessage> => {
      if (_codec == null) {
        _codec = message<DirectMessage>(
          (obj, w, opts = {}) => {
            if (opts.lengthDelimited !== false) {
              w.fork()
            }

            if (opts.lengthDelimited !== false) {
              w.ldelim()
            }
          },
          (reader, length, opts = {}) => {
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
          },
        )
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

  export interface Metadata {
    clientVersion: string
    timestamp: bigint
  }

  export namespace Metadata {
    let _codec: Codec<Metadata>

    export const codec = (): Codec<Metadata> => {
      if (_codec == null) {
        _codec = message<Metadata>(
          (obj, w, opts = {}) => {
            if (opts.lengthDelimited !== false) {
              w.fork()
            }

            if (obj.clientVersion != null && obj.clientVersion !== '') {
              w.uint32(10)
              w.string(obj.clientVersion)
            }

            if (obj.timestamp != null && obj.timestamp !== 0n) {
              w.uint32(16)
              w.int64(obj.timestamp)
            }

            if (opts.lengthDelimited !== false) {
              w.ldelim()
            }
          },
          (reader, length, opts = {}) => {
            const obj: any = {
              clientVersion: '',
              timestamp: 0n,
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
                default: {
                  reader.skipType(tag & 7)
                  break
                }
              }
            }

            return obj
          },
        )
      }

      return _codec
    }

    export const encode = (obj: Partial<Metadata>): Uint8Array => {
      return encodeMessage(obj, Metadata.codec())
    }

    export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<Metadata>): Metadata => {
      return decodeMessage(buf, Metadata.codec(), opts)
    }
  }

  export enum Status {
    UNKNOWN = 'UNKNOWN',
    OK = 'OK',
    ERROR = 'ERROR',
  }

  enum __StatusValues {
    UNKNOWN = 0,
    OK = 200,
    ERROR = 500,
  }

  export namespace Status {
    export const codec = (): Codec<Status> => {
      return enumeration<Status>(__StatusValues)
    }
  }

  export interface DirectMessageRequest {
    metadata?: dm.Metadata
    content: string
    type: string
  }

  export namespace DirectMessageRequest {
    let _codec: Codec<DirectMessageRequest>

    export const codec = (): Codec<DirectMessageRequest> => {
      if (_codec == null) {
        _codec = message<DirectMessageRequest>(
          (obj, w, opts = {}) => {
            if (opts.lengthDelimited !== false) {
              w.fork()
            }

            if (obj.metadata != null) {
              w.uint32(10)
              dm.Metadata.codec().encode(obj.metadata, w)
            }

            if (obj.content != null && obj.content !== '') {
              w.uint32(18)
              w.string(obj.content)
            }

            if (obj.type != null && obj.type !== '') {
              w.uint32(26)
              w.string(obj.type)
            }

            if (opts.lengthDelimited !== false) {
              w.ldelim()
            }
          },
          (reader, length, opts = {}) => {
            const obj: any = {
              content: '',
              type: '',
            }

            const end = length == null ? reader.len : reader.pos + length

            while (reader.pos < end) {
              const tag = reader.uint32()

              switch (tag >>> 3) {
                case 1: {
                  obj.metadata = dm.Metadata.codec().decode(reader, reader.uint32(), {
                    limits: opts.limits?.metadata,
                  })
                  break
                }
                case 2: {
                  obj.content = reader.string()
                  break
                }
                case 3: {
                  obj.type = reader.string()
                  break
                }
                default: {
                  reader.skipType(tag & 7)
                  break
                }
              }
            }

            return obj
          },
        )
      }

      return _codec
    }

    export const encode = (obj: Partial<DirectMessageRequest>): Uint8Array => {
      return encodeMessage(obj, DirectMessageRequest.codec())
    }

    export const decode = (
      buf: Uint8Array | Uint8ArrayList,
      opts?: DecodeOptions<DirectMessageRequest>,
    ): DirectMessageRequest => {
      return decodeMessage(buf, DirectMessageRequest.codec(), opts)
    }
  }

  export interface DirectMessageResponse {
    metadata?: dm.Metadata
    status: dm.Status
    statusText?: string
  }

  export namespace DirectMessageResponse {
    let _codec: Codec<DirectMessageResponse>

    export const codec = (): Codec<DirectMessageResponse> => {
      if (_codec == null) {
        _codec = message<DirectMessageResponse>(
          (obj, w, opts = {}) => {
            if (opts.lengthDelimited !== false) {
              w.fork()
            }

            if (obj.metadata != null) {
              w.uint32(10)
              dm.Metadata.codec().encode(obj.metadata, w)
            }

            if (obj.status != null && __StatusValues[obj.status] !== 0) {
              w.uint32(16)
              dm.Status.codec().encode(obj.status, w)
            }

            if (obj.statusText != null) {
              w.uint32(26)
              w.string(obj.statusText)
            }

            if (opts.lengthDelimited !== false) {
              w.ldelim()
            }
          },
          (reader, length, opts = {}) => {
            const obj: any = {
              status: Status.UNKNOWN,
            }

            const end = length == null ? reader.len : reader.pos + length

            while (reader.pos < end) {
              const tag = reader.uint32()

              switch (tag >>> 3) {
                case 1: {
                  obj.metadata = dm.Metadata.codec().decode(reader, reader.uint32(), {
                    limits: opts.limits?.metadata,
                  })
                  break
                }
                case 2: {
                  obj.status = dm.Status.codec().decode(reader)
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
          },
        )
      }

      return _codec
    }

    export const encode = (obj: Partial<DirectMessageResponse>): Uint8Array => {
      return encodeMessage(obj, DirectMessageResponse.codec())
    }

    export const decode = (
      buf: Uint8Array | Uint8ArrayList,
      opts?: DecodeOptions<DirectMessageResponse>,
    ): DirectMessageResponse => {
      return decodeMessage(buf, DirectMessageResponse.codec(), opts)
    }
  }

  let _codec: Codec<dm>

  export const codec = (): Codec<dm> => {
    if (_codec == null) {
      _codec = message<dm>(
        (obj, w, opts = {}) => {
          if (opts.lengthDelimited !== false) {
            w.fork()
          }

          if (opts.lengthDelimited !== false) {
            w.ldelim()
          }
        },
        (reader, length, opts = {}) => {
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
        },
      )
    }

    return _codec
  }

  export const encode = (obj: Partial<dm>): Uint8Array => {
    return encodeMessage(obj, dm.codec())
  }

  export const decode = (buf: Uint8Array | Uint8ArrayList, opts?: DecodeOptions<dm>): dm => {
    return decodeMessage(buf, dm.codec(), opts)
  }
}
