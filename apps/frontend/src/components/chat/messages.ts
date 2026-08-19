import type { UIMessage } from '@tanstack/ai-react'

export type ChatSeedMessage = {
  role: string
  content: string
}

export function toChatMessages(messages: ChatSeedMessage[]): UIMessage[] {
  return messages.map((message, index) => ({
    id: `seed-${index}`,
    role: message.role === 'user' ? 'user' : 'assistant',
    parts: [{ type: 'text' as const, content: message.content }],
  }))
}

export function messageText(message: UIMessage): string {
  return message.parts
    .filter((part): part is Extract<UIMessage['parts'][number], { type: 'text' }> => part.type === 'text')
    .map((part) => part.content)
    .join('')
}
