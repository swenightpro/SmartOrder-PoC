"use client";

import { useState, useEffect, useCallback } from "react";
import OrderChat, { Message } from "@/components/OrderChat"; 
import OrderCanvas, { CartItem } from "@/components/OrderCanvas";
import ClientSelector from "@/components/ClientSelector";
import OrderList from "@/components/OrderList";

export interface Client {
  cod_cli: number;
  rag_soc: string;
}

export default function Home() {
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [activeTab, setActiveTab] = useState<"create" | "history">("create");
  const [refreshKey, setRefreshKey] = useState(0);
  const [showClientSelector, setShowClientSelector] = useState(false);
  const [chatMessages, setChatMessages] = useState<Message[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);

  const refreshCart = useCallback(async () => {
    if (!selectedClient?.cod_cli) {
      setCart([]);
      return;
    }
    try {
      const res = await fetch(`/api/cart?cod_cli=${selectedClient.cod_cli}`);
      if (res.ok) {
        const data = await res.json();
        setCart(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error("Errore fetch carrello", e);
    }
  }, [selectedClient]);

  useEffect(() => {
    if (selectedClient) {
      setChatMessages([{
        id: 'welcome',
        role: 'assistant',
        content: `Ciao ${selectedClient.rag_soc}! Cosa ti serve oggi?`
      }]);
      refreshCart();
    } else {
      setChatMessages([]);
      setCart([]);
    }
  }, [selectedClient, refreshCart]);

  useEffect(() => {
    if (!selectedClient) {
      setShowClientSelector(true);
    }
  }, [selectedClient]);

  const handleOrderSuccess = () => {
    setRefreshKey((k) => k + 1);
    setActiveTab("history");
    refreshCart();
  };

  const handleClientChange = (c: Client | null) => {
    setSelectedClient(c);
    setActiveTab("create");
    if (c) setShowClientSelector(false);
  };

  return (
    <main className="h-screen bg-gray-100 flex flex-col overflow-hidden font-sans">
      {/* HEADER MOBILE */}
      <div className="md:hidden bg-white border-b border-gray-200 shrink-0 relative">
        <div className="flex items-center gap-2 p-2">

          {/* BOTTONE SELEZIONE CLIENTE */}
          <button
            onClick={() => setShowClientSelector(true)}
            className={`shrink-0 px-3 h-8 flex items-center rounded-lg text-sm font-bold transition-all border max-w-[140px] truncate text-left ${selectedClient
                ? "bg-green-50 text-green-700 border-green-200"
                : "bg-gray-100 text-gray-600 border-gray-200"
              }`}
          >
            {selectedClient ? selectedClient.rag_soc : "Seleziona Cliente"}
          </button>

          {selectedClient && (
            <div className="flex gap-1 flex-1 min-w-0">
              {/* BOTTONE TAB CREA */}
              <button
                onClick={() => setActiveTab("create")}
                className={`flex-1 px-3 h-8 rounded-lg text-sm font-bold transition-colors ${activeTab === "create" ? "bg-black text-white" : "bg-gray-100 text-gray-600"
                  }`}
              >
                Crea
              </button>

              {/* BOTTONE TAB STORICO */}
              <button
                onClick={() => setActiveTab("history")}
                className={`flex-1 px-3 h-8 rounded-lg text-sm font-bold transition-colors ${activeTab === "history" ? "bg-black text-white" : "bg-gray-100 text-gray-600"
                  }`}
              >
                Storico
              </button>
            </div>
          )}
        </div>

        {/* CLIENT SELECTOR OVERLAY */}
        {showClientSelector && (
          <>
            <div 
              className="fixed inset-0 bg-black/20 z-[100] animate-in fade-in duration-200"
              onClick={() => setShowClientSelector(false)}
            />
            
            <div className="absolute top-0 left-0 right-0 z-[101] animate-in slide-in-from-top duration-200">
              <button
                onClick={() => setShowClientSelector(false)}
                className="absolute top-5 right-2 z-[102] p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
              
              <ClientSelector 
                currentClient={selectedClient}
                onClientChange={handleClientChange}
                isOverlay={true}
              />
            </div>
          </>
        )}
      </div>

      {/* DESKTOP HEADER */}
      <div className="hidden md:block">
        <ClientSelector
          currentClient={selectedClient}
          onClientChange={(c) => {
            setSelectedClient(c);
            setActiveTab("create");
          }}
        />
      </div>

      {/* LAYOUT DESKTOP */}
      <div className="hidden md:flex flex-1 p-3 overflow-hidden gap-3">
        {/* CHAT */}
        <div className="w-1/2 bg-white rounded-[24px] shadow-sm border overflow-hidden">
          <OrderChat
            selectedClient={selectedClient}
            messages={chatMessages}
            setMessages={setChatMessages}
          />
        </div>

        {/* SIDEBAR */}
        <div className="w-1/2 flex flex-col gap-3">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("create")}
              disabled={!selectedClient}
              className={`flex-1 p-2 rounded-lg text-sm font-bold transition-colors ${activeTab === "create" ? "bg-black text-white" : "bg-white border"
                }`}
            >
              Crea Ordine
            </button>
            <button
              onClick={() => setActiveTab("history")}
              disabled={!selectedClient}
              className={`flex-1 p-2 rounded-lg text-sm font-bold transition-colors ${activeTab === "history" ? "bg-black text-white" : "bg-white border"
                }`}
            >
              Storico
            </button>
          </div>

          {activeTab === "create" ? (
            selectedClient ? (
              <div className="bg-white p-3 rounded-[24px] shadow-sm border flex-1 overflow-hidden">
                {/* CANVAS */}
                <OrderCanvas
                  currentClient={selectedClient}
                  onOrderSuccess={handleOrderSuccess}
                  cart={cart}
                  refreshCart={refreshCart}
                />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400 italic text-sm">
                Seleziona un cliente
              </div>
            )
          ) : (
            <div className="bg-white p-3 rounded-[24px] shadow-sm border flex-1 overflow-hidden">
              {selectedClient ? (
                <OrderList
                  cod_cli={String(selectedClient.cod_cli)}
                  key={`${selectedClient.cod_cli}-${refreshKey}`}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400 italic text-sm">
                  Seleziona un cliente
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* LAYOUT MOBILE */}
      <div className="md:hidden flex-1 flex flex-col overflow-hidden">
        {activeTab === "create" ? (
          <>
            <div className="h-1/2 bg-white border-b overflow-hidden">
              {selectedClient ? (
                // CANVAS MOBILE
                <OrderCanvas
                  currentClient={selectedClient}
                  onOrderSuccess={handleOrderSuccess}
                  isMobile={true}
                  cart={cart}
                  refreshCart={refreshCart}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400 italic text-xs px-4 text-center">
                  Seleziona un cliente per iniziare
                </div>
              )}
            </div>

            <div className="flex-1 bg-white overflow-hidden">
              {/* CHAT MOBILE */}
              <OrderChat
                selectedClient={selectedClient}
                messages={chatMessages}
                setMessages={setChatMessages}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 bg-white overflow-hidden p-2">
            {selectedClient ? (
              <OrderList
                cod_cli={String(selectedClient.cod_cli)}
                key={`${selectedClient.cod_cli}-${refreshKey}`}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-400 italic text-xs px-4 text-center">
                Seleziona un cliente
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}