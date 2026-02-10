"use client";

import { useState, useRef } from "react";
import { ChatMessage, sendMessage } from "@/lib/api";
import { MessageList } from "./MessageList";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Music, Send, Loader2, X } from "lucide-react";

export function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<unknown[]>([]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragOverRef = useRef(false);

  const handleSendMessage = async () => {
    if (!input.trim() && !file) return;

    const userMessage = input.trim();
    const userFile = file;

    // Clear inputs immediately for responsiveness
    setInput("");
    setFile(null);

    // Add user message
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: userMessage || (userFile ? `📁 ${userFile.name}` : ""),
      },
    ]);

    // Add an empty assistant message to be populated by streaming
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "",
      },
    ]);

    setIsLoading(true);

    try {
      await sendMessage(
        userMessage,
        history,
        (chunk) => {
          console.log(`received chunk type: ${chunk.type}`)
          if (chunk.type === 'delta') {
            // Update the last message (the assistant's message) with the new content
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: lastMessage.content + chunk.content },
                ];
              }
              return prev;
            });
          } else if (chunk.type === 'tool_call') {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: lastMessage.content + `\n\n🛠️ Calling tool: ${chunk.tool_name}...\n` },
                ];
              }
              return prev;
            });
          } else if (chunk.type === 'tool_result') {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: lastMessage.content + `\n📝 Tool Result (${chunk.tool_name}):\n${chunk.content}\n\n` },
                ];
              }
              return prev;
            });
          // TODO: do i need to add part start and part ends to this????
          } else if (chunk.type === 'part_start') {
            console.log('Part Start:', chunk);
          } else if (chunk.type === 'part_end') {
            console.log('Part End:', chunk);
          } else if (chunk.type === 'event') {
            console.log('received event:', chunk.event);
          } else if (chunk.type === 'final') {
            // Final content might be different or complete, ensure it's set
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage && lastMessage.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: chunk.content },
                ];
              }
              return [...prev, { role: 'assistant', content: chunk.content }];
            });
            if (chunk.new_history) setHistory(chunk.new_history);
          } else {
            console.log('no handler for this chunk type:', chunk.type);
            console.log(chunk);
          }
        },
        userFile || undefined
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to send message";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${errorMessage}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (selectedFile: File | null) => {
    if (selectedFile && selectedFile.type.startsWith("audio/")) {
      setFile(selectedFile);
    } else if (selectedFile) {
      alert("Please select an audio file (MP3, WAV, etc.)");
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    dragOverRef.current = true;
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (e.currentTarget === e.target) {
      dragOverRef.current = false;
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragOverRef.current = false;

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      handleFileSelect(droppedFiles[0]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-gray-950">
      {/* Header */}
      <div className="border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg">
              <Music className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Audio to Sheet Music
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Convert MP3 files to MIDI with AI
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full max-w-4xl mx-auto w-full flex flex-col">
          <MessageList messages={messages} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4">
        <div className="max-w-4xl mx-auto">
          {/* File Upload Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`mb-4 border-2 border-dashed rounded-lg p-4 transition-colors ${
              dragOverRef.current
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/20"
                : "border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
              className="hidden"
            />

            {file ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Music className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="p-1 hover:bg-gray-200 dark:hover:bg-gray-800 rounded"
                >
                  <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center">
                <Music className="w-8 h-8 text-gray-400 dark:text-gray-600 mb-2" />
                <p className="text-center text-sm text-gray-600 dark:text-gray-400">
                  Drag and drop an audio file here or{" "}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="text-blue-600 dark:text-blue-400 font-medium hover:underline"
                  >
                    click to browse
                  </button>
                </p>
              </div>
            )}
          </div>

          {/* Message Input */}
          <div className="flex gap-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask the agent to convert your audio..."
              disabled={isLoading}
              className="flex-1 bg-gray-50 dark:bg-gray-900 border-gray-300 dark:border-gray-700"
            />
            <Button
              onClick={handleSendMessage}
              disabled={isLoading || (!input.trim() && !file)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span className="hidden sm:inline ml-2">Send</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
