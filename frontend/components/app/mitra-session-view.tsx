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

  // Day 6 Outbound Call State
  const [activeTab, setActiveTab] = useState<'inbound' | 'outbound'>('outbound');
  const [customerName, setCustomerName] = useState('Ramesh Kumar');
  const [phoneNumber, setPhoneNumber] = useState('+91 98765 43210');
  const [restockItem, setRestockItem] = useState('Basmati Rice 5kg & Wheat Flour 10kg');
  const [simulateOutcome, setSimulateOutcome] = useState<'CONNECTED' | 'NO_ANSWER' | 'BUSY' | 'VOICEMAIL' | 'IMMEDIATE_HANGUP'>('CONNECTED');
  const [outboundLog, setOutboundLog] = useState<any | null>(null);
  const [isCallingOutbound, setIsCallingOutbound] = useState(false);

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
      { label: '📦 Restock Basmati Rice', value: 'I want to restock 5kg Basmati Rice' },
      { label: '🛑 Opt Out of Calls', value: 'Please opt out and stop calling me' },
      { label: '🏷️ Check Catalogue', value: 'Check price for Wheat Flour' },
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

  const handleTriggerOutbound = async () => {
    setIsCallingOutbound(true);
    setOutboundLog(null);
    try {
      const res = await fetch('/api/outbound', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_name: customerName,
          phone_number: phoneNumber,
          restock_item: restockItem,
          simulate_outcome: simulateOutcome,
        }),
      });
      const data = await res.json();
      setOutboundLog(data);
    } catch (err: any) {
      setOutboundLog({ error: err.message || 'Call failed' });
    } finally {
      setIsCallingOutbound(false);
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
              <div className="shop-icon">📲</div>
              <div style={{ flex: 1 }}>
                <div className="shop-name">ABC ShopMitra</div>
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

            {/* Mode Switcher Tabs */}
            <div className="tab-bar">
              <button
                type="button"
                className={`tab-btn ${activeTab === 'outbound' ? 'active' : ''}`}
                onClick={() => setActiveTab('outbound')}
              >
                📞 Outbound Restock (Day 6)
              </button>
              <button
                type="button"
                className={`tab-btn ${activeTab === 'inbound' ? 'active' : ''}`}
                onClick={() => setActiveTab('inbound')}
              >
                💬 Inbound Chat
              </button>
            </div>
          </div>

          {activeTab === 'outbound' ? (
            <div className="outbound-panel">
              <div className="panel-header">
                <span className="badge">DAY 6 OUTBOUND CALL</span>
                <h3>Proactive Restock Nudge</h3>
                <p>ShopMitra calls customers when their regular monthly supply is due for reorder.</p>
              </div>

              <div className="form-group">
                <label>Customer Name</label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="e.g. Ramesh Kumar"
                />
              </div>

              <div className="form-group">
                <label>Phone Number</label>
                <input
                  type="text"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+91 98765 43210"
                />
              </div>

              <div className="form-group">
                <label>Restock Item (Order Rhythm)</label>
                <input
                  type="text"
                  value={restockItem}
                  onChange={(e) => setRestockItem(e.target.value)}
                  placeholder="e.g. Basmati Rice 5kg"
                />
              </div>

              <div className="form-group">
                <label>Telephony Outcome Handler</label>
                <select
                  value={simulateOutcome}
                  onChange={(e: any) => setSimulateOutcome(e.target.value)}
                >
                  <option value="CONNECTED">CONNECTED (Customer Answers)</option>
                  <option value="NO_ANSWER">NO ANSWER (Retry in 30 mins)</option>
                  <option value="BUSY">BUSY (Retry in 15 mins)</option>
                  <option value="VOICEMAIL">VOICEMAIL (Leave Voice Note)</option>
                  <option value="IMMEDIATE_HANGUP">IMMEDIATE HANGUP (Do Not Call Today)</option>
                </select>
              </div>

              {/* Step 4 Mandatory Opening Rule Card */}
              <div className="opening-rule-card">
                <div className="rule-title">⚠️ STEP 4 MANDATORY OPENING RULE</div>
                <div className="rule-step"><strong>1. Who:</strong> "Hello {customerName}! This is ShopMitra from ABC Local Store..."</div>
                <div className="rule-step"><strong>2. Why:</strong> "...calling regarding your monthly restock for {restockItem}."</div>
                <div className="rule-step"><strong>3. Opt-out:</strong> "...If you'd like to stop restock call reminders, just say opt out or let me know."</div>
              </div>

              <button
                type="button"
                className="dispatch-btn"
                onClick={handleTriggerOutbound}
                disabled={isCallingOutbound}
              >
                {isCallingOutbound ? '📞 Placing Outbound Call...' : '📲 Trigger Outbound Call'}
              </button>

              {outboundLog && (
                <div className="outbound-result">
                  <div className="result-header">
                    <span>CALL DISPATCH LOG</span>
                    <span className={`status-pill ${outboundLog.call_metadata?.simulate_outcome}`}>
                      {outboundLog.call_metadata?.simulate_outcome || 'SENT'}
                    </span>
                  </div>
                  <div className="result-detail">
                    <strong>Room Name:</strong> {outboundLog.roomName}<br />
                    <strong>Customer ID:</strong> {outboundLog.call_metadata?.user_id}<br />
                    <strong>Mandatory Intro:</strong> "{outboundLog.mandatory_opening?.who}"
                  </div>
                  {simulateOutcome !== 'CONNECTED' && (
                    <div className="retry-policy-box">
                      <strong>Outcome Rule Applied:</strong> {
                        simulateOutcome === 'NO_ANSWER' ? 'Ring timeout -> Retry 1 scheduled in 30 mins (max 2 retries).' :
                        simulateOutcome === 'BUSY' ? 'Line busy -> Retry 1 scheduled in 15 mins (max 3 retries).' :
                        simulateOutcome === 'VOICEMAIL' ? 'Voicemail detected -> Delivered restock audio note. No further retries.' :
                        'User hung up <5s -> Marked Do-Not-Call today to respect privacy.'
                      }
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="chat" ref={chatRef}>
                {messages.length === 0 ? (
                  <div className="msg bot">
                    <div className="msg-label">Mitra</div>
                    Namaste! 🙏 I'm Mitra, your assistant for ABC Shop. Ask me about orders, products, returns, or opt-out options.
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
            </>
          )}

          <div className="footnote">
            ABC ShopMitra • Day 6 Outbound Call Engine • Powered by Murf Falcon TTS
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
            max-width: 440px;
            height: min(800px, 94vh);
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
            padding: 18px 18px 14px;
            position: relative;
            color: #fbf3e7;
            border-bottom: 5px solid #f2a93b;
          }

          .bulbs {
            display: flex;
            justify-content: space-between;
            padding: 0 4px 8px;
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
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: #f2a93b;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
          }

          .shop-name {
            font-weight: 800;
            font-size: 21px;
            line-height: 1.1;
          }

          .shop-tag {
            font-size: 12px;
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
          }

          .voice-toggle {
            background: rgba(255,255,255,0.15);
            border: none;
            color: #fff;
            padding: 6px 10px;
            border-radius: 8px;
            cursor: pointer;
          }

          .tab-bar {
            display: flex;
            gap: 6px;
            margin-top: 14px;
            background: rgba(0,0,0,0.2);
            padding: 3px;
            border-radius: 10px;
          }

          .tab-btn {
            flex: 1;
            padding: 7px 10px;
            font-size: 11.5px;
            font-weight: 600;
            border: none;
            background: transparent;
            color: rgba(255,255,255,0.7);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .tab-btn.active {
            background: #f2a93b;
            color: #2b2118;
          }

          /* Outbound Panel */
          .outbound-panel {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: #fbf3e7;
          }

          .panel-header h3 {
            margin: 4px 0 2px;
            font-size: 17px;
            color: #7a1f2b;
          }

          .panel-header p {
            font-size: 12px;
            color: #666;
            margin: 0;
          }

          .badge {
            background: #1c6e63;
            color: #fff;
            font-size: 9.5px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            letter-spacing: 0.5px;
          }

          .form-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
          }

          .form-group label {
            font-size: 11.5px;
            font-weight: 600;
            color: #444;
          }

          .form-group input, .form-group select {
            padding: 8px 12px;
            border: 1px solid rgba(43,33,24,0.15);
            border-radius: 8px;
            font-size: 13px;
            background: #fff;
            color: #2b2118;
          }

          .opening-rule-card {
            background: #fff8eb;
            border: 1px solid #f2a93b;
            border-radius: 10px;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
            gap: 4px;
          }

          .rule-title {
            font-size: 10.5px;
            font-weight: 800;
            color: #7a1f2b;
            letter-spacing: 0.4px;
          }

          .rule-step {
            font-size: 11.5px;
            color: #333;
            line-height: 1.35;
          }

          .dispatch-btn {
            background: #7a1f2b;
            color: #fff;
            border: none;
            padding: 12px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s ease;
            margin-top: 4px;
          }

          .dispatch-btn:hover {
            background: #611722;
          }

          .outbound-result {
            background: #fff;
            border: 1px solid rgba(0,0,0,0.08);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 12px;
          }

          .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 700;
            font-size: 11px;
            color: #555;
          }

          .status-pill {
            background: #e2f5ec;
            color: #1c6e63;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
          }

          .status-pill.NO_ANSWER, .status-pill.BUSY {
            background: #fff0f0;
            color: #c0392b;
          }

          .retry-policy-box {
            background: #eef6f5;
            border-left: 3px solid #1c6e63;
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 11px;
            color: #1c6e63;
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

          .msg {
            max-width: 82%;
            padding: 11px 14px;
            border-radius: 16px;
            font-size: 14.5px;
            line-height: 1.45;
          }

          .msg.bot {
            align-self: flex-start;
            background: #fffdf8;
            border: 1px solid rgba(43,33,24,0.08);
            border-bottom-left-radius: 4px;
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

          .chips {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 6px 14px;
            background: #fbf3e7;
          }

          .chip {
            white-space: nowrap;
            padding: 6px 12px;
            border-radius: 16px;
            background: #fffdf8;
            border: 1px solid rgba(43,33,24,0.12);
            font-size: 12px;
            color: #2b2118;
            cursor: pointer;
          }

          .counter {
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            background: #fffdf8;
            border-top: 1px solid rgba(43,33,24,0.08);
          }

          .counter input {
            flex: 1;
            border: 1px solid rgba(43,33,24,0.15);
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 13.5px;
            outline: none;
          }

          .mic-btn, .send-btn {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border: none;
            background: #7a1f2b;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
          }

          .mic-btn.listening {
            background: #1c6e63;
            animation: pulse 1.2s infinite;
          }

          .footnote {
            text-align: center;
            font-size: 10px;
            color: #888;
            padding: 6px;
            background: #f4ea6f;
            color: #2b2118;
            font-weight: 600;
          }

          .listening-banner {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            background: #1c6e63;
            color: #fff;
            font-size: 12px;
          }

          .listening-banner.active {
            display: flex;
          }
        `}</style>
      </div>
    </section>
  );
}
