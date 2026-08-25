import WebSocket from 'ws'
import { parseServerMessage, type ServerMessage } from '../shared/protocol'

export class GatewayClient {
  private ws: WebSocket | null = null
  private listeners: Array<(msg: ServerMessage) => void> = []

  constructor(private url: string) {}

  onMessage(fn: (msg: ServerMessage) => void): void {
    this.listeners.push(fn)
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url)
      this.ws.on('open', () => {
        this.send({ type: 'hello', protocol_version: 1 })
        resolve()
      })
      this.ws.on('error', reject)
      this.ws.on('message', (data) => {
        const raw = JSON.parse(String(data)) as unknown
        let msg: ServerMessage
        try {
          msg = parseServerMessage(raw)
        } catch (err) {
          console.error('[gateway] dropped server message', err, raw)
          return
        }
        for (const fn of this.listeners) {
          fn(msg)
        }
      })
    })
  }

  startCall(deviceId: string): void {
    this.send({ type: 'start_call', device_id: deviceId, language: 'spanish' })
  }

  stopCall(): void {
    this.send({ type: 'stop_call' })
  }

  close(): void {
    this.ws?.close()
  }

  private send(obj: object): void {
    if (this.ws == null || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('Not connected to the local assistant service')
    }
    this.ws.send(JSON.stringify(obj))
  }
}
