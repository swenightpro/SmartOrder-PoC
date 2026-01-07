"use client";
import { useState, useRef, useEffect } from 'react';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

export default function OrderChat({ selectedClient }: { selectedClient: any }) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  
  // Refs per l'audio visualizer
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const volumeHistory = useRef<number[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Reset chat al cambio cliente
  useEffect(() => {
    setMessages(selectedClient ? [{
      id: 'welcome',
      role: 'assistant',
      content: `Ciao ${selectedClient.rag_soc}! Cosa ti serve oggi?`
    }] : []);
  }, [selectedClient]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- LOGICA AUDIO VISUALIZER (Snippet grafico, lo teniamo?) -----------------------------------
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
  // ----------------------------------------------------------------------------------------------------

  // --- GESTIONE REGISTRAZIONE ---
  const startRecording = async () => {
    if (!selectedClient) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const recorder = new MediaRecorder(stream);
      volumeHistory.current = [];

      recorder.onstop = () => {
        ctx.close();
        stream.getTracks().forEach(t => t.stop());
      };

      mediaRecorder.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (e) {
      alert("Impossibile accedere al microfono");
    }
  };

  const stopRecording = (save: boolean) => {
    if (!mediaRecorder.current) return;
    mediaRecorder.current.stop();
    setIsRecording(false);

    if (save) {
      // Qui invieremo l'audio all'AI, per ora simuliamo un messaggio utente generico
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: "🎙️ (Messaggio Vocale)" }]);
    }
  };

  const handleSend = () => {
    if (!input.trim() || !selectedClient) return;
    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: input }]);
    setInput('');
  };

  return (
    <div className={`flex flex-col h-full w-full bg-white overflow-hidden transition-opacity duration-300 ${!selectedClient ? 'opacity-50 pointer-events-none' : 'opacity-100'}`} >

      {/* AREA MESSAGGI */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50/50 custom-scrollbar">
        {!selectedClient ? (
          <div className="h-full flex items-center justify-center text-center p-8">
            <p className="text-gray-400 italic text-sm">Identifica un cliente per iniziare</p>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] px-5 py-3 rounded-2xl text-[15px] shadow-sm animate-in zoom-in-95 duration-200 ${m.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-gray-800 border border-gray-100 rounded-bl-none'
                }`}>
                {m.content}
              </div>
            </div>
          ))
        )}
        <div ref={scrollRef} />
      </div>

      {/* AREA INPUT */}
      <div className="p-4 bg-white border-t border-gray-100">
        {isRecording ? (
          <div className="h-14 bg-gray-50 rounded-full border border-gray-200 flex items-center px-2 animate-in fade-in duration-200">
            <div className="flex-1 h-full overflow-hidden flex items-center pl-4">
              <canvas ref={canvasRef} className="w-full h-8" />
            </div>
            <div className="flex gap-1 pr-2">
              <button onClick={() => stopRecording(false)} className="w-10 h-10 flex items-center justify-center text-gray-400 hover:bg-gray-200 rounded-full transition-colors">✕</button>
              <button onClick={() => stopRecording(true)} className="w-10 h-10 flex items-center justify-center bg-black text-white rounded-full hover:scale-105 transition-transform">✓</button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2 h-14">
            <input
              type="text"
              disabled={!selectedClient}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder={selectedClient ? "Scrivi o registra il tuo ordine..." : "Seleziona cliente..."}
              className="flex-1 bg-gray-50 rounded-full px-6 text-[15px] outline-none focus:bg-white transition-all text-gray-900 border border-transparent focus:border-blue-200 disabled:cursor-not-allowed"
            />
            <button
              onClick={input.trim() ? handleSend : startRecording}
              disabled={!selectedClient && !input.trim()}
              className={`w-14 rounded-full shadow-md flex items-center justify-center transition-all active:scale-95 ${input.trim() ? 'bg-blue-600 text-white' : 'bg-black text-white'} disabled:bg-gray-200`}
            >
              {input.trim() ? (
                // Icona Invio
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
              ) : (
                // Icona Microfono
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}