import { forwardRef } from "react"
import MessageBubble from "./message-bubble"

interface Message {
  role: "user" | "assistant" | "tool"
  content: string
  image?: string
  fileName?: string
  toolName?: string
  toolStatus?: "start" | "end" | "error"
  toolResult?: any
}

interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
}

const ChatWindow = forwardRef<HTMLDivElement, ChatWindowProps>(({ messages, isLoading }, ref) => {
  return (
    <div
      ref={ref}
      className="flex-1 overflow-y-auto px-6 py-6 space-y-4 bg-gradient-to-b from-background to-background"
    >
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="text-5xl mb-4">🐦</div>
            <h2 className="text-2xl font-bold mb-2">Welcome to BirdyTalk</h2>
            <p className="text-foreground/60 max-w-md">
              Start a conversation to identify bird species or ask questions about birds.
            </p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-muted text-muted-foreground rounded-lg px-4 py-3 max-w-md">
                <div className="flex gap-2">
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
})

ChatWindow.displayName = "ChatWindow"

export default ChatWindow