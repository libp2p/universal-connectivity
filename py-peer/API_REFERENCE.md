# py-peer Tornado API Reference

**Base URL:** `http://localhost:8765`  
**API Version:** `v1`  
**Framework:** [Tornado](https://www.tornadoweb.org/) 6.5+  
**Python:** 3.12 · **libp2p:** py-libp2p 0.6.0

---

## Overview

The py-peer Tornado API exposes the full capabilities of a running libp2p node over HTTP REST and WebSocket. It allows any HTTP client — browser, CLI, frontend app, or another service — to interact with the peer without a UI.

### Starting the API server

```bash
python main.py --nick <nickname> --api --api-port 8765
```

| Flag | Default | Description |
|---|---|---|
| `--api` | — | Enable Tornado REST + WebSocket server |
| `--api-port` | `8765` | Port for the API server |
| `--nick` | auto | Nickname shown in chat |
| `--port` | auto | libp2p TCP listen port |
| `--no-strict-signing` | off | Disable message signature verification |
| `--api-routes` | — | Print all routes and exit immediately |

```bash
# Print all routes without starting
python main.py --api-routes
```

---

## Response Envelope

Most REST endpoints return the same JSON envelope:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": 1772532115.19
}
```

> **Exception:** `POST /api/v1/ask` uses a dedicated RAG response shape and does not use the `data/error/timestamp` envelope from `BaseHandler`.

**Error:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": 400,
    "message": "Human-readable error message",
    "detail": "Optional traceback or extra context"
  },
  "timestamp": 1772532115.19
}
```

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `202` | Request accepted and queued (async libp2p operations) |
| `204` | No content (CORS preflight) |
| `400` | Bad request — missing or invalid field |
| `404` | Resource not found |
| `409` | Conflict — e.g. already subscribed to topic |
| `500` | Internal server error |
| `502` | Upstream/model backend error |
| `503` | Service not ready yet or queue unavailable |

### CORS

