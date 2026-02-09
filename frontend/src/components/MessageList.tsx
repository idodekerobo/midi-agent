"use client";

import { ChatMessage } from "@/lib/api";
import { useEffect, useRef } from "react";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full text-center">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-2">
              Start a Conversation
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Upload an MP3 file or send a message to get started
            </p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-xl px-4 py-3 rounded-lg ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : message.isThought
                      ? "bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 italic border-l-2 border-gray-400 dark:border-gray-500"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                  {message.content}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
}
