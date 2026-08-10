'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useAgent, useChat, useSessionContext, useSessionMessages } from '@livekit/components-react';

const canned = [
  'Got it! Let me check that for you... 🧾 Could you share your order ID so I can look it up?',
  'Sure thing! Our current offers include 10% off on festive wear and free delivery above ₹499.',
  'No worries, returns are easy. Which item would you like to return, and what is the reason?',
  'Connecting you to a human teammate now — they will join the chat shortly. 🙋',
  'Thanks for sharing that! I have noted it down — is there anything else I can help you with?',
];

function speak(text: string, voiceRepliesOn: boolean, onSpeakStateChange: (status: string) => void) {
  if (!voiceRepliesOn || typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return;
  }

  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1;
  utter.pitch = 1;
  utter.onstart = () => onSpeakStateChange('Speaking...');
  utter.onend = () => onSpeakStateChange('Online — your shopping dost');
  window.speechSynthesis.speak(utter);
}

export function MitraSessionView({ className }: { className?: string }) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { send } = useChat();
  const { state: agentState } = useAgent();
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [voiceRepliesOn, setVoiceRepliesOn] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [statusText, setStatusText] = useState('Online — your shopping dost');
  const [listeningText, setListeningText] = useState('Listening...');
  const recognitionRef = useRef<any>(null);
  const draftRef = useRef(draft);

  const scrolledToBottomRef = useRef(false);
  const chatRef = useRef<HTMLDivElement>(null);

  draftRef.current = draft;

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    recognition.onstart = () => {
      setIsListening(true);
      setListeningText('Listening...');
      setStatusText('Listening...');
    };

    recognition.onresult = (event: any) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript || '';
      }
      setDraft(transcript);
      setListeningText(transcript || 'Listening...');
    };

    recognition.onerror = (event: any) => {
      setListeningText(
        event.error === 'no-speech' ? "Didn't catch that — try again" : 'Mic error — check permissions'
      );
      window.setTimeout(() => {
        setIsListening(false);
        setStatusText('Online — your shopping dost');
      }, 1200);
    };

    recognition.onend = () => {
      setIsListening(false);
      setStatusText('Online — your shopping dost');
      if (draftRef.current.trim()) {
        void handleSend(draftRef.current);
      }
    };

    recognitionRef.current = recognition;
  }, []);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const lastIncoming = [...messages].reverse().find((message) => !message.from?.isLocal);
    if (!lastIncoming) return;
    speak(lastIncoming.message, voiceRepliesOn, setStatusText);
  }, [messages, voiceRepliesOn]);

  const isConnected = session.isConnected;

  const quickReplies = useMemo(
    () => [
      { label: '📦 Track my order', value: 'Track my order' },
      { label: '🏷️ Today\'s offers', value: "What are today's offers?" },
      { label: '↩️ Return an item', value: 'I want to return an item' },
      { label: '🧑‍💼 Talk to a human', value: 'Talk to a human agent' },
    ],
    []
  );

  const handleSend = async (text?: string) => {
    const value = (text ?? draft).trim();
    if (!value || !isConnected) return;
    setDraft('');
    setIsSending(true);
    try {
      await send(value);
    } catch (error) {
      console.error(error);
    } finally {
      setIsSending(false);
    }
  };

  const handleMicClick = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    if (isListening) {
      recognition.stop();
    } else {
      window.speechSynthesis.cancel();
      setDraft('');
      try {
        recognition.start();
      } catch {
        // ignore if already started
      }
    }
  };

  return (
    <section className={className}>
      <div className="mitra-root">
        <div className="phone">
          <div className="signboard">
            <div className="bulbs">
              {Array.from({ length: 9 }).map((_, index) => (
                <div key={index} className="bulb" />
              ))}
            </div>
            <div className="shop-row">
              <div className="shop-icon">🛍️</div>
              <div style={{ flex: 1 }}>
                <div className="shop-name">ABC Shop Mitra</div>
                <div className="shop-tag">
                  <span className="dot" /> <span>{statusText}</span>
                </div>
              </div>
              <button
                type="button"
                className={`voice-toggle ${!voiceRepliesOn ? 'muted' : ''}`}
                onClick={() => {
                  setVoiceRepliesOn((state) => {
                    const next = !state;
                    if (!next && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                      window.speechSynthesis.cancel();
                    }
                    return next;
                  });
                }}
                aria-label="Toggle voice replies"
                title="Toggle voice replies"
              >
                {voiceRepliesOn ? '🔊' : '🔇'}
              </button>
            </div>
          </div>

          <div className="chat" ref={chatRef}>
            {messages.length === 0 ? (
              <div className="msg bot">
                <div className="msg-label">Mitra</div>
                Namaste! 🙏 I'm Mitra, your assistant for ABC Shop. Ask me about orders, products, returns, or anything else — I'm here to help.
              </div>
            ) : null}
            {messages.map((item) => {
              const isUser = item.from?.isLocal === true;
              return (
                <div key={item.id} className={`msg ${isUser ? 'user' : 'bot'}`}>
                  {!isUser && <div className="msg-label">Mitra</div>}
                  {item.message}
                </div>
              );
            })}
            {agentState === 'thinking' && (
              <div className="typing">
                <span />
                <span />
                <span />
              </div>
            )}
          </div>

          <div className="chips">
            {quickReplies.map((reply) => (
              <button
                key={reply.value}
                type="button"
                className="chip"
                onClick={() => void handleSend(reply.value)}
              >
                {reply.label}
              </button>
            ))}
          </div>

          <div className={`listening-banner ${isListening ? 'active' : ''}`}>
            <div className="wave">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
            <span>{listeningText}</span>
          </div>

          <div className="counter">
            <button
              type="button"
              className={`mic-btn ${isListening ? 'listening' : ''}`}
              onClick={handleMicClick}
              aria-label="Speak to Mitra"
              title="Speak to Mitra"
            >
              🎤
            </button>
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Type or tap the mic to talk..."
              autoComplete="off"
            />
            <button
              type="button"
              className="send-btn"
              onClick={() => void handleSend()}
              aria-label="Send message"
              disabled={!draft.trim() || !isConnected || isSending}
            >
              ➤
            </button>
          </div>
          <div className="footnote">
            ABC Shop Mitra can make mistakes. Please double-check important info.
          </div>
        </div>
        <style jsx>{`
          .mitra-root {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: radial-gradient(circle at 10% 10%, rgba(242,169,59,0.12), transparent 40%),
              radial-gradient(circle at 90% 90%, rgba(28,110,99,0.1), transparent 40%),
              #fbf3e7;
            color: #2b2118;
            font-family: 'Poppins', sans-serif;
          }

          .phone {
            width: 100%;
            max-width: 430px;
            height: min(760px, 92vh);
            background: #fffdf8;
            border-radius: 22px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 30px 60px -20px rgba(43,33,24,0.35), 0 0 0 1px rgba(43,33,24,0.06);
            position: relative;
          }

          .signboard {
            background: linear-gradient(180deg, #7a1f2b 0%, #611722 100%);
            padding: 22px 20px 26px;
            position: relative;
            color: #fbf3e7;
            border-bottom: 6px solid #f2a93b;
          }

          .signboard::before {
            content: '';
            position: absolute;
            inset: 0;
            background-image: repeating-linear-gradient(45deg, rgba(255,255,255,0.03) 0 2px, transparent 2px 14px);
            pointer-events: none;
          }

          .bulbs {
            display: flex;
            justify-content: space-between;
            padding: 0 4px 12px;
          }

          .bulb {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #f2a93b;
            box-shadow: 0 0 6px 1px rgba(242,169,59,0.9);
          }

          .shop-row {
            display: flex;
            align-items: center;
            gap: 12px;
          }

          .shop-icon {
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: #f2a93b;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            flex-shrink: 0;
            box-shadow: inset 0 -3px 0 rgba(0,0,0,0.15);
          }

          .shop-name {
            font-family: 'Baloo 2', sans-serif;
            font-weight: 800;
            font-size: 23px;
            letter-spacing: 0.3px;
            line-height: 1.1;
            text-shadow: 0 2px 0 rgba(0,0,0,0.2);
          }

          .shop-tag {
            font-size: 12.5px;
            opacity: 0.85;
            margin-top: 2px;
            display: flex;
            align-items: center;
            gap: 6px;
          }

          .dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #6fe0a0;
            box-shadow: 0 0 0 3px rgba(111,224,160,0.25);
          }

          .chat {
            flex: 1;
            overflow-y: auto;
            padding: 18px 16px 8px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: linear-gradient(180deg, rgba(122,31,43,0.02), transparent 120px), #fbf3e7;
          }

          .chat::-webkit-scrollbar {
            width: 6px;
          }

          .chat::-webkit-scrollbar-thumb {
            background: rgba(122,31,43,0.15);
            border-radius: 10px;
          }

          .msg {
            max-width: 82%;
            padding: 11px 14px;
            border-radius: 16px;
            font-size: 14.5px;
            line-height: 1.45;
            animation: rise 0.25s ease;
          }

          @keyframes rise {
            from {
              opacity: 0;
              transform: translateY(6px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }

          .msg.bot {
            align-self: flex-start;
            background: #fffdf8;
            border: 1px solid rgba(43,33,24,0.08);
            border-bottom-left-radius: 4px;
            box-shadow: 0 2px 6px rgba(43,33,24,0.05);
          }

          .msg.user {
            align-self: flex-end;
            background: #1c6e63;
            color: #fff;
            border-bottom-right-radius: 4px;
          }

          .msg-label {
            font-size: 10.5px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 3px;
            opacity: 0.55;
          }

          .typing {
            align-self: flex-start;
            display: flex;
            gap: 4px;
            padding: 12px 14px;
            background: #fffdf8;
            border: 1px solid rgba(43,33,24,0.08);
            border-radius: 16px;
            border-bottom-left-radius: 4px;
          }

          .typing span {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #7a1f2b;
            opacity: 0.4;
            animation: bounce 1.1s infinite ease-in-out;
          }

          .typing span:nth-child(2) {
            animation-delay: 0.15s;
          }

          .typing span:nth-child(3) {
            animation-delay: 0.3s;
          }

          @keyframes bounce {
            0%, 60%, 100% {
              transform: translateY(0);
              opacity: 0.4;
            }
            30% {
              transform: translateY(-4px);
              opacity: 0.9;
            }
          }

          .chips {
            display: flex;
            gap: 8px;
            padding: 2px 16px 12px;
            overflow-x: auto;
            flex-wrap: nowrap;
            background: #fbf3e7;
          }

          .chips::-webkit-scrollbar {
            display: none;
          }

          .chip {
            flex-shrink: 0;
            border: 1.5px solid #f2a93b;
            color: #7a1f2b;
            background: #fff8ea;
            padding: 7px 13px;
            border-radius: 999px;
            font-size: 12.5px;
            font-weight: 500;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s ease;
          }

          .chip:hover {
            background: #f2a93b;
            color: #7a1f2b;
            transform: translateY(-1px);
          }

          .counter {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 14px;
            background: #fffdf8;
            border-top: 3px solid #f2a93b;
          }

          .counter input {
            flex: 1;
            border: 1.5px solid rgba(43,33,24,0.15);
            background: #fbf3e7;
            border-radius: 24px;
            padding: 11px 16px;
            font-family: 'Poppins', sans-serif;
            font-size: 14px;
            color: #2b2118;
            outline: none;
            transition: border-color 0.15s ease;
          }

          .counter input:focus {
            border-color: #1c6e63;
          }

          .send-btn {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            border: none;
            background: #c0392b;
            color: #fff;
            font-size: 17px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: transform 0.12s ease, background 0.12s ease;
          }

          .send-btn:hover {
            background: #7a1f2b;
            transform: scale(1.05);
          }

          .send-btn:active {
            transform: scale(0.94);
          }

          .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .voice-toggle {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border: 1.5px solid rgba(255,255,255,0.35);
            background: rgba(255,255,255,0.08);
            color: #fbf3e7;
            font-size: 15px;
            cursor: pointer;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
          }

          .voice-toggle:hover {
            background: rgba(255,255,255,0.18);
          }

          .voice-toggle.muted {
            opacity: 0.5;
          }

          .mic-btn {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            border: none;
            background: #1c6e63;
            color: #fff;
            font-size: 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: transform 0.12s ease, background 0.12s ease, box-shadow 0.15s ease;
            position: relative;
          }

          .mic-btn:hover {
            transform: scale(1.05);
          }

          .mic-btn:active {
            transform: scale(0.94);
          }

          .mic-btn.listening {
            background: #c0392b;
            animation: pulse-ring 1.4s infinite;
          }

          @keyframes pulse-ring {
            0% {
              box-shadow: 0 0 0 0 rgba(192,57,43,0.5);
            }
            70% {
              box-shadow: 0 0 0 12px rgba(192,57,43,0);
            }
            100% {
              box-shadow: 0 0 0 0 rgba(192,57,43,0);
            }
          }

          .listening-banner {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 8px 16px;
            background: linear-gradient(90deg, rgba(192,57,43,0.08), rgba(242,169,59,0.12));
            border-top: 1px solid rgba(122,31,43,0.08);
            font-size: 12.5px;
            color: #7a1f2b;
            font-weight: 500;
          }

          .listening-banner.active {
            display: flex;
          }

          .wave {
            display: flex;
            align-items: center;
            gap: 2px;
            height: 16px;
          }

          .wave span {
            width: 3px;
            border-radius: 2px;
            background: #c0392b;
            animation: wave 0.9s infinite ease-in-out;
          }

          .wave span:nth-child(1) {
            height: 6px;
            animation-delay: 0s;
          }
          .wave span:nth-child(2) {
            height: 14px;
            animation-delay: 0.1s;
          }
          .wave span:nth-child(3) {
            height: 9px;
            animation-delay: 0.2s;
          }
          .wave span:nth-child(4) {
            height: 16px;
            animation-delay: 0.3s;
          }
          .wave span:nth-child(5) {
            height: 7px;
            animation-delay: 0.4s;
          }

          @keyframes wave {
            0%, 100% {
              transform: scaleY(0.4);
            }
            50% {
              transform: scaleY(1);
            }
          }

          .footnote {
            text-align: center;
            font-size: 10.5px;
            color: rgba(43,33,24,0.4);
            padding: 6px 0 10px;
            background: #fffdf8;
          }
        `}</style>
      </div>
    </section>
  );
}
