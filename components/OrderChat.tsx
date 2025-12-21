"use client";

import { useState, useRef, useEffect } from 'react';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

export default function OrderChat() {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  
  // Simulazione utente loggato (per il PoC)
  const userContext = "Mario Rossi • Ristorante Da Luigi";

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `Ciao Mario! Sono pronto a ricevere il tuo ordine per il ${userContext.split('•')[1].trim()}.`
    }
  ]);

  // Refs
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const volumeHistory = useRef<number[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Visualizer Logic
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
        if (volumeHistory.current.length > maxBars + 4) {
          volumeHistory.current.shift();
        }
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

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isRecording]);

  // Audio Logic
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.6;
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
      console.error(e);
      alert("Microfono non disponibile");
    }
  };

  const stopRecording = (save: boolean) => {
    if (!mediaRecorder.current) return;
    mediaRecorder.current.stop();
    setIsRecording(false);

    if (save) {
      setInput(prev => (prev ? prev + " " : "") + "Vorrei ordinare 3 casse di acqua e 5kg di pane.");
    }
  };

  const send = () => {
    if (!input.trim()) return;
    const text = input;
    setInput('');
    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: text }]);
    
    setTimeout(() => {
      setMessages(prev => [...prev, { 
        id: Date.now().toString(), 
        role: 'assistant', 
        content: 'Ricevuto. Procedo con la verifica a magazzino.' 
      }]);
    }, 800);
  };

  return (
    <div className="flex flex-col h-[75vh] w-full max-w-lg mx-auto bg-white shadow-2xl rounded-2xl overflow-hidden border border-gray-100 ring-1 ring-gray-900/5">
      
      {/* Header Personalizzato */}
      <div className="bg-white p-5 border-b border-gray-100 flex items-center justify-between shadow-sm relative z-10">
        <div>
          <h1 className="text-lg font-bold text-gray-800 tracking-tight">SmartOrder</h1>
          {/* Nome Utente Simulato */}
          <p className="text-[12px] text-gray-500 font-medium tracking-wide flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            {userContext}
          </p>
        </div>
        
        {/* Puntino Verde */}
        <div className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-[15px] shadow-sm ${
                m.role === 'user' 
                  ? 'bg-blue-600 text-white rounded-br-none' 
                  : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
              }`}>
              {m.content}
            </div>
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 bg-white border-t border-gray-100">
        {isRecording ? (
          // Recording State
          <div className="h-12 bg-white rounded-full shadow-sm border border-gray-200 flex items-center pl-2 pr-2 animate-in slide-in-from-bottom-2 duration-200">
            
            <div className="flex-1 h-full overflow-hidden flex items-center pl-2">
               <canvas ref={canvasRef} className="w-full h-full" />
            </div>

            <div className="flex gap-1 pl-2">
              <button onClick={() => stopRecording(false)} className="w-9 h-9 flex items-center justify-center text-gray-400 hover:bg-gray-100 rounded-full transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
              <button onClick={() => stopRecording(true)} className="w-9 h-9 flex items-center justify-center bg-black text-white rounded-full hover:bg-gray-800 transition-transform active:scale-95 shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
          </div>
        ) : (
          // Text State
          <div className="flex gap-2 h-12">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Scrivi messaggio..."
              className="flex-1 bg-gray-100 rounded-full px-5 text-[15px] outline-none focus:bg-white focus:ring-1 focus:ring-gray-300 transition-all text-gray-900 placeholder-gray-500"
            />
            
            {input.trim() ? (
               <button onClick={send} className="w-12 bg-blue-600 text-white rounded-full hover:bg-blue-700 shadow-sm flex items-center justify-center transition-transform active:scale-95">
                 <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
               </button>
            ) : (
               <button onClick={startRecording} className="w-12 bg-black text-white rounded-full hover:opacity-80 shadow-sm flex items-center justify-center transition-transform active:scale-95">
                 <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
               </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}