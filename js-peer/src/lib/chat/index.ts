export const newChatFileMessage = (id: string, body: Uint8Array) => {
  return `File: ${id} (${body.length} bytes)`;
};
