"use client";
import { useState, useEffect } from 'react';
import Image from 'next/image';

interface Client {
  cod_cli: number;
  rag_soc: string;
}

interface ClientSelectorProps {
  onClientChange: (client: Client | null) => void;
}

export default function ClientSelector({ onClientChange }: ClientSelectorProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Client[]>([]);
  const [selected, setSelected] = useState<Client | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selected) {
      setResults([]);
      return;
    }

    const timer = setTimeout(() => {
      setLoading(true);
      fetch(`/api/clients/search?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
          setResults(Array.isArray(data) ? data : []);
          setLoading(false);
        })
        .catch(() => {
          setResults([]);
          setLoading(false);
        });
    }, 300);

    return () => clearTimeout(timer);
  }, [query, selected]);

  const handleSelect = (client: Client) => {
    setSelected(client);
    setQuery(client.rag_soc);
    setResults([]);           
    onClientChange(client); 
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    
    if (selected) {
      setSelected(null);
      onClientChange(null);
    }
  };

  return (
    <div className="bg-white border-b border-gray-200 p-4 sticky top-0 z-40 shadow-sm w-full">
      <div className="max-w-7xl mx-auto flex items-center gap-4">
        
        <div className="shrink-0">
          <Image 
            src="/icon.png" 
            alt="Logo Ergon" 
            width={40} 
            height={40} 
            className="rounded-lg object-contain"
            priority
          />
        </div>

        {/* INPUT DI RICERCA */}
        <div className="relative flex-1 max-w-md">
          <label className="absolute -top-2 left-3 bg-white px-1 text-[9px] font-black text-gray-400 uppercase tracking-widest z-10 pointer-events-none">
            identifica cliente
          </label>
          
          <input
            type="text"
            value={query}
            onChange={handleInputChange}
            placeholder="Cerca per nome o codice (es: 70)..."
            className={`w-full p-3 border-2 rounded-2xl outline-none text-sm transition-all ${
              selected 
                ? 'border-green-500 bg-green-50 font-bold text-green-900' 
                : 'border-gray-100 focus:border-blue-400 shadow-sm text-gray-800'
            }`}
          />

          {loading && (
            <div className="absolute right-4 top-3.5">
               <div className="w-4 h-4 border-2 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
          )}

          {results.length > 0 && !selected && (
            <div className="absolute w-full mt-2 bg-white border border-gray-100 rounded-2xl shadow-xl z-50 max-h-60 overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
              {results.map((c) => (
                <div 
                  key={c.cod_cli} 
                  onClick={() => handleSelect(c)} 
                  className="p-4 hover:bg-blue-50 cursor-pointer flex justify-between items-center group transition-colors"
                >
                  <span className="text-sm font-bold text-gray-800 group-hover:text-blue-700">
                    {c.rag_soc}
                  </span>
                  <span className="text-[10px] font-mono bg-gray-100 px-2 py-1 rounded text-gray-500 group-hover:bg-blue-100 group-hover:text-blue-600">
                    {c.cod_cli}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {selected && (
          <div className="hidden md:flex items-center gap-2 text-green-700 bg-green-50 px-4 py-2 rounded-full border border-green-100 animate-in fade-in zoom-in-95 duration-300">
             <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
             <span className="text-[10px] font-black uppercase tracking-widest">sessione attiva</span>
          </div>
        )}
      </div>
    </div>
  );
}