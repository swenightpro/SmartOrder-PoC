"use client";
import { useState, useEffect, useCallback } from 'react';

// --- TIPI ---
interface Product {
  cod_art: string;
  des_art: string;
  des_um: string;
  pezzi_conf: number;
  des_tipo_um: string;
  stato?: string;
  linea?: string;
  famiglia?: string;
}

interface CartItem {
  id: number;
  cod_art: string | null;
  des_art?: string;
  descrizione_libera?: string;
  qta_ordinata: number;
  linea?: string;
  famiglia?: string;
  des_um?: string;
  pezzi_conf?: number;
  des_tipo_um?: string;
}

const BLOCKING_STATUSES = ["ARTICOLO SOSPESO", "SU AUTORIZZAZIONE", "DISPONIBILE DAL"];

export default function OrderCanvas({ currentClient, onClose, onOrderSuccess }: any) {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [qty, setQty] = useState<number>(1);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [error, setError] = useState('');

  // --- LOGICA DATI ---

  const fetchCart = useCallback(async () => {
    if (!currentClient?.cod_cli) {
      setCart([]);
      return;
    }
    try {
      const res = await fetch(`/api/cart?cod_cli=${currentClient.cod_cli}`);
      if (res.ok) {
        const data = await res.json();
        setCart(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error("Errore fetch carrello", e);
    }
  }, [currentClient]);

  useEffect(() => { fetchCart(); }, [fetchCart]);

  // Gestione Ricerca
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm.length >= 2 && !selectedProduct && currentClient?.cod_cli) {
        fetch(`/api/products/search?q=${encodeURIComponent(searchTerm)}&cod_cli=${currentClient.cod_cli}`)
          .then(res => res.json())
          .then(data => setSuggestions(Array.isArray(data) ? data : []))
          .catch(() => setSuggestions([]));
      } else {
        setSuggestions([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, selectedProduct, currentClient]);

  // --- AZIONI ---

  const handleSelectProduct = (product: Product) => {
    setSelectedProduct(product);
    setSuggestions([]);
    setQty(1);
    setError('');
  };

  // Logica blocco
  const isBlocked = selectedProduct ? BLOCKING_STATUSES.some(s => 
    selectedProduct.stato?.toUpperCase().includes(s)
  ) : false;

  const addToCart = async () => {
    if (!selectedProduct || isBlocked || !currentClient?.cod_cli) return;
    setError('');

    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          action: 'add',
          cod_cli: currentClient.cod_cli,
          cod_art: selectedProduct.cod_art,
          qta: Math.max(1, qty)
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Errore aggiunta articolo");
      }

      await fetchCart();
      setSelectedProduct(null);
      setSearchTerm('');
      setQty(1);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const removeFromCart = async (id: number) => {
    try {
      await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'remove', id })
      });
      fetchCart();
    } catch (e) { console.error("Errore rimozione", e); }
  };

  const handleSendFullOrder = async () => {
    if (cart.length === 0) return;
    setError('');
    
    try {
      const res = await fetch('/api/orders/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          cod_cli: currentClient.cod_cli, 
          items: cart.map(i => ({ 
            cod_art: i.cod_art, 
            qty: i.qta_ordinata,
            descrizione_libera: i.descrizione_libera
          })) 
        })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Errore invio ordine");
      }

      onOrderSuccess();
      onClose();
    } catch (err: any) { 
      setError(err.message); 
    }
  };

  // --- RENDER ---

  return (
    <div className="h-full bg-white rounded-[32px] rounded-l-md shadow-sm border border-gray-200 flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
      
      {/* HEADER */}
      <div className="flex justify-between items-center p-4 border-b border-gray-100 bg-gray-50/50">
        <h2 className="text-lg font-bold text-gray-800 tracking-tight flex items-center gap-2">
           <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
           Crea Ordine
        </h2>
        <button onClick={onClose} className="text-xs font-bold text-gray-400 hover:text-gray-600 uppercase tracking-wider hover:bg-gray-100 px-3 py-1.5 rounded-lg transition-all">
          Chiudi ✕
        </button>
      </div>

      {/* BODY */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden">
        
        {/* BOX AGGIUNTA ARTICOLO */}
        <div className="space-y-4 mb-4 bg-gray-50 p-4 rounded-[24px] border border-gray-100 shadow-inner shrink-0 relative z-20">
          <div className="relative">
            <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">
              AGGIUNGI ARTICOLO
            </label>
            <input
              type="text"
              autoComplete="off"
              value={selectedProduct ? selectedProduct.des_art : searchTerm}
              onChange={(e) => { 
                setSearchTerm(e.target.value); 
                setSelectedProduct(null); 
                setError(''); 
              }}
              className="w-full p-3.5 border border-gray-200 rounded-xl outline-none text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all bg-white"
              placeholder="Digita nome o codice..."
            />
            
            {/* Suggerimenti */}
            {suggestions.length > 0 && (
              <div className="absolute w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl z-[110] max-h-[250px] overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
                {suggestions.map((p) => (
                  <div 
                    key={p.cod_art} 
                    onClick={() => handleSelectProduct(p)} 
                    className="p-3 hover:bg-blue-50 cursor-pointer group transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <span className="shrink-0 bg-gray-100 text-gray-600 text-[10px] font-mono px-1.5 py-0.5 rounded border border-gray-200 group-hover:bg-blue-100 group-hover:text-blue-700 group-hover:border-blue-200 transition-colors mt-0.5">
                        {p.cod_art}
                      </span>
                      <div className="flex-1 min-w-0">
                         <p className="text-sm font-bold text-gray-800 leading-tight group-hover:text-blue-900">
                           {p.des_art}
                         </p>
                         <p className="text-[10px] text-gray-500 mt-1 flex items-center gap-1.5">
                           <span className="uppercase tracking-tight text-gray-400">{p.linea} / {p.famiglia}</span>
                         </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* DETTAGLIO PRODOTTO SELEZIONATO */}
          {selectedProduct && (
            <div className={`p-4 rounded-xl border animate-in zoom-in-95 ${isBlocked ? 'bg-red-50 border-red-100' : 'bg-white border-blue-100'}`}>
              
              <div className="flex items-center justify-between mb-3">
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${isBlocked ? 'bg-red-100 text-red-700 border-red-200' : 'bg-gray-100 text-gray-600 border-gray-200'}`}>
                  {selectedProduct.cod_art}
                </span>
                <div className="text-[10px] text-gray-400 uppercase tracking-tight text-right">
                   {selectedProduct.linea} <span className="text-gray-300">/</span> {selectedProduct.famiglia}
                </div>
              </div>

              <div className="mb-4">
                 <p className="text-xs text-gray-500">
                   Venduto in <span className="font-bold text-gray-700">{selectedProduct.des_um} ({selectedProduct.pezzi_conf} {selectedProduct.des_tipo_um})</span>
                 </p>
              </div>

              <div className="flex justify-between items-center gap-4">
                <div className="flex-1">
                  <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block mb-1">quantità</span>
                  <input 
                    type="number" 
                    min="1"
                    value={qty} 
                    onChange={(e) => setQty(Number(e.target.value))}
                    className="w-full p-2 border-2 border-gray-100 rounded-lg text-center text-lg font-black text-gray-800 outline-none focus:border-blue-500 transition-colors bg-white"
                  />
                </div>
                <button 
                  onClick={addToCart}
                  disabled={isBlocked}
                  className="bg-black text-white px-8 py-3 rounded-xl font-bold hover:bg-gray-800 disabled:bg-gray-200 disabled:text-gray-400 mt-5 shadow-lg hover:shadow-xl active:scale-95 transition-all"
                >
                  AGGIUNGI
                </button>
              </div>
              
              {selectedProduct.stato && (
                <div className={`mt-3 p-2 rounded-lg text-[10px] font-bold uppercase tracking-tight flex items-center gap-2 ${isBlocked ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                   <span>{isBlocked ? '✕' : '✓'}</span> {selectedProduct.stato}
                </div>
              )}
            </div>
          )}
        </div>

        {/* LISTA CARRELLO */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-2 custom-scrollbar -mr-2">
          <div className="flex items-center justify-between mb-2">
             <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest">CARRELLO</label>
             <span className="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full font-bold">{cart.length} Articoli</span>
          </div>

          {cart.length === 0 ? (
            <div className="h-40 flex flex-col items-center justify-center border-2 border-dashed border-gray-100 rounded-[24px] text-gray-300 text-sm italic text-center px-10 gap-2">
              <span className="opacity-50 text-2xl">🛒</span>
              <span>Nessun articolo</span>
            </div>
          ) : (
            <div className="space-y-3 pb-2">
              {cart.map((item) => {
                const isDraft = !item.cod_art;
                
                return (
                  <div key={item.id} className={`relative flex items-start justify-between p-4 border rounded-2xl shadow-sm transition-all animate-in slide-in-from-bottom-2 ${
                    isDraft ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-100 hover:border-blue-200'
                  }`}>
                    
                    <div className="flex-1 min-w-0 pr-4">
                      {/* Titolo e Codice */}
                      <div className="flex items-start gap-2 mb-1">
                        {!isDraft && (
                           <span className="shrink-0 bg-gray-100 text-gray-600 text-[9px] font-mono px-1.5 py-0.5 rounded border border-gray-200 mt-0.5">
                             {item.cod_art}
                           </span>
                        )}
                        <p className={`text-sm font-bold leading-tight ${isDraft ? 'text-amber-900 italic' : 'text-gray-800'}`}>
                          {isDraft ? item.descrizione_libera : item.des_art}
                        </p>
                      </div>

                      {/* Info Tecniche */}
                      {!isDraft && (
                        <div className="mb-2 text-[10px] text-gray-400 flex items-center gap-1.5 pl-0.5">
                           <span className="uppercase">{item.linea}</span>
                           <span className="text-gray-300">/</span>
                           <span className="font-medium text-gray-500">{item.famiglia}</span>
                        </div>
                      )}

                      {/* Footer Riga (Qta o Errore) */}
                      {isDraft ? (
                        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-amber-600 bg-amber-100/50 px-2 py-1 rounded-md w-fit">
                          <span>⚠️ Prodotto non identificato</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-md text-[11px] font-bold">
                            Qta: {item.qta_ordinata}
                          </span>
                          <span className="text-[10px] text-gray-400">
                             Venduto in {item.des_um} ({item.pezzi_conf} {item.des_tipo_um})
                          </span>
                        </div>
                      )}
                    </div>
                    
                    {/* Pulsante Rimuovi */}
                    <button onClick={() => removeFromCart(item.id)} className="shrink-0 p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                      ✕
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* FOOTER */}
        <div className="pt-4 border-t border-gray-100 mt-2">
           {error && (
            <div className="mb-3 p-3 bg-red-50 text-red-600 rounded-xl text-[11px] font-bold border border-red-100 flex items-center gap-2 animate-pulse">
              ⚠️ {error}
            </div>
          )}
          
          <button 
            onClick={handleSendFullOrder}
            disabled={cart.length === 0}
            className="w-full bg-black text-white py-5 rounded-[24px] font-black text-lg shadow-xl hover:bg-gray-800 disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none transition-all active:scale-95 flex justify-center items-center gap-2"
          >
            CONFERMA E INVIA
          </button>
        </div>
      </div>
    </div>
  );
}