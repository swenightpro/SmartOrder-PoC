"use client";

import { useState, useRef, useEffect } from 'react';
import OrderChat from "@/components/OrderChat";
import OrderCanvas from "@/components/OrderCanvas";
import ClientSelector from "@/components/ClientSelector";
import OrderList from "@/components/OrderList";

interface Client {
  cod_cli: number;
  rag_soc: string;
}

export default function Home() {
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isBuilderOpen, setIsBuilderOpen] = useState(false); 
  const [refreshKey, setRefreshKey] = useState(0);

  const [sidebarWidth, setSidebarWidth] = useState(450); 
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const startResizing = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    const stopResizing = () => setIsResizing(false);
    
    const resize = (e: MouseEvent) => {
      if (isResizing) {
        const newWidth = window.innerWidth - e.clientX;
        if (newWidth > 300 && newWidth < 800) {
          setSidebarWidth(newWidth);
        }
      }
    };

    if (isResizing) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
    }

    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [isResizing]);

  const handleOrderSuccess = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <main className={`h-screen bg-gray-100 flex flex-col overflow-hidden font-sans ${isResizing ? 'cursor-col-resize select-none' : ''}`}>
      
      {/* HEADER */}
      <div className="shrink-0 z-20 relative">
        <ClientSelector onClientChange={(c) => {
          setSelectedClient(c);
          setIsBuilderOpen(false);
        }} />
      </div>
      
      <div className="flex-1 p-4 flex gap-0 justify-center overflow-hidden w-full relative">
        
        {/* COLONNA SINISTRA */}
        <div className="flex-1 h-full shadow-lg rounded-l-[32px] rounded-r-md overflow-hidden bg-white z-10">
          <OrderChat selectedClient={selectedClient} />
        </div>

        {/* MANIGLIA DI RIDIMENSIONAMENTO (Barra grigia centrale) */}
        <div 
          onMouseDown={startResizing}
          className="w-4 cursor-col-resize hover:bg-blue-100 flex items-center justify-center transition-colors group z-20"
        >
          <div className="w-1 h-8 bg-gray-300 rounded-full group-hover:bg-blue-400 transition-colors" />
        </div>

        {/* COLONNA DESTRA */}
        <div 
          style={{ width: sidebarWidth }} 
          className="h-full flex flex-col gap-4 shrink-0 transition-none" 
        >
          
          {isBuilderOpen ? (
            // VISTA EDITOR (Carrello)
            <OrderCanvas 
              currentClient={selectedClient} 
              onClose={() => setIsBuilderOpen(false)} 
              onOrderSuccess={handleOrderSuccess}
            />
          ) : (
            // VISTA MENU + STORICO
            <>
              <button 
                onClick={() => setIsBuilderOpen(true)}
                disabled={!selectedClient}
                className="shrink-0 w-full bg-black text-white p-4 rounded-[24px] font-bold hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-xl flex items-center justify-center gap-3"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                Nuovo Ordine
              </button>

              <div className="bg-white p-4 rounded-[32px] shadow-sm border border-gray-200 flex-1 overflow-hidden flex flex-col rounded-l-md">
                <h3 className="shrink-0 font-bold text-gray-800 mb-3 flex items-center gap-2 text-md px-2 pt-2">
                  <span className="bg-blue-100 text-blue-600 p-1 rounded-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  </span>
                  Storico Ordini
                </h3>
                
                <div className="flex-1 overflow-hidden">
                  {selectedClient ? (
                    <OrderList 
                      cod_cli={String(selectedClient.cod_cli)} 
                      key={`${selectedClient.cod_cli}-${refreshKey}`} 
                    />
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-400 gap-2">
                      <div className="text-3xl opacity-20">📂</div>
                      <p className="text-xs font-medium italic">Seleziona un cliente</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}