All endpoints return:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-API-Key
```

---

## Endpoint Index

| Method | Path | Description |
|---|---|---|
| GET | [`/api/v1/node/info`](#get-apiv1nodeinfo) | Local peer identity |
| GET | [`/api/v1/node/status`](#get-apiv1nodestatus) | Readiness and uptime |
| GET | [`/api/v1/node/multiaddr`](#get-apiv1nodemultiaddr) | Full multiaddress |
| GET | [`/api/v1/peers`](#get-apiv1peers) | Connected peers |
| GET | [`/api/v1/peers/count`](#get-apiv1peerscount) | Connected peer count |
| GET | [`/api/v1/peers/known`](#get-apiv1peersknown) | All peers in peerstore |
| POST | [`/api/v1/peers/connect`](#post-apiv1peersconnect) | Connect via multiaddr |
| GET | [`/api/v1/peers/{peer_id}`](#get-apiv1peerspeer_id) | Single peer info |
| GET | [`/api/v1/peers/{peer_id}/identify`](#get-apiv1peerspeer_ididentify) | Cached identify data |
| POST | [`/api/v1/messages`](#post-apiv1messages) | Send to default topic |
| GET | [`/api/v1/messages/{topic}`](#get-apiv1messagestopic) | List stored messages |
| POST | [`/api/v1/messages/{topic}`](#post-apiv1messagestopic) | Send to specific topic |
| GET | [`/api/v1/messages/{topic}/unread`](#get-apiv1messagestopicunread) | Unread count |
| PUT | [`/api/v1/messages/{topic}/read`](#put-apiv1messagestopicread) | Mark all as read |
| GET | [`/api/v1/topics`](#get-apiv1topics) | List subscribed topics |
| POST | [`/api/v1/topics`](#post-apiv1topics) | Subscribe to new topic |
| GET | [`/api/v1/topics/{topic}/info`](#get-apiv1topicstopicinfo) | Topic details |
| GET | [`/api/v1/topics/{topic}/peers`](#get-apiv1topicstopicpeers) | Mesh peers for topic |
| GET | [`/api/v1/files/shared`](#get-apiv1filesshared) | List shared files |
| GET | [`/api/v1/files/shared/{cid}`](#get-apiv1filessharedcid) | Shared file detail |
| POST | [`/api/v1/files/share`](#post-apiv1filesshare) | Share a local file |
| POST | [`/api/v1/files/download`](#post-apiv1filesdownload) | Download file by CID |
| POST | [`/api/v1/files/upload`](#post-apiv1filesupload) | Upload + share (multipart) |
| GET | [`/api/v1/dht/status`](#get-apiv1dhtstatus) | DHT mode and table size |
| GET | [`/api/v1/dht/peers`](#get-apiv1dhtpeers) | DHT routing table peers |
| GET | [`/api/v1/dht/routing-table`](#get-apiv1dhtrouting-table) | Full routing table |
| GET | [`/api/v1/pubsub/peers`](#get-apiv1pubsubpeers) | PubSub connected peers |
| GET | [`/api/v1/pubsub/mesh`](#get-apiv1pubsubmesh) | GossipSub mesh state |
| GET | [`/api/v1/pubsub/fanout`](#get-apiv1pubsubfanout) | GossipSub fanout |
| GET | [`/api/v1/pubsub/config`](#get-apiv1pubsubconfig) | GossipSub configuration |
| GET | [`/api/v1/pubsub/subscriptions`](#get-apiv1pubsubsubscriptions) | Active subscriptions |
| GET | [`/api/v1/identity/cache`](#get-apiv1identitycache) | All cached identify entries |
| GET | [`/api/v1/identity/{peer_id}`](#get-apiv1identitypeer_id) | Cached identify info |
| GET | [`/api/v1/identity/{peer_id}/pubkey`](#get-apiv1identitypeer_idpubkey) | Public key (hex) |
| DELETE | [`/api/v1/identity/{peer_id}/cache`](#delete-apiv1identitypeer_idcache) | Invalidate cache entry |
| GET | [`/api/v1/service/status`](#get-apiv1servicestatus) | Service health |
| GET | [`/api/v1/service/config`](#get-apiv1serviceconfig) | Service configuration |
| POST | [`/api/v1/service/stop`](#post-apiv1servicestop) | Graceful shutdown |
| POST | [`/api/v1/service/bootstrap`](#post-apiv1servicebootstrap) | Re-trigger bootstrap |
| POST | [`/api/v1/ask`](#post-apiv1ask) | RAG assistant for py-libp2p/spec questions |
| WS | [`/ws/messages`](#ws-wsmessages) | Real-time message stream |
| WS | [`/ws/system`](#ws-wssystem) | Real-time system events |
| WS | [`/ws/peers`](#ws-wspeers) | Real-time peer list updates |
| WS | [`/ws/pubsub/mesh`](#ws-wspubsubmesh) | Real-time mesh topology |

---

## Node

### GET /api/v1/node/info

Returns the local peer's identity, multiaddress, nickname, and readiness.

**Request:**
```bash
curl http://localhost:8765/api/v1/node/info
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peer_id": "QmcfYkkx45zyxRdRw333WnNssTMQ9AAVMF2wUB7nmQMiow",
    "nickname": "alice",
    "multiaddr": "/ip4/0.0.0.0/tcp/54770/p2p/QmcfYkkx45zyxRdRw333WnNssTMQ9AAVMF2wUB7nmQMiow",
    "port": 54770,
    "ready": true,
    "uptime_seconds": 42.3
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/node/status

Returns the current running state and uptime. This endpoint works **even before** the service is fully ready (unlike most others).

