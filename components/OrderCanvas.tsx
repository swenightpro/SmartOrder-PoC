"use client";
import { useState, useEffect } from 'react';
import { Client } from '../app/page';

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

export interface CartItem {
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

interface OrderCanvasProps {
  currentClient: Client | null;
  onClose?: () => void;
  onOrderSuccess: () => void;
  isMobile?: boolean;
  cart: CartItem[];
  refreshCart: () => void;
}

export default function OrderCanvas({ currentClient, onClose, onOrderSuccess, isMobile = false, cart, refreshCart }: OrderCanvasProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [qty, setQty] = useState<number | ''>(1);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm.length >= 2 && !selectedProduct && currentClient?.cod_cli) {
        performSearch(searchTerm);
      } else {
        setSuggestions([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, selectedProduct, currentClient]);

  const performSearch = (query: string) => {
    if (!currentClient?.cod_cli) return;
    fetch(`/api/products/search?q=${encodeURIComponent(query)}&cod_cli=${currentClient.cod_cli}`)
      .then(res => res.json())
      .then(data => setSuggestions(Array.isArray(data) ? data : []))
      .catch(() => setSuggestions([]));
  };

  const handleSelectProduct = (product: Product) => {
    setSelectedProduct(product);
    setSuggestions([]);
    setQty(1);
    setError('');
  };

  const isBlocked = selectedProduct ? BLOCKING_STATUSES.some(s =>
    selectedProduct.stato?.toUpperCase().includes(s)
  ) : false;

  const handleQtyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value === '') {
      setQty('');
    } else {
      const numValue = parseInt(value);
      if (!isNaN(numValue) && numValue >= 0) setQty(numValue);
    }
  };

  const addToCart = async () => {
    if (!selectedProduct || isBlocked || !currentClient?.cod_cli || qty === '' || qty === 0) return;
    setError('');
    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'add',
          cod_cli: currentClient.cod_cli,
          cod_art: selectedProduct.cod_art,
          qta: typeof qty === 'number' ? qty : 1
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Errore aggiunta articolo");
      }
      refreshCart();
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
      refreshCart();
    } catch (e) { console.error("Errore rimozione", e); }
  };

  const handleSendFullOrder = async () => {
    if (cart.length === 0 || !currentClient) return;
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
      if (onClose) onClose();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // --- RENDER ---

  // Layout Mobile
  if (isMobile) {
    return (
      <div className="h-full bg-white flex flex-col overflow-hidden relative">
        <div className="flex-1 flex gap-1 p-1 overflow-hidden">
          {/* SINISTRA: RICERCA E AGGIUNTA */}
          <div className="w-1/2 flex flex-col gap-1 overflow-hidden border-r border-gray-200 pr-1 relative">
            <div className="shrink-0 px-1">
              <span className="text-[8px] font-bold text-gray-400 uppercase">Aggiungi Articolo</span>
            </div>
            <div className="shrink-0 relative">
              <input
                type="text"
                autoComplete="off"
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setError(""); }}
                onFocus={() => {
                  if (searchTerm.length >= 2 && !selectedProduct) {
                    performSearch(searchTerm);
                  }
                }}
                onBlur={() => {
                  setTimeout(() => setSuggestions([]), 200);
                }}
                className="w-full p-2 border border-gray-200 rounded-lg outline-none text-[11px] focus:border-blue-500 bg-white shadow-sm"
                placeholder="Cerca articolo..."
              />
              {/* SUGGESTIONS MOBILE */}
              {suggestions.length > 0 && (
                <div className="absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-[110] max-h-[150px] overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
                  {suggestions.map((p) => (
                    <div
                      key={p.cod_art}
                      onClick={() => handleSelectProduct(p)}
                      className="p-2 hover:bg-blue-50 cursor-pointer group transition-colors"
                    >
                      <p className="text-[10px] font-bold text-gray-800 leading-tight group-hover:text-blue-900 mb-0.5">{p.des_art}</p>
                      <div className="flex items-center gap-1 text-[8px] text-gray-400">
                        <span className="bg-gray-100 text-gray-600 font-mono px-1 py-0.5 rounded">{p.cod_art}</span>
                        <span>•</span>
                        <span>{p.linea}</span>
                        <span>/</span>
                        <span>{p.famiglia}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* BOX PRODOTTO SELEZIONATO MOBILE */}
            {selectedProduct && (
              <div className="absolute top-[28px] left-0 right-1 z-[120] animate-in slide-in-from-top duration-200">
                <div className={`p-2 border rounded-lg shadow-xl space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto custom-scrollbar ${isBlocked ? "bg-red-50 border-red-200" : "bg-white border-gray-100"}`}>
                  <p className="text-[10px] font-bold leading-tight text-gray-800">{selectedProduct.des_art}</p>
                  <div className="text-[8px] text-gray-400 flex items-center gap-1">
                    <span className="bg-gray-100 text-gray-600 font-mono px-1 py-0.5 rounded">{selectedProduct.cod_art}</span>
                    <span>•</span>
                    <span>{selectedProduct.linea}</span>
                    <span>/</span>
                    <span>{selectedProduct.famiglia}</span>
                  </div>
                  <div className="text-[8px] text-gray-500">
                    Venduto in {selectedProduct.des_um} ({selectedProduct.pezzi_conf} {selectedProduct.des_tipo_um})
                  </div>

                  {selectedProduct.stato && (
                    <div className={`text-[8px] font-bold px-1.5 py-0.5 rounded w-fit ${isBlocked ? "bg-red-100 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                      {isBlocked ? "⛔" : "⚠️"} {selectedProduct.stato}
                    </div>
                  )}

                  <div className="flex items-center gap-1">
                    <input type="number" min="1" value={qty} onChange={handleQtyChange} className="w-12 p-1 border border-gray-200 rounded text-center text-[10px] font-bold text-gray-800 bg-white" />
                    <button onClick={addToCart} disabled={isBlocked || qty === '' || qty === 0} className="bg-black text-white px-2 py-1 rounded text-[10px] font-bold hover:bg-gray-800 disabled:bg-gray-200 disabled:text-gray-400">+</button>
                    <button onClick={() => { setSelectedProduct(null); setSearchTerm(""); setQty(1); setError(""); }} className="p-1 border border-gray-200 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded text-[10px]">✕</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* DESTRA: CARRELLO */}
          <div className="w-1/2 flex flex-col gap-1 overflow-hidden pl-1">
            <div className="flex items-center justify-between px-1">
              <span className="text-[8px] font-bold text-gray-400 uppercase">Carrello</span>
              <span className="text-[8px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full font-bold">{cart.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1 custom-scrollbar pr-1">
              {cart.map((item) => {
                const isDraft = !item.cod_art;
                return (
                  <div key={item.id} className={`p-2 border rounded-lg shadow-sm ${isDraft ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-100'}`}>
                    <div className="flex items-start justify-between gap-1">
                      <div className="flex-1 min-w-0">
                        <p className={`text-[10px] font-bold leading-tight mb-1 ${isDraft ? 'text-amber-900 italic' : 'text-gray-800'}`}>{item.des_art || item.descrizione_libera}</p>

                        {/* RIPRISTINATO: Dettagli nel carrello */}
                        {!isDraft && (
                          <>
                            <div className="text-[8px] text-gray-400 flex items-center gap-1 mb-1">
                              <span className="bg-gray-100 text-gray-600 font-mono px-1 py-0.5 rounded">{item.cod_art}</span>
                              <span>•</span>
                              <span>{item.linea}</span>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="bg-blue-50 text-blue-700 border border-blue-100 px-1.5 py-0.5 rounded text-[9px] font-bold inline-block">Qta: {item.qta_ordinata}</span>
                              <span className="text-[8px] text-gray-400">{item.des_um} ({item.pezzi_conf} {item.des_tipo_um})</span>
                            </div>
                          </>
                        )}
                      </div>
                      <button onClick={() => removeFromCart(item.id)} className="p-1 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded text-[10px]">✕</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* FOOTER MOBILE - CHAT */}
        <div className="p-1 border-t border-gray-100 shrink-0">
          <button
            onClick={handleSendFullOrder}
            disabled={cart.length === 0}
            className="w-full h-8 bg-black text-white rounded-lg font-bold text-sm shadow-sm hover:bg-gray-800 disabled:bg-gray-100 disabled:text-gray-400 transition-all flex justify-center items-center gap-2"
          >
            CONFERMA E INVIA
          </button>
        </div>
      </div>
    );
  }

  // Layout Desktop
  return (
    <div className="h-full bg-white flex flex-col overflow-hidden">
      <div className="flex-1 flex flex-col pt-3 px-1 pb-0.5 overflow-hidden">
        <div className="space-y-3 mb-3 shrink-0 relative z-20">
          {!selectedProduct && (
            <div className="relative">
              <label className="block text-[9px] font-black text-gray-400 uppercase mb-1.5 tracking-widest">AGGIUNGI ARTICOLO</label>
              <input
                type="text"
                autoComplete="off"
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setError(""); }}
                onFocus={() => {
                  if (searchTerm.length >= 2 && !selectedProduct) performSearch(searchTerm);
                }}
                onBlur={() => {
                  setTimeout(() => setSuggestions([]), 200);
                }}
                className="w-full p-2.5 border border-gray-200 rounded-lg outline-none text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all bg-white shadow-sm"
                placeholder="Digita nome o codice dell'articolo..."
              />

              {/* SUGGESTIONS DESKTOP */}
              {suggestions.length > 0 && (
                <div className="absolute w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-2xl z-[110] max-h-[200px] overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
                  {suggestions.map((p) => (
                    <div key={p.cod_art} onClick={() => handleSelectProduct(p)} className="p-2.5 hover:bg-blue-50 cursor-pointer group transition-colors">
                      <div className="mb-1"><p className="text-sm font-bold text-gray-800 leading-tight group-hover:text-blue-900">{p.des_art}</p></div>
                      <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
                        <span className="shrink-0 bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded border border-gray-200">{p.cod_art}</span>
                        <span className="text-gray-300">•</span>
                        <span className="uppercase">{p.linea}</span>
                        <span className="text-gray-300">/</span>
                        <span className="font-medium text-gray-500">{p.famiglia}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* BOX PRODOTTO SELEZIONATO DESKTOP */}
          {selectedProduct && (
            <div className={`p-3 border rounded-xl shadow-sm space-y-2.5 transition-colors ${isBlocked ? "bg-red-50 border-red-200" : "bg-white border-gray-100"}`}>
              <div className="w-full">
                <div className="mb-1.5"><p className="text-sm font-bold leading-tight text-gray-800 break-words">{selectedProduct.des_art}</p></div>
                <div className="text-[10px] text-gray-400 flex items-center gap-1.5 mb-1.5">
                  <span className={`shrink-0 font-mono px-1.5 py-0.5 rounded border ${isBlocked ? "bg-red-100 text-red-700 border-red-200" : "bg-gray-100 text-gray-600 border-gray-200"}`}>{selectedProduct.cod_art}</span>
                  <span className="text-gray-300">•</span>
                  <span className="uppercase">{selectedProduct.linea}</span>
                  <span className="text-gray-300">/</span>
                  <span className="font-medium text-gray-500">{selectedProduct.famiglia}</span>
                </div>

                {selectedProduct.stato && (<div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold border ${isBlocked ? "bg-red-100 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>{isBlocked ? "⛔" : "⚠️"} {selectedProduct.stato}</div>)}
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-2 shrink-0">
                  <input type="number" min="1" value={qty} onChange={handleQtyChange} className="w-14 p-1 border border-gray-200 rounded-md text-center font-black text-gray-800 focus:border-blue-500 outline-none bg-white text-sm" />
                  <button onClick={addToCart} disabled={isBlocked || qty === '' || qty === 0} className="bg-black text-white p-2 rounded-lg font-bold hover:bg-gray-800 disabled:bg-gray-200 disabled:text-gray-400 transition-all shrink-0">+</button>
                  <button onClick={() => { setSelectedProduct(null); setSearchTerm(""); setQty(1); setError(""); }} className="p-2 border border-gray-200 text-gray-400 hover:text-red-500 hover:bg-red-50 hover:border-red-200 rounded-lg transition-all shrink-0 bg-white font-bold">✕</button>
                </div>
                <div className="text-[10px] text-gray-500 whitespace-normal">
                  Venduto in {selectedProduct.des_um} ({selectedProduct.pezzi_conf} {selectedProduct.des_tipo_um})
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto pr-2 space-y-2 custom-scrollbar -mr-2">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-[9px] font-black text-gray-400 uppercase tracking-widest">CARRELLO</label>
            <span className="text-[9px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full font-bold">{cart.length} Articoli</span>
          </div>
          {cart.length === 0 ? (
            <div className="h-60 flex flex-col items-center justify-center border-2 border-dashed border-gray-100 rounded-[20px] text-gray-300 text-sm italic text-center px-8 gap-2"><span className="opacity-50 text-2xl">🛒</span><span>Nessun articolo</span></div>
          ) : (
            <div className="space-y-2.5 pb-2">
              {cart.map((item) => {
                const isDraft = !item.cod_art;
                return (
                  <div key={item.id} className={`relative flex items-start justify-between p-3 border rounded-xl shadow-sm transition-all ${isDraft ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-100 hover:border-blue-200'}`}>
                    <div className="flex-1 min-w-0 pr-3">
                      <div className="mb-1.5"><p className={`text-sm font-bold leading-tight ${isDraft ? 'text-amber-900 italic' : 'text-gray-800'}`}>{item.des_art || item.descrizione_libera}</p></div>
                      {!isDraft && (
                        <div className="mb-1.5 text-[10px] text-gray-400 flex items-center gap-1.5">
                          <span className="shrink-0 bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded border border-gray-200">{item.cod_art}</span>
                          <span className="text-gray-300">•</span>
                          <span className="uppercase">{item.linea}</span>
                          <span className="text-gray-300">/</span>
                          <span className="font-medium text-gray-500">{item.famiglia}</span>
                        </div>
                      )}

                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-md text-[11px] font-bold">Qta: {item.qta_ordinata}</span>
                        {!isDraft && (
                          <span className="text-[10px] text-gray-400">Venduto in {item.des_um} ({item.pezzi_conf} {item.des_tipo_um})</span>
                        )}
                      </div>
                    </div>
                    <button onClick={() => removeFromCart(item.id)} className="shrink-0 p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">✕</button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* FOOTER DESKTOP */}
        <div className="pt-2 border-t border-gray-100 mt-2 flex items-center gap-3">
          {error && (<div className="p-2 bg-red-50 text-red-600 rounded-lg text-[10px] font-bold border border-red-100 flex-1">⚠️ {error}</div>)}

          <button
            onClick={handleSendFullOrder}
            disabled={cart.length === 0}
            className="w-full h-10 bg-black text-white rounded-lg font-bold text-sm shadow-sm hover:bg-gray-800 disabled:bg-gray-100 disabled:text-gray-400 transition-all flex justify-center items-center gap-2"
          >
            CONFERMA E INVIA
          </button>
        </div>
      </div>
    </div>
  );
}