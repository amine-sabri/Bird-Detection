"use client"

import type React from "react"

import { useEffect, useRef, useState } from "react"
import Sidebar from "@/components/sidebar"
import ChatWindow from "@/components/chat-window"
import InputBar from "@/components/input-bar"

interface Message {
  role: "user" | "assistant" | "tool"
  content: string
  image?: string
  fileName?: string
  toolName?: string
  toolStatus?: "start" | "end" | "error"
  toolResult?: any
}

interface BackendStatus {
  status: string
  mcp_status: "connected" | "disconnected"
  available_tools?: string[]
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [currentMessage, setCurrentMessage] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [backendStatus, setBackendStatus] = useState<BackendStatus | null>(null)
  const chatWindowRef = useRef<HTMLDivElement>(null)

  // Fetch backend health status on mount
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch("/api/health");
        const data = await response.json()
        setBackendStatus(data)
      } catch (error) {
        console.error("Failed to fetch backend status:", error)
        setBackendStatus({
          status: "error",
          mcp_status: "disconnected",
        })
      }
    }

    fetchHealth()
  }, [])

  // Auto-scroll to latest message
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight
    }
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!currentMessage.trim() && !selectedFile) return

    try {
      // Créer l'URL de l'image pour l'affichage
      let imageUrl = ""
      if (selectedFile) {
        imageUrl = URL.createObjectURL(selectedFile)
      }

      // Add user message to UI (optimistic update)
      const userMessage: Message = {
        role: "user",
        content: currentMessage,
        image: imageUrl,
        fileName: selectedFile?.name,
      }

      setMessages((prev) => [...prev, userMessage])
      setCurrentMessage("")
      const fileToSend = selectedFile
      setSelectedFile(null)
      setIsLoading(true)

      // Create FormData for submission
      const formData = new FormData()
      formData.append("message", currentMessage)

      if (sessionId) {
        formData.append("session_id", sessionId)
      }

      if (fileToSend) {
        formData.append("file", fileToSend)
      }

      // Utiliser la route streaming
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        body: formData,
      })

      if (!response.body) {
        throw new Error("No response body")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantResponse = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === "session_created") {
                setSessionId(data.session_id)
              } else if (data.type === "tool_start") {
                // Afficher un message de début d'utilisation d'outil
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "tool",
                    content: `Utilisation de l'outil : ${data.tool_name}`,
                    toolName: data.tool_name,
                    toolStatus: "start",
                  },
                ])
              } else if (data.type === "tool_end") {
                // Mettre à jour le message d'outil avec le résultat
                setMessages((prev) => {
                  const newMessages = [...prev]
                  const lastToolIndex = newMessages
                    .map((m, i) => ({ m, i }))
                    .reverse()
                    .find(({ m }) => m.role === "tool" && m.toolName === data.tool_name && m.toolStatus === "start")

                  if (lastToolIndex) {
                    newMessages[lastToolIndex.i] = {
                      ...newMessages[lastToolIndex.i],
                      content: `Outil ${data.tool_name} terminé`,
                      toolStatus: "end",
                      toolResult: data.result,
                    }
                  }

                  return newMessages
                })
              } else if (data.type === "tool_error") {
                // Gérer les erreurs d'outil
                setMessages((prev) => {
                  const newMessages = [...prev]
                  const lastToolIndex = newMessages
                    .map((m, i) => ({ m, i }))
                    .reverse()
                    .find(({ m }) => m.role === "tool" && m.toolName === data.tool_name && m.toolStatus === "start")

                  if (lastToolIndex) {
                    newMessages[lastToolIndex.i] = {
                      ...newMessages[lastToolIndex.i],
                      content: `Erreur avec l'outil ${data.tool_name}`,
                      toolStatus: "error",
                      toolResult: { error: data.error },
                    }
                  }

                  return newMessages
                })
              } else if (data.type === "final_response") {
                assistantResponse = data.content
              } else if (data.type === "done") {
                // Ajouter la réponse finale de l'assistant
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: assistantResponse,
                  },
                ])
                setIsLoading(false)
              } else if (data.type === "error") {
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: `Erreur: ${data.message}`,
                  },
                ])
                setIsLoading(false)
              }
            } catch (err) {
              console.error("Error parsing SSE data:", err)
            }
          }
        }
      }
    } catch (error) {
      console.error("Error sending message:", error)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, there was an error connecting to the backend.",
        },
      ])
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setCurrentMessage("")
    setSelectedFile(null)
    setSessionId(null)
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        backendStatus={backendStatus}
        onNewChat={handleNewChat}
        availableTools={backendStatus?.available_tools || []}
      />
      <div className="flex flex-1 flex-col">
        <ChatWindow messages={messages} isLoading={isLoading} ref={chatWindowRef} />
        <InputBar
          currentMessage={currentMessage}
          selectedFile={selectedFile}
          isLoading={isLoading}
          onMessageChange={setCurrentMessage}
          onFileSelect={setSelectedFile}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  )
}
