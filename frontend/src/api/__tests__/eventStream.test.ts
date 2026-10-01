import { describe, expect, it } from 'vitest'
import { createEventParser } from '../eventStream'

describe('authenticated event stream framing', () => {
  it('handles partial CRLF frames and multiline payloads without duplicate delivery', () => {
    const received: Array<[string, string]> = []
    const parse = createEventParser((id, data) => received.push([id, data]))
    parse(': keepalive\r\nid: 12\r\nevent: event\r\ndata: {\r')
    parse('\ndata: "event": {}\r\ndata: }\r\n\r\n')
    expect(received).toEqual([['12', '{\n"event": {}\n}']])
    parse('id: 13\ndata: {"event":{"title":"红磡"}}\n\n')
    expect(received).toHaveLength(2)
    expect(received[1][0]).toBe('13')
  })
})
