"use client"

import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SidebarProps {
  backendStatus: {
    status: string
    mcp_status: "connected" | "disconnected"
    available_tools?: string[]
  } | null
  onNewChat: () => void
  availableTools: string[]
}

export default function Sidebar({ backendStatus, onNewChat, availableTools }: SidebarProps) {
  const isConnected = backendStatus?.mcp_status === "connected"

  return (
    <aside className="w-64 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-sidebar-border">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <span className="text-xl">🐦</span>
          <span>BirdyTalk</span>
        </h1>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <Button
          onClick={onNewChat}
          className="w-full bg-sidebar-primary text-sidebar-primary-foreground hover:opacity-90"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Chat
        </Button>
      </div>

      {/* Backend Status */}
      <div className="px-4 py-3 border-t border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-sm font-medium">Backend Status</span>
          </div>
        </div>
        <p className="text-xs text-sidebar-foreground/60 mt-2">{isConnected ? "Connected" : "Disconnected"}</p>
      </div>

      {/* Available Tools */}
      <div className="flex-1 overflow-y-auto px-4 py-4 border-t border-sidebar-border">
        <h3 className="text-sm font-semibold mb-3 text-sidebar-foreground/80">Available Tools</h3>
        <div className="space-y-2">
          {availableTools.length > 0 ? (
            availableTools.map((tool, index) => (
              <div
                key={index}
                className="text-xs bg-sidebar-accent bg-opacity-50 px-3 py-2 rounded text-sidebar-accent-foreground"
              >
                {tool}
              </div>
            ))
          ) : (
            <p className="text-xs text-sidebar-foreground/60">No tools available</p>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-sidebar-border text-xs text-sidebar-foreground/60">v1.0</div>
    </aside>
  )
}
