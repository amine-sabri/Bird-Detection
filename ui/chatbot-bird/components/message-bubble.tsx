import ReactMarkdown from "react-markdown"
import { Loader2, CheckCircle2, XCircle, Wrench } from "lucide-react"

interface Message {
  role: "user" | "assistant" | "tool"
  content: string
  image?: string
  fileName?: string
  toolName?: string
  toolStatus?: "start" | "end" | "error"
  toolResult?: any
}

export default function MessageBubble({ message }: { message: Message }) {
  // Affichage pour les messages d'outils
  if (message.role === "tool") {
    return (
      <div className="flex justify-center my-2">
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 rounded-lg px-4 py-2 max-w-md flex items-center gap-2">
          {message.toolStatus === "start" && (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">
                🔧 Utilisation de l'outil : <span className="font-semibold">{message.toolName}</span> en cours...
              </span>
            </>
          )}
          {message.toolStatus === "end" && (
            <>
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm">
                ✅ Outil <span className="font-semibold">{message.toolName}</span> terminé
              </span>
            </>
          )}
          {message.toolStatus === "error" && (
            <>
              <XCircle className="w-4 h-4" />
              <span className="text-sm">
                ❌ Erreur avec l'outil <span className="font-semibold">{message.toolName}</span>
              </span>
            </>
          )}
        </div>
      </div>
    )
  }

  // Affichage pour les messages utilisateur
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-lg px-4 py-3 max-w-md">
          {/* Afficher l'image si présente */}
          {message.image && (
            <div className="mb-3">
              <img
                src={message.image}
                alt={message.fileName || "Uploaded image"}
                className="rounded-lg max-w-full h-auto max-h-64 object-contain"
              />
              {message.fileName && <p className="text-xs mt-2 opacity-80">📎 {message.fileName}</p>}
            </div>
          )}
          {/* Afficher le texte */}
          {message.content && <p className="text-sm">{message.content}</p>}
        </div>
      </div>
    )
  }

  // Affichage pour les messages de l'assistant
  return (
    <div className="flex justify-start">
      <div className="bg-muted text-muted-foreground rounded-lg px-4 py-3 max-w-md">
        <ReactMarkdown
          components={{
            p: ({ children }) => <p className="text-sm mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="text-sm list-disc list-inside mb-2 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="text-sm list-decimal list-inside mb-2 space-y-1">{children}</ol>,
            li: ({ children }) => <li className="mb-1">{children}</li>,
            code: ({ children }) => (
              <code className="bg-background/50 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
            ),
            pre: ({ children }) => (
              <pre className="bg-background/50 p-3 rounded text-xs overflow-x-auto my-2 font-mono">{children}</pre>
            ),
            strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
            em: ({ children }) => <em className="italic">{children}</em>,
            h1: ({ children }) => <h1 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h1>,
            h2: ({ children }) => <h2 className="text-sm font-bold mb-2 mt-2 first:mt-0">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h3>,
            a: ({ children, href }) => (
              <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-muted-foreground/30 pl-3 my-2 italic">{children}</blockquote>
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  )
}