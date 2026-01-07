"use client";

import { useState, useEffect } from "react";
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
  const [activeTab, setActiveTab] = useState<"create" | "history">("create");
  const [refreshKey, setRefreshKey] = useState(0);

  const [sidebarWidth, setSidebarWidth] = useState<number | null>(null);

  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    setSidebarWidth(Math.floor(window.innerWidth / 2));
  }, []);

  const startResizing = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    const stop = () => setIsResizing(false);

    const resize = (e: MouseEvent) => {
      if (!isResizing) return;

      const newWidth = window.innerWidth - e.clientX;
      if (newWidth > 300 && newWidth < window.innerWidth - 300) {
        setSidebarWidth(newWidth);
      }
    };

    if (isResizing) {
      window.addEventListener("mousemove", resize);
      window.addEventListener("mouseup", stop);
    }

    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stop);
    };
  }, [isResizing]);

  const handleOrderSuccess = () => {
    setRefreshKey((k) => k + 1);
    setActiveTab("history");
  };

  return (
    <main className="h-screen bg-gray-100 flex flex-col overflow-hidden font-sans">
      <ClientSelector
        onClientChange={(c) => {
          setSelectedClient(c);
          setActiveTab("create");
        }}
      />

      <div className="flex-1 p-4 flex overflow-hidden">
        {/* CHAT */}
        <div className="flex-1 bg-white rounded-[32px] shadow-sm border overflow-hidden">
          <OrderChat selectedClient={selectedClient} />
        </div>

        {/* RESIZE HANDLE */}
        <div
          onMouseDown={startResizing}
          className={`w-4 cursor-col-resize flex items-center justify-center ${
            isResizing ? "bg-blue-100" : ""
          }`}
        >
          <div className="w-1 h-8 bg-gray-300 rounded-full" />
        </div>

        {/* SIDEBAR */}
        <div
          style={{ width: sidebarWidth ?? 450 }}
          className="flex flex-col gap-4 min-w-[300px]"
        >
          {/* TAB */}
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("create")}
              disabled={!selectedClient}
              className={`flex-1 p-3 rounded-xl font-bold transition-colors ${
                activeTab === "create"
                  ? "bg-black text-white"
                  : "bg-white border"
              }`}
            >
              Crea Ordine
            </button>

            <button
              onClick={() => setActiveTab("history")}
              className={`flex-1 p-3 rounded-xl font-bold transition-colors ${
                activeTab === "history"
                  ? "bg-black text-white"
                  : "bg-white border"
              }`}
            >
              Storico
            </button>
          </div>

          {/* CONTENT */}
          {activeTab === "create" ? (
            selectedClient ? (
              <div className="bg-white p-4 rounded-[32px] shadow-sm border flex-1 overflow-hidden">
                <OrderCanvas
                  currentClient={selectedClient}
                  onOrderSuccess={handleOrderSuccess}
                />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400 italic">
                Seleziona un cliente
              </div>
            )
          ) : (
            <div className="bg-white p-4 rounded-[32px] shadow-sm border flex-1 overflow-hidden">
              {selectedClient ? (
                <OrderList
                  cod_cli={String(selectedClient.cod_cli)}
                  key={`${selectedClient.cod_cli}-${refreshKey}`}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400 italic">
                  Seleziona un cliente
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}