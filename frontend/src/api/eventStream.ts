// Incremental SSE parser: handles split UTF-8 chunks through TextDecoder upstream,
// multiline data, CRLF, comments, and durable audit cursors.
export function createEventParser(onEvent: (id: string, data: string) => void) {
  let buffer = '', id = '', data: string[] = []
  return (chunk: string) => {
    buffer += chunk
    let end: number
    while ((end = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, end).replace(/\r$/, '')
      buffer = buffer.slice(end + 1)
      if (!line) {
        if (data.length) onEvent(id, data.join('\n'))
        data = []
      } else if (!line.startsWith(':')) {
        const colon = line.indexOf(':')
        const field = colon < 0 ? line : line.slice(0, colon)
        const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'id' && !value.includes('\0')) id = value
        if (field === 'data') data.push(value)
      }
    }
  }
}
