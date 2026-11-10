"use client";

import { useState, type FormEvent } from "react";

interface Message {
  id: number;
  text: string;
  sender: "user" | "assistant";
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const text = message.trim();

    if (!text) return;

    setMessages((previous) => [
      ...previous,
      {
        id: Date.now(),
        text,
        sender: "user",
      },
      {
        id: Date.now() + 1,
        text: "El asistente todavía no está conectado al servicio de IA.",
        sender: "assistant",
      },
    ]);

    setMessage("");
  };

  return (
    <>
      {/* VENTANA DEL CHAT */}
      {isOpen && (
        <div className="
          fixed bottom-24 right-5 z-50
          flex h-[min(550px,calc(100dvh-8rem))]
          w-[min(380px,calc(100vw-2.5rem))]
          flex-col overflow-hidden
          rounded-2xl border border-gray-200
          bg-white shadow-2xl
        ">

          {/* ENCABEZADO */}
          <div className="flex items-center justify-between bg-slate-800 p-4 text-white">

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="23"
                  height="23"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 8V4H8" />
                  <rect width="16" height="12" x="4" y="8" rx="2" />
                  <path d="M2 14h2" />
                  <path d="M20 14h2" />
                  <path d="M9 13v2" />
                  <path d="M15 13v2" />
                </svg>
              </div>

              <div>
                <h3 className="font-semibold">
                  Asistente OpenBridge
                </h3>
                <p className="text-xs text-blue-100">
                  Asistente del catálogo
                </p>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              className="rounded-full p-2 transition hover:bg-white/20"
              aria-label="Cerrar chat"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d="m18 6-12 12" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </div>

          {/* MENSAJES */}
          <div className="flex-1 space-y-4 overflow-y-auto bg-gray-50 p-4">

            <div className="max-w-[85%] rounded-xl rounded-tl-none bg-white p-3 text-sm text-gray-700 shadow-sm">
              ¡Hola! Soy el asistente de OpenBridge.

              <p className="mt-2">
                Puedo ayudarte a explorar el catálogo de tecnologías
                Open Source y encontrar herramientas para tus proyectos.
              </p>
            </div>

            {messages.map((item) => (
              <div
                key={item.id}
                className={`flex ${
                  item.sender === "user"
                    ? "justify-end"
                    : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-xl p-3 text-sm ${
                    item.sender === "user"
                      ? "rounded-tr-none bg-slate-800 text-white"
                      : "rounded-tl-none bg-white text-gray-700 shadow-sm"
                  }`}
                >
                  {item.text}
                </div>
              </div>
            ))}

          </div>

          {/* CAMPO DE MENSAJE */}
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 border-t border-gray-200 bg-white p-3"
          >
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Escribe tu consulta..."
              className="
                min-w-0 flex-1 rounded-xl border border-gray-300
                px-3 py-2.5 text-sm text-gray-700 outline-none
                transition focus:border-blue-500 focus:ring-2
                focus:ring-blue-100
              "
            />

            <button
              type="submit"
              disabled={!message.trim()}
              className="
                flex h-10 w-10 shrink-0 items-center justify-center
                rounded-xl bg-slate-800 text-white transition
                hover:bg-slate-700 disabled:cursor-not-allowed
                disabled:opacity-40
              "
              aria-label="Enviar mensaje"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="19"
                height="19"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m22 2-7 20-4-9-9-4Z" />
                <path d="M22 2 11 13" />
              </svg>
            </button>
          </form>
        </div>
      )}

      {/* BURBUJA FLOTANTE */}
      <button
        onClick={() => setIsOpen((previous) => !previous)}
        className="
          fixed bottom-5 right-5 z-50
          flex h-14 w-14 items-center justify-center
          rounded-full bg-slate-800 text-white
          shadow-lg transition-all duration-200
          hover:scale-105 hover:bg-slate-700
          focus:outline-none focus:ring-4 focus:ring-blue-200
        "
        aria-label={isOpen ? "Cerrar chat" : "Abrir chat"}
        aria-expanded={isOpen}
      >
        {isOpen ? (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="25"
            height="25"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="m18 6-12 12" />
            <path d="m6 6 12 12" />
          </svg>
        ) : (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="27"
            height="27"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />
          </svg>
        )}
      </button>
    </>
  );
}