**Request:**
```bash
curl http://localhost:8765/api/v1/node/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "ready": true,
    "running": true,
    "uptime_seconds": 507.2,
    "port": 54770,
    "strict_signing": false,
    "nickname": "alice",
    "topic": null
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/node/multiaddr

Returns just the full multiaddress string. Useful for sharing with other peers.

**Request:**
```bash
curl http://localhost:8765/api/v1/node/multiaddr
```

**Response:**
```json
{
  "success": true,
  "data": {
    "multiaddr": "/ip4/0.0.0.0/tcp/54770/p2p/QmcfYkkx45zyxRdRw333WnNssTMQ9AAVMF2wUB7nmQMiow"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## Peers

### GET /api/v1/peers

Returns the list of currently connected peers (active libp2p connections).

**Request:**
```bash
curl http://localhost:8765/api/v1/peers
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peers": [
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"
    ],
    "count": 1
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/peers/count

Returns just the count of currently connected peers.

**Request:**
```bash
curl http://localhost:8765/api/v1/peers/count
```

**Response:**
```json
{
  "success": true,
  "data": { "count": 1 },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/peers/known

Returns all peers the node has ever seen, including disconnected ones stored in the peerstore.

**Request:**
```bash
curl http://localhost:8765/api/v1/peers/known
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peers": [
      "QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"
    ],
    "count": 78
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/peers/connect

Queues a connection request to a remote peer using its multiaddress.

> **Note:** Returns `202 Accepted` immediately. The actual TCP connection happens asynchronously in the libp2p trio thread.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/peers/connect \
  -H "Content-Type: application/json" \
  -d '{"multiaddr": "/ip4/139.178.65.157/tcp/4001/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `multiaddr` | string | ✅ | Full libp2p multiaddress of the peer to connect to |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "Connection request queued",
    "multiaddr": "/ip4/139.178.65.157/tcp/4001/p2p/QmQCU2Ec..."
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `400` — missing field:**
```json
{
  "success": false,
  "data": null,
  "error": { "code": 400, "message": "'multiaddr' field is required.", "detail": null },
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/peers/{peer_id}

Returns peerstore information (known addresses) for a specific peer.

**Request:**
```bash
curl http://localhost:8765/api/v1/peers/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peer_id": "QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "addrs": ["/ip4/139.178.65.157/tcp/4001"]
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `404`** — peer not in peerstore.

---

### GET /api/v1/peers/{peer_id}/identify

Returns **cached** identify protocol data for the peer (agent version, protocols, listen addresses). The data is populated automatically when the node connects to the peer.

**Request:**
```bash
curl http://localhost:8765/api/v1/peers/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa/identify
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peer_id": "QmQCU2Ec...",
    "protocol_version": "ipfs/0.1.0",
    "agent_version": "go-libp2p/0.31.0",
    "listen_addrs": ["/ip4/139.178.65.157/tcp/4001"],
    "protocols": ["/ipfs/id/1.0.0", "/meshsub/1.1.0", "/kad/1.0.0"],
    "cached_at": 1772532115.19
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `404`** — connect to the peer first to populate the cache.

---

## Messaging

### POST /api/v1/messages

Sends a message to the node's **default chat topic** (`universal-connectivity` or the one set via `--topic`).

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello everyone!"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | ✅ | The message text to publish |

**Response `202`:**
```json
{
  "success": true,
  "data": { "message": "Message queued for delivery" },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/messages/{topic}

Returns stored messages for a topic. Supports pagination with `limit` and `offset` query params.

**Request:**
```bash
curl "http://localhost:8765/api/v1/messages/universal-connectivity?limit=50&offset=0"
```

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | `100` | Max messages to return |
| `offset` | integer | `0` | Number of messages to skip |

**Response:**
```json
{
  "success": true,
  "data": {
    "topic": "universal-connectivity",
    "messages": [
      {
        "type": "chat_message",
        "message": "Hello from Tornado API!",
        "sender_nick": "alice",
        "sender_id": "QmcfYkkx45zyxRdRw333WnNssTMQ9AAVMF2wUB7nmQMiow",
        "timestamp": 1772532166.99,
        "topic": "universal-connectivity",
        "read": false
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

Each message object fields:

| Field | Description |
|---|---|
| `type` | `"chat_message"` or `"file_message"` |
| `message` | Message text |
| `sender_nick` | Display name of the sender |
| `sender_id` | libp2p peer ID of the sender |
| `timestamp` | Unix timestamp |
| `topic` | Topic the message was received on |
| `read` | Whether the message has been marked as read |

---

### POST /api/v1/messages/{topic}

Sends a message to a **specific topic**. The topic must already be subscribed.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/messages/universal-connectivity \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from the API!"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | ✅ | The message text |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "Message queued for delivery",
    "topic": "universal-connectivity"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `400`** — topic not subscribed (subscribe first via `POST /api/v1/topics`).

---

### GET /api/v1/messages/{topic}/unread

Returns the count of unread messages in a topic.

**Request:**
```bash
curl http://localhost:8765/api/v1/messages/universal-connectivity/unread
```

**Response:**
```json
{
  "success": true,
  "data": {
    "topic": "universal-connectivity",
    "unread_count": 3
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### PUT /api/v1/messages/{topic}/read

Marks all messages in a topic as read, resetting the unread count to `0`.

**Request:**
```bash
curl -X PUT http://localhost:8765/api/v1/messages/universal-connectivity/read
```

**Response:**
```json
{
  "success": true,
  "data": {
    "topic": "universal-connectivity",
    "message": "All messages marked as read"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## Topics

### GET /api/v1/topics

Returns all currently subscribed topics with metadata.

**Request:**
```bash
curl http://localhost:8765/api/v1/topics
```

**Response:**
```json
{
  "success": true,
  "data": {
    "topics": {
      "universal-connectivity": {
        "unread_count": 1,
        "total_count": 5,
        "last_message": {
          "type": "chat_message",
          "message": "Hello!",
          "sender_nick": "bob",
          "timestamp": 1772532166.99
        }
      },
      "universal-connectivity-browser-peer-discovery": {
        "unread_count": 0,
        "total_count": 0,
        "last_message": null
      }
    },
    "count": 2
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/topics

Subscribes the node to a new GossipSub topic.

> Returns `202 Accepted` immediately. The actual subscription happens asynchronously.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/topics \
  -H "Content-Type: application/json" \
  -d '{"topic": "my-custom-channel"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `topic` | string | ✅ | Topic name to subscribe to |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "Subscription request queued for 'my-custom-channel'",
    "topic": "my-custom-channel"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `409`** — already subscribed:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": 409,
    "message": "Already subscribed to topic 'universal-connectivity'.",
    "detail": null
  },
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/topics/{topic}/info

Returns detailed info for a single topic.

**Request:**
```bash
curl http://localhost:8765/api/v1/topics/universal-connectivity/info
```

**Response:**
```json
{
  "success": true,
  "data": {
    "topic": "universal-connectivity",
    "unread_count": 1,
    "total_count": 5,
    "last_message": { "message": "hi", "sender_nick": "bob", "timestamp": 1772532166.99 }
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/topics/{topic}/peers

Returns peer IDs of nodes currently in the GossipSub mesh for this topic.

**Request:**
```bash
curl http://localhost:8765/api/v1/topics/universal-connectivity/peers
```

**Response:**
```json
{
  "success": true,
  "data": {
    "topic": "universal-connectivity",
    "mesh_peers": [
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"
    ],
    "count": 1
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## File Sharing

File sharing is powered by **Bitswap** and **MerkleDag** — the same protocol used by IPFS.

### GET /api/v1/files/shared

Lists all files this node has shared in the current session.

**Request:**
```bash
curl http://localhost:8765/api/v1/files/shared
```

**Response:**
```json
{
  "success": true,
  "data": {
    "shared_files": [
      {
        "cid": "a1b2c3d4e5f6...",
        "filename": "document.pdf",
        "filesize": 204800,
        "filepath": "/home/alice/document.pdf"
      }
    ],
    "count": 1
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/files/shared/{cid}

Returns metadata for a specific shared file by its CID (hex string).

**Request:**
```bash
curl http://localhost:8765/api/v1/files/shared/a1b2c3d4e5f6
```

**Response:**
```json
{
  "success": true,
  "data": {
    "cid": "a1b2c3d4e5f6...",
    "filename": "document.pdf",
    "filesize": 204800,
    "filepath": "/home/alice/document.pdf"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/files/share

Shares a file that already exists on the node's local disk. The file is added to Bitswap and its CID is announced via the subscribed topic.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/files/share \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/home/alice/photo.jpg", "topic": "universal-connectivity"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `file_path` | string | ✅ | Absolute path to the file on disk |
| `topic` | string | ✅ | Topic to announce the file on |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "File share request queued",
    "filename": "photo.jpg",
    "topic": "universal-connectivity"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/files/download

Downloads a file by its CID hex from a remote peer via Bitswap.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/files/download \
  -H "Content-Type: application/json" \
  -d '{"file_cid": "a1b2c3d4e5f6...", "file_name": "photo.jpg"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `file_cid` | string | ✅ | CID hex string of the file to download |
| `file_name` | string | — | Expected filename (used for saving) |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "Download request queued",
    "file_cid": "a1b2c3d4e5f6...",
    "file_name": "photo.jpg"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

> **Note:** When the download completes, a `file_downloaded` event is pushed via `WS /ws/messages`.

---

### POST /api/v1/files/upload

Accepts a file uploaded via `multipart/form-data`, saves it to the node's download directory, and shares it to a topic.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/files/upload \
  -F "file=@/home/alice/photo.jpg" \
  -F "topic=universal-connectivity"
```

**Form fields:**
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | ✅ | The file to upload |
| `topic` | string | ✅ | Topic to share the file on |

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "File uploaded and share request queued",
    "filename": "photo.jpg",
    "size": 204800,
    "topic": "universal-connectivity",
    "saved_path": "/Users/alice/Downloads/photo.jpg"
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## DHT

### GET /api/v1/dht/status

Returns the current Kademlia DHT mode and routing table summary.

**Request:**
```bash
curl http://localhost:8765/api/v1/dht/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "mode": "SERVER",
    "random_walk_enabled": true,
    "routing_table_size": 9
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

| Field | Values | Description |
|---|---|---|
| `mode` | `"SERVER"`, `"CLIENT"` | DHT operating mode |
| `random_walk_enabled` | bool | Whether random walk peer discovery is active |
| `routing_table_size` | integer | Number of peers in the Kademlia routing table |

---

### GET /api/v1/dht/peers

Returns the list of peer IDs currently in the DHT routing table.

**Request:**
```bash
curl http://localhost:8765/api/v1/dht/peers
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peers": [
      "QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
      "QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"
    ],
    "count": 9
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/dht/routing-table

Returns the full DHT routing table as a flat list.

**Request:**
```bash
curl http://localhost:8765/api/v1/dht/routing-table
```

**Response:**
```json
{
  "success": true,
  "data": {
    "routing_table": ["QmcZf59...", "QmQCU2Ec...", "12D3KooW..."],
    "total_peers": 9
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## PubSub

### GET /api/v1/pubsub/peers

Returns all peers currently connected via the GossipSub/PubSub protocol.

**Request:**
```bash
curl http://localhost:8765/api/v1/pubsub/peers
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peers": ["12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"],
    "count": 1
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/pubsub/mesh

Returns the current GossipSub mesh — which peers are in the mesh for each subscribed topic.

**Request:**
```bash
curl http://localhost:8765/api/v1/pubsub/mesh
```

**Response:**
```json
{
  "success": true,
  "data": {
    "mesh": {
      "universal-connectivity": ["12D3KooWRogVw8...", "12D3KooWMtHTK4..."],
      "universal-connectivity-browser-peer-discovery": ["12D3KooWRogVw8..."]
    },
    "topic_count": 2,
    "total_mesh_peers": 3
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/pubsub/fanout

Returns the GossipSub fanout peers — peers that receive messages on topics they haven't subscribed to yet.

**Request:**
```bash
curl http://localhost:8765/api/v1/pubsub/fanout
```

**Response:**
```json
{
  "success": true,
  "data": {
    "fanout": {
      "universal-connectivity": ["12D3KooWRogVw8..."]
    }
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/pubsub/config

Returns the GossipSub router configuration values set at startup.

**Request:**
```bash
curl http://localhost:8765/api/v1/pubsub/config
```

**Response:**
```json
{
  "success": true,
  "data": {
    "degree": 3,
    "degree_low": 2,
    "degree_high": 4,
    "gossip_window": null,
    "gossip_history": null,
    "heartbeat_interval": 5,
    "heartbeat_initial_delay": 2.0,
    "protocols": ["/meshsub/1.0.0", "/meshsub/1.1.0", "/meshsub/1.2.0"]
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/pubsub/subscriptions

Returns the names of all currently active pubsub topic subscriptions.

**Request:**
```bash
curl http://localhost:8765/api/v1/pubsub/subscriptions
```

**Response:**
```json
{
  "success": true,
  "data": {
    "subscriptions": [
      "universal-connectivity",
      "universal-connectivity-browser-peer-discovery"
    ],
    "count": 2
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## Identity

The identify protocol is used by libp2p nodes to exchange metadata (agent version, supported protocols, listen addresses). Data is cached when a peer connects.

### GET /api/v1/identity/cache

Returns all currently cached identify entries.

**Request:**
```bash
curl http://localhost:8765/api/v1/identity/cache
```

**Response:**
```json
{
  "success": true,
  "data": {
    "cache": {
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7": {
        "protocol_version": "ipfs/0.1.0",
        "agent_version": "go-libp2p/0.31.0",
        "listen_addrs": ["/ip4/10.0.0.1/tcp/4001"],
        "protocols": ["/ipfs/id/1.0.0", "/meshsub/1.1.0"],
        "cached_at": 1772532100.0
      }
    },
    "count": 1
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/identity/{peer_id}

Returns cached identify data for a specific peer.

**Request:**
```bash
curl http://localhost:8765/api/v1/identity/12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peer_id": "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7",
    "protocol_version": "ipfs/0.1.0",
    "agent_version": "go-libp2p/0.31.0",
    "listen_addrs": ["/ip4/10.0.0.1/tcp/4001"],
    "protocols": ["/ipfs/id/1.0.0", "/meshsub/1.1.0"],
    "cached_at": 1772532100.0
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

**Error `404`** — if the peer has not connected yet.

---

### GET /api/v1/identity/{peer_id}/pubkey

Returns the public key (hex) for a peer from the identity cache.

**Request:**
```bash
curl http://localhost:8765/api/v1/identity/12D3KooWRogVw8.../pubkey
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peer_id": "12D3KooWRogVw8...",
    "public_key_hex": "0802122102a1b2c3d4..."
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### DELETE /api/v1/identity/{peer_id}/cache

Removes a specific peer's cached identify data so it will be re-fetched on next connection.

**Request:**
```bash
curl -X DELETE http://localhost:8765/api/v1/identity/12D3KooWRogVw8.../cache
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Cache entry for '12D3KooWRogVw8...' deleted."
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## Service

### GET /api/v1/service/status

Returns the overall health of the running service.

**Request:**
```bash
curl http://localhost:8765/api/v1/service/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "ready": true,
    "running": true,
    "uptime_seconds": 507.2,
    "peer_count": 3
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### GET /api/v1/service/config

Returns the configuration the service was started with.

**Request:**
```bash
curl http://localhost:8765/api/v1/service/config
```

**Response:**
```json
{
  "success": true,
  "data": {
    "nickname": "alice",
    "port": 54770,
    "topic": null,
    "strict_signing": false,
    "download_dir": "/Users/alice/Downloads",
    "connect_addrs": []
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/service/stop

Sends a graceful shutdown signal to the `HeadlessService`. The libp2p node will stop accepting connections and close.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/service/stop
```

**Response:**
```json
{
  "success": true,
  "data": { "message": "Stop signal sent to HeadlessService." },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

### POST /api/v1/service/bootstrap

Re-queues connections to all default bootstrap peers. Useful if the node lost connectivity.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/service/bootstrap
```

**Response `202`:**
```json
{
  "success": true,
  "data": {
    "message": "Queued connections to 9 bootstrap peers.",
    "bootstrap_peers_count": 9
  },
  "error": null,
  "timestamp": 1772532115.19
}
```

---

## RAG Assistant

### POST /api/v1/ask

Asks the py-libp2p assistant a grounded question using the local vector store + Groq model backend.

> **Response shape note:** this endpoint does **not** return the standard `BaseHandler` envelope.

**Request:**
```bash
curl -X POST http://localhost:8765/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How does GossipSub mesh maintenance work?"}'
```

**Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | ✅ | Natural-language question about py-libp2p/libp2p specs |

**Success `200`:**
```json
{
  "success": true,
  "answer": "...grounded answer...",
  "sources": [
    "py-libp2p/libp2p/pubsub/gossipsub.py",
    "specs/pubsub/gossipsub/README.md"
  ]
}
```

**No relevant chunks found (`200`):**
```json
{
  "success": true,
  "answer": "No relevant context found in the knowledge base.",
  "sources": []
}
```

**Error `400` (bad/missing `question`):**
```json
{
  "success": false,
  "error": "'question' cannot be empty."
}
```

**Error `503` (vector store unavailable):**
```json
{
  "success": false,
  "error": "RAG assistant is not available. Vector store not loaded."
}
```

**Error `500` (vector search failure):**
```json
{
  "success": false,
  "error": "Vector search failed."
}
```

**Error `502` (LLM backend failure):**
```json
{
  "success": false,
  "error": "LLM backend error: ..."
}
```

---

## WebSocket APIs

WebSocket endpoints provide **real-time, push-based** data delivery. Connect once and receive a continuous stream of events — no polling needed.

> **Important:** WebSocket endpoints are **Tornado-level** feeds of internal data. They are completely separate from the py-libp2p WebSocket transport that peers use to talk to each other.

---

### WS /ws/messages

Streams all incoming chat messages and file events in real-time.

**Connect:**
```bash
# Using wscat (npm install -g wscat)
wscat -c ws://localhost:8765/ws/messages
```

**Received frame — chat message:**
```json
{
  "event": "chat_message",
  "data": {
    "type": "chat_message",
    "message": "Hello!",
    "sender_nick": "bob",
    "sender_id": "QmBob...",
    "topic": "universal-connectivity",
    "timestamp": 1772532200.0,
    "read": false
  }
}
```

**Received frame — file announced:**
```json
{
  "event": "file_message",
  "data": {
    "type": "file_message",
    "file_cid": "a1b2c3...",
    "file_name": "photo.jpg",
    "file_size": 204800,
    "sender_nick": "carol",
    "topic": "universal-connectivity",
    "timestamp": 1772532210.0
  }
}
```

**Received frame — file download complete:**
```json
{
  "event": "file_downloaded",
  "data": {
    "type": "file_downloaded",
    "file_cid": "a1b2c3...",
    "file_name": "photo.jpg",
    "file_size": 204800,
    "save_path": "/Users/alice/Downloads/photo.jpg",
    "timestamp": 1772532220.0
  }
}
```

**Client → server commands:**

Optionally send JSON to filter messages by topic:

```json
{ "action": "filter_topic", "topic": "my-channel" }
```
```json
{ "action": "unfilter" }
```

Server acknowledgements for these commands:

```json
{ "event": "filter_set", "topic": "my-channel" }
```

```json
{ "event": "filter_cleared" }
```

---

### WS /ws/system

Streams service system events and notifications.

**Connect:**
```bash
wscat -c ws://localhost:8765/ws/system
```

**Received frame:**
```json
{
  "event": "system_message",
  "data": {
    "type": "system_message",
    "message": "Connected to peer: 12D3KooWRog...",
    "timestamp": 1772532115.19
  }
}
```

Common system messages include: connection established, connection failed, subscription confirmed, file share started.

---

### WS /ws/peers

Pushes the current connected peer list whenever it changes (checked every 3 seconds).

**Connect:**
```bash
wscat -c ws://localhost:8765/ws/peers
```

**Received frame:**
```json
{
  "event": "peer_update",
  "data": {
    "connected_peers": [
      "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7",
      "12D3KooWMtHTK4bKh8gkaq65JuUNEo1Q8kJUpUfy98RC7sog2SXT"
    ],
    "peer_count": 2,
    "timestamp": 1772532115.19
  }
}
```

Only pushes when the peer list actually changes.

---

### WS /ws/pubsub/mesh

Pushes GossipSub mesh topology updates every 5 seconds.

**Connect:**
```bash
wscat -c ws://localhost:8765/ws/pubsub/mesh
```

**Received frame:**
```json
{
  "event": "mesh_update",
  "data": {
    "mesh": {
      "universal-connectivity": [
        "12D3KooWRogVw8icxSguqjKonoTsbVymkbRoBtyr8Zz2bFdytJh7"
      ],
      "universal-connectivity-browser-peer-discovery": []
    },
    "topic_count": 2,
    "total_mesh_peers": 1,
    "timestamp": 1772532115.19
  }
}
```

---

## Common Workflows

### Start a node and check it's ready

```bash
python main.py --nick alice --api --api-port 8765 --no-strict-signing

curl http://localhost:8765/api/v1/service/status
```

### Connect to a specific peer

```bash
curl -X POST http://localhost:8765/api/v1/peers/connect \
  -H "Content-Type: application/json" \
  -d '{"multiaddr": "/ip4/192.168.1.10/tcp/9095/p2p/QmBob..."}'
```

### Subscribe to a custom topic and send a message

```bash
curl -X POST http://localhost:8765/api/v1/topics \
  -H "Content-Type: application/json" \
  -d '{"topic": "my-team-chat"}'

# Wait a moment for subscription to be confirmed via WS /ws/system, then:
curl -X POST http://localhost:8765/api/v1/messages/my-team-chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from the API!"}'
```

### Read and clear new messages

```bash
# Get unread count
curl http://localhost:8765/api/v1/messages/universal-connectivity/unread

# Fetch messages (paginated)
curl "http://localhost:8765/api/v1/messages/universal-connectivity?limit=20&offset=0"

# Mark all as read
curl -X PUT http://localhost:8765/api/v1/messages/universal-connectivity/read
```

### Share a file

```bash
# Share a local file
curl -X POST http://localhost:8765/api/v1/files/share \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/home/alice/doc.pdf", "topic": "universal-connectivity"}'

# Or upload directly
curl -X POST http://localhost:8765/api/v1/files/upload \
  -F "file=@/home/alice/doc.pdf" \
  -F "topic=universal-connectivity"
```

### Download a file announced by another peer

```bash
# First, listen for file_message events on WS /ws/messages to get the CID.
# Then:
curl -X POST http://localhost:8765/api/v1/files/download \
  -H "Content-Type: application/json" \
  -d '{"file_cid": "a1b2c3d4e5f6...", "file_name": "doc.pdf"}'
```

### Monitor in real-time (three terminals)

```bash
# Terminal 1 — all messages
wscat -c ws://localhost:8765/ws/messages

# Terminal 2 — peer updates
wscat -c ws://localhost:8765/ws/peers

# Terminal 3 — system events
wscat -c ws://localhost:8765/ws/system
```

---

## File Structure

```
py-peer/
├── main.py               ← --api, --api-port, --api-routes flags added here
├── tornado_server.py     ← TornadoServer class, URL routing, _print_routes()
└── api/
    ├── __init__.py
    ├── base.py           ← BaseHandler (CORS, JSON envelope, 503 guard)
    ├── node.py           ← /api/v1/node/*
    ├── peers.py          ← /api/v1/peers/*
    ├── messages.py       ← /api/v1/messages/*
    ├── topics.py         ← /api/v1/topics/*
    ├── files.py          ← /api/v1/files/*
    ├── dht.py            ← /api/v1/dht/*
    ├── pubsub.py         ← /api/v1/pubsub/*
    ├── identity.py       ← /api/v1/identity/*
    ├── service.py        ← /api/v1/service/*
    └── websocket.py      ← /ws/* WebSocket handlers
```
