"use client";
import { useState, useEffect } from 'react';

interface Order {
  id: number;
  cod_art: string;
  des_art: string;
  data_ord: string;
  qta_ordinata: number;
  des_um: string;
  linea?: string;
  famiglia?: string;
  pezzi_conf?: number;
  des_tipo_um?: string;
}

export default function OrderList({ cod_cli }: { cod_cli: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cod_cli) return;

    setLoading(true);
    fetch(`/api/orders/list?cod_cli=${cod_cli}`)
      .then(res => res.json())
      .then(data => {
        setOrders(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [cod_cli]);

  if (loading) return (
    <div className="h-full flex items-center justify-center">
        <p className="text-xs text-gray-400 animate-pulse font-medium">Caricamento storico...</p>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto pr-2 space-y-3 custom-scrollbar">
      {orders.length === 0 ? (
        <div className="h-32 flex flex-col items-center justify-center border-2 border-dashed border-gray-100 rounded-[24px] text-gray-300 text-sm italic text-center px-6">
          <span>Nessun ordine recente</span>
        </div>
      ) : (
        orders.map((order) => (
          <div key={order.id} className="group relative p-4 bg-white border border-gray-100 rounded-2xl shadow-sm hover:border-blue-200 hover:shadow-md transition-all">
            
            {/* DATA */}
            <div className="absolute top-4 right-4 text-[10px] font-bold text-gray-300 group-hover:text-blue-400 transition-colors bg-gray-50 px-2 py-1 rounded-full group-hover:bg-blue-50">
              {new Date(order.data_ord).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: '2-digit' })}
            </div>

            <div className="pr-16"> 
              {/* CODICE E NOME */}
              <div className="flex items-start gap-2 mb-1">
                <span className="shrink-0 bg-gray-100 text-gray-600 text-[9px] font-mono px-1.5 py-0.5 rounded border border-gray-200 mt-0.5">
                  {order.cod_art}
                </span>
                <p className="text-sm font-bold text-gray-800 leading-tight">
                  {order.des_art}
                </p>
              </div>

              {/* LINEA / FAMIGLIA */}
              {(order.linea || order.famiglia) && (
                <div className="mb-2 text-[10px] text-gray-400 flex items-center gap-1.5 pl-0.5">
                   <span className="uppercase tracking-tight">{order.linea}</span>
                   <span className="text-gray-300">/</span>
                   <span className="font-medium text-gray-500">{order.famiglia}</span>
                </div>
              )}

              {/* DETTAGLI QUANTITA */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-md text-[11px] font-bold">
                  Qta: {order.qta_ordinata}
                </span>
                <span className="text-[10px] text-gray-400">
                   Venduto in {order.des_um} 
                   {order.pezzi_conf ? ` (${order.pezzi_conf} ${order.des_tipo_um || ''})` : ''}
                </span>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}