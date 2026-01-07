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
    <div className="h-full bg-white flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">

      {/* BODY */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden">

        {/* BOX AGGIUNTA ARTICOLO */}
        <div className="space-y-4 mb-4 shrink-0 relative z-20">
          {!selectedProduct && (
            <div className="relative">
              <label className="block text-[10px] font-black text-gray-400 uppercase mb-2 tracking-widest">
                AGGIUNGI ARTICOLO
              </label>

              <input
                type="text"
                autoComplete="off"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setError("");
                }}
                className="w-full p-3.5 border border-gray-200 rounded-xl outline-none text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all bg-white shadow-sm"
                placeholder="Digita nome o codice dell'articolo (es: GR059)..."
              />

              {suggestions.length > 0 && (
                <div className="absolute w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl z-[110] max-h-[250px] overflow-y-auto divide-y divide-gray-50 custom-scrollbar">
                  {suggestions.map((p) => (
                    <div
                      key={p.cod_art}
                      onClick={() => handleSelectProduct(p)}
                      className="p-3 hover:bg-blue-50 cursor-pointer group transition-colors"
                    >
                      {/* NOME PRODOTTO */}
                      <div className="mb-1.5">
                        <p className="text-sm font-bold text-gray-800 leading-tight group-hover:text-blue-900">
                          {p.des_art}
                        </p>
                      </div>

                      {/* CODICE / LINEA / FAMIGLIA */}
                      <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
                        <span className="shrink-0 bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded border border-gray-200 group-hover:bg-blue-100 group-hover:text-blue-700 group-hover:border-blue-200 transition-colors">
                          {p.cod_art}
                        </span>
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

          {/* DETTAGLIO PRODOTTO SELEZIONATO */}
          {selectedProduct && (
            <div className={`p-4 border rounded-2xl shadow-sm space-y-3 transition-colors ${
              isBlocked
                ? "bg-red-50 border-red-200"
                : "bg-white border-gray-100"
            }`}>

              {/* INFO PRODOTTO */}
              <div className="w-full">
                {/* NOME PRODOTTO */}
                <div className="mb-2">
                  <p className="text-sm font-bold leading-tight text-gray-800 break-words">
                    {selectedProduct.des_art}
                  </p>
                </div>

                {/* CODICE / LINEA / FAMIGLIA */}
                <div className="text-[10px] text-gray-400 flex items-center gap-1.5 mb-2">
                  <span
                    className={`shrink-0 font-mono px-1.5 py-0.5 rounded border ${
                      isBlocked
                        ? "bg-red-100 text-red-700 border-red-200"
                        : "bg-gray-100 text-gray-600 border-gray-200"
                    }`}
                  >
                    {selectedProduct.cod_art}
                  </span>
                  <span className="text-gray-300">•</span>
                  <span className="uppercase">{selectedProduct.linea}</span>
                  <span className="text-gray-300">/</span>
                  <span className="font-medium text-gray-500">{selectedProduct.famiglia}</span>
                </div>

                {/* --- VISUALIZZAZIONE STATO --- */}
                {selectedProduct.stato && (
                  <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold border ${
                    isBlocked 
                      ? "bg-red-100 text-red-700 border-red-200" 
                      : "bg-amber-50 text-amber-700 border-amber-200"
                  }`}>
                    {isBlocked ? "⛔" : "⚠️"} {selectedProduct.stato}
                  </div>
                )}
              </div>

              {/* QUANTITÀ E AZIONI */}
              <div className="flex items-center gap-2 flex-wrap">
                
                <div className="flex items-center gap-2 shrink-0">
                  {/* Quantità */}
                  <div className="flex items-center gap-2 bg-gray-50 px-3 py-2 rounded-lg">
                    <span className="text-[10px] font-black text-gray-400 uppercase whitespace-nowrap">
                      Quantità
                    </span>
                    <input
                      type="number"
                      min={1}
                      value={qty}
                      onChange={(e) => setQty(Number(e.target.value))}
                      className="w-16 p-1.5 border border-gray-200 rounded-md text-center font-black text-gray-800 focus:border-blue-500 outline-none bg-white"
                    />
                  </div>
                  <button
                    onClick={addToCart}
                    disabled={isBlocked}
                    className="bg-black text-white p-2.5 rounded-xl font-bold hover:bg-gray-800 disabled:bg-gray-200 disabled:text-gray-400 transition-all shrink-0"
                  >
                    +
                  </button>
                  <button
                    onClick={() => {
                      setSelectedProduct(null);
                      setSearchTerm("");
                      setQty(1);
                      setError("");
                    }}
                    className="p-2.5 border border-gray-200 text-gray-400 hover:text-red-500 hover:bg-red-50 hover:border-red-200 rounded-xl transition-all shrink-0 bg-white font-bold"
                  >
                    ✕
                  </button>
                </div>

                <div className="text-[10px] text-gray-500 whitespace-normal">
                  Venduto in {selectedProduct.des_um} ({selectedProduct.pezzi_conf}{" "}
                  {selectedProduct.des_tipo_um})
                </div>
              </div>
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
            <div className="h-80 flex flex-col items-center justify-center border-2 border-dashed border-gray-100 rounded-[24px] text-gray-300 text-sm italic text-center px-10 gap-2">
              <span className="opacity-50 text-2xl">🛒</span>
              <span>Nessun articolo</span>
            </div>
          ) : (
            <div className="space-y-3 pb-2">
              {cart.map((item) => {
                const isDraft = !item.cod_art;

                return (
                  <div key={item.id} className={`relative flex items-start justify-between p-4 border rounded-2xl shadow-sm transition-all animate-in slide-in-from-bottom-2 ${isDraft ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-100 hover:border-blue-200'
                    }`}>

                    <div className="flex-1 min-w-0 pr-4">
                      {/* NOME PRODOTTO */}
                      <div className="mb-2">
                        <p className={`text-sm font-bold leading-tight ${isDraft ? 'text-amber-900 italic' : 'text-gray-800'}`}>
                          {isDraft ? item.descrizione_libera : item.des_art}
                        </p>
                      </div>

                      {/* CODICE / LINEA / FAMIGLIA */}
                      {!isDraft && (
                        <div className="mb-2 text-[10px] text-gray-400 flex items-center gap-1.5">
                          <span className="shrink-0 bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded border border-gray-200">
                            {item.cod_art}
                          </span>
                          <span className="text-gray-300">•</span>
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