"use client"

import type React from "react"

import { useRef } from "react"
import { Button } from "@/components/ui/button"
import { Paperclip, Send } from "lucide-react"

interface InputBarProps {
  currentMessage: string
  selectedFile: File | null
  isLoading: boolean
  onMessageChange: (message: string) => void
  onFileSelect: (file: File | null) => void
  onSubmit: (e: React.FormEvent) => void
}

export default function InputBar({
  currentMessage,
  selectedFile,
  isLoading,
  onMessageChange,
  onFileSelect,
  onSubmit,
}: InputBarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onFileSelect(file)
    }
  }

  const handleRemoveFile = () => {
    onFileSelect(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  return (
    <form onSubmit={onSubmit} className="border-t border-border bg-background p-4">
      {/* File Preview */}
      {selectedFile && (
        <div className="mb-3 flex items-center gap-2 bg-muted p-2 rounded">
          <span className="text-sm text-muted-foreground flex-1">📎 {selectedFile.name}</span>
          <button
            type="button"
            onClick={handleRemoveFile}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Remove
          </button>
        </div>
      )}

      {/* Input Container */}
      <div className="flex gap-2 items-end">
        {/* File Upload Button */}
        <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
        <Button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          size="icon"
          variant="ghost"
          disabled={isLoading}
          className="text-foreground/60 hover:text-foreground"
        >
          <Paperclip className="w-5 h-5" />
        </Button>

        {/* Text Input */}
        <input
          type="text"
          value={currentMessage}
          onChange={(e) => onMessageChange(e.target.value)}
          placeholder="Send a message or upload an image..."
          disabled={isLoading}
          className="flex-1 bg-input border border-border rounded-lg px-4 py-2 text-foreground placeholder-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        />

        {/* Send Button */}
        <Button
          type="submit"
          size="icon"
          disabled={isLoading || (!currentMessage.trim() && !selectedFile)}
          className="bg-blue-600 hover:bg-blue-700 text-white"
        >
          <Send className="w-5 h-5" />
        </Button>
      </div>
    </form>
  )
}
