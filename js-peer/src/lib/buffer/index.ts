export async function* toBuffer(source: any) {
  for await (const item of source) {
    yield Buffer.from(item)
  }
}
