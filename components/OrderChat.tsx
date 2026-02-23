"use client";
import { useState, useRef, useEffect } from 'react';
import { Client } from '../app/page';

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

function formatChatMessage(text: string): string {
  if (!text) return "";
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  return escaped
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br />");
}

interface OrderChatProps {
  selectedClient: Client | null;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  refreshCart?: () => void;
}

export default function OrderChat({ selectedClient, messages, setMessages, refreshCart }: OrderChatProps) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const pendingVoiceSendRef = useRef(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const volumeHistory = useRef<number[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- LOGICA AUDIO VISUALIZER  ---
  useEffect(() => {
    if (!isRecording || !canvasRef.current || !analyserRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const barWidth = 2;
    const gap = 2;
    const maxBars = Math.ceil(rect.width / (barWidth + gap));
    const buffer = new Uint8Array(analyserRef.current.frequencyBinCount);
    let tick = 0;
    const render = () => {
      tick++;
      if (tick % 3 === 0) {
        analyserRef.current!.getByteFrequencyData(buffer);
        let sum = 0;
        const range = Math.floor(buffer.length / 2);
        for (let i = 0; i < range; i++) sum += buffer[i];
        const avg = sum / range;
        volumeHistory.current.push(avg);
        if (volumeHistory.current.length > maxBars + 4) volumeHistory.current.shift();
      }
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.fillStyle = '#374151';
      const history = volumeHistory.current;
      for (let i = 0; i < history.length; i++) {
        const val = history[history.length - 1 - i] || 0;
        let h = (val / 255) * rect.height * 1.5;
        h = Math.max(2, Math.min(h, rect.height));
        const x = rect.width - (i * (barWidth + gap)) - barWidth;
        const y = (rect.height - h) / 2;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, y, barWidth, h, 4);
        else ctx.rect(x, y, barWidth, h);
        ctx.fill();
      }
      animationRef.current = requestAnimationFrame(render);
    };
    render();
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current); };
  }, [isRecording]);

  // --- GESTIONE REGISTRAZIONE ---
  const startRecording = async () => {
    if (!selectedClient) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
            echoCancellation: true,
            autoGainControl: true,
            noiseSuppression: true
        }
      });

      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const recorder = new MediaRecorder(stream, {mimeType: 'audio/webm;codecs=opus'}); //codecs=opus formato piu' stabile per Whisper
      volumeHistory.current = [];
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        ctx.close();
        stream.getTracks().forEach(t => t.stop());
        if (pendingVoiceSendRef.current && audioChunksRef.current.length > 0) {
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          pendingVoiceSendRef.current = false;
          sendVoiceBlob(blob);
        }
      };

      mediaRecorder.current = recorder;
      recorder.start(1000);
      setIsRecording(true);
    } catch {
      alert("Impossibile accedere al microfono");
    }
  };

  const stopRecording = (save: boolean) => {
    if (!mediaRecorder.current) return;
    if (save) pendingVoiceSendRef.current = true;
    mediaRecorder.current.stop();
    setIsRecording(false);
  };

  const sendMessageContent = async (userMessage: string, isVoice = false) => {
    if (!selectedClient) return;
    const displayContent = isVoice ? `🎙️ ${userMessage}` : userMessage;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: displayContent };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);
    const history = [...messages, { role: 'user' as const, content: displayContent }].slice(-10).map((m) => ({ role: m.role, content: m.content }));
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, clientId: selectedClient.cod_cli, history }),
      });
      const data = await response.json();
      if (data.success) {
        const assistantMsg: Message = { id: Date.now().toString(), role: 'assistant', content: data.response };
        setMessages(prev => [...prev, assistantMsg]);
        const productItems = Array.isArray(data.product_items) && data.product_items.length > 0
          ? data.product_items.map((it: { cod_art: string; quantity?: number }) => ({ cod_art: it.cod_art, qta: Number(it.quantity) || 1 }))
          : (data.product_codes || []).map((cod_art: string) => ({ cod_art, qta: 1 }));
        const orderConfirmed = data.order_confirmed === true;
        if (orderConfirmed && productItems.length >= 1 && selectedClient) {
          try {
            const failed: string[] = [];
            for (const { cod_art, qta } of productItems) {
              const cartResponse = await fetch('/api/cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'add', cod_cli: selectedClient.cod_cli, cod_art, qta }),
              });
              if (!cartResponse.ok) failed.push(cod_art);
            }
            refreshCart?.();
            if (failed.length > 0) {
              const followUp: Message = {
                id: (Date.now() + 2).toString(),
                role: 'assistant',
                content: failed.length === productItems.length
                  ? 'Ho provato ad aggiungere i prodotti al carrello, ma al momento non risultano disponibili per te. Prova a chiedere altre opzioni.'
                  : `Alcuni prodotti non risultano al momento disponibili e non sono stati aggiunti al carrello (codici: ${failed.join(', ')}). Gli altri sono stati inseriti.`,
              };
              setMessages(prev => [...prev, followUp]);
            }
          } catch {
            setMessages(prev => [...prev, { id: (Date.now() + 2).toString(), role: 'assistant', content: 'Non sono riuscito ad aggiornare il carrello. Riprova tra poco.' }]);
          }
        }
      } else {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: data.error || 'Errore di connessione. Verifica che il servizio sia attivo.' }]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', content: 'Errore di connessione. Verifica che il servizio sia attivo.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendVoiceBlob = async (blob: Blob) => {
    if (!selectedClient) return;
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', blob, 'audio.webm');
      const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
      const json = await res.json();
      if (!res.ok) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: json.error || 'Trascrizione non disponibile. Riprova.' }]);
        return;
      }
      const text = (json.text || '').trim();
      if (!text) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: '🎙️ (nessun testo riconosciuto)' }, { id: (Date.now() + 1).toString(), role: 'assistant', content: 'Non ho capito nulla dall\'audio. Puoi ripetere o scrivere?' }]);
        return;
      }
      await sendMessageContent(text, true);
    } catch (e) {
      console.error('Transcribe error:', e);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: 'Impossibile trascrivere l\'audio. Verifica il microfono e riprova.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedClient) return;
    const userMessage = input.trim();
    setInput('');
    await sendMessageContent(userMessage, false);
  };

  return (
    <div className={`flex flex-col h-full w-full bg-white overflow-hidden transition-opacity duration-300 ${!selectedClient ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>

      {/* AREA MESSAGGI */}
      <div className="flex-1 overflow-y-auto p-3 md:p-4 space-y-3 bg-gray-50/50 custom-scrollbar">
        {!selectedClient ? (
          <div className="h-full flex items-center justify-center text-center p-8">
            <p className="text-gray-400 italic text-sm">Identifica un cliente per iniziare</p>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] px-4 py-2.5 rounded-xl text-sm md:text-[15px] shadow-sm animate-in zoom-in-95 duration-200 ${m.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-gray-800 border border-gray-100 rounded-bl-none'
                }`}>
                {m.role === "assistant" ? (
                  <span className="break-words [&_strong]:font-semibold" dangerouslySetInnerHTML={{ __html: formatChatMessage(m.content) }} />
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white text-gray-800 border border-gray-100 rounded-2xl rounded-bl-none px-5 py-3 max-w-[85%]">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
              </div>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* AREA INPUT */}
      <div className="p-2 md:p-3 bg-white border-t border-gray-100">
        {isRecording ? (
          <div className="h-10 bg-gray-50 rounded-lg border border-gray-200 flex items-center px-2 animate-in fade-in duration-200">
            <div className="flex-1 h-full overflow-hidden flex items-center pl-3">
              <canvas ref={canvasRef} className="w-full h-6" />
            </div>
            <div className="flex gap-1 pr-1">
              <button
                onClick={() => stopRecording(false)}
                className="w-8 h-8 flex items-center justify-center text-gray-400 hover:bg-gray-200 rounded-lg transition-colors text-sm"
              >
                ✕
              </button>
              <button
                onClick={() => stopRecording(true)}
                className="w-8 h-8 flex items-center justify-center bg-black text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
              >
                ✓
              </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2 h-10">
            <input
              ref={inputRef}
              type="text"
              disabled={!selectedClient}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSend();
                  inputRef.current?.blur();
                }
              }}
              placeholder={selectedClient ? "Scrivi o registra..." : "Seleziona cliente..."}
              className="flex-1 bg-gray-50 rounded-lg px-4 text-sm outline-none focus:bg-white transition-all text-gray-900 border border-transparent focus:border-blue-200 disabled:cursor-not-allowed"
            />
            <button
              onClick={() => {
                if (input.trim()) {
                  handleSend();
                  inputRef.current?.blur();
                } else {
                  startRecording();
                }
              }}
              disabled={!selectedClient && !input.trim()}
              className={`w-10 h-10 rounded-lg shadow-sm flex items-center justify-center transition-all active:scale-95 ${input.trim() ? 'bg-blue-600 text-white' : 'bg-black text-white'
                } disabled:bg-gray-200`}
            >
              {input.trim() ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}