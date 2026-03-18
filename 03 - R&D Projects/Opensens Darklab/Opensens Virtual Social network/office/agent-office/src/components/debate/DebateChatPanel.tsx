/**
 * DebateChatPanel — Slide-in panel for agent chat (during running or post-debate)
 */

import { useCallback, useRef, useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useDebateStore } from "@/store/debate-store";
import { X, Send } from "lucide-react";

export function DebateChatPanel() {
  const { t } = useTranslation("debate");

  const chatOpen = useDebateStore((s) => s.chatOpen);
  const chatAgentId = useDebateStore((s) => s.chatAgentId);
  const chatMessages = useDebateStore((s) => s.chatMessages);
  const debateAgents = useDebateStore((s) => s.debateAgents);
  const closeChat = useDebateStore((s) => s.closeChat);
  const sendChatMessage = useDebateStore((s) => s.sendChatMessage);
  const debateStatus = useDebateStore((s) => s.status);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const agent = chatAgentId ? debateAgents.get(chatAgentId) : null;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chatMessages.length]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    const msg = input.trim();
    setInput("");
    try {
      await sendChatMessage(msg);
    } finally {
      setSending(false);
    }
  }, [input, sending, sendChatMessage]);

  if (!chatOpen || !agent) return null;

  return (
    <div className="absolute inset-y-0 right-0 z-50 flex w-80 flex-col border-l border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {agent.name}
          </p>
          <p className="text-xs text-gray-500">{agent.role}</p>
          {debateStatus === "running" && (
            <span className="mt-0.5 flex items-center gap-1 text-[10px] text-amber-500">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
              {t("chat.debateOngoing", "Debate in progress")}
            </span>
          )}
        </div>
        <button
          onClick={closeChat}
          className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2">
        {chatMessages.length === 0 && (
          <p className="mt-4 text-center text-xs text-gray-400">
            {t("chat.prompt", "Ask this agent about the debate...")}
          </p>
        )}
        {chatMessages.map((msg, i) => (
          <div
            key={i}
            className={`mb-2 ${msg.role === "user" ? "text-right" : "text-left"}`}
          >
            <div
              className={`inline-block max-w-[90%] rounded-lg px-3 py-2 text-xs ${
                msg.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="text-left">
            <div className="inline-block rounded-lg bg-gray-100 px-3 py-2 text-xs text-gray-500 dark:bg-gray-800">
              <div className="flex gap-1">
                <span className="animate-bounce">.</span>
                <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>.</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 border-t border-gray-200 px-3 py-2 dark:border-gray-700">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={t("chat.placeholder", "Type a message...")}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          disabled={sending}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || sending}
          className="rounded-lg bg-blue-500 p-1.5 text-white hover:bg-blue-600 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
