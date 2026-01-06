import { NextResponse } from 'next/server';
import db from '@/lib/db';

// Costanti di configurazione business
const BLOCKING_STATUSES = ["ARTICOLO SOSPESO", "SU AUTORIZZAZIONE", "DISPONIBILE DAL"];

export async function POST(request: Request) {
  try {
    const { cod_cli, items } = await request.json();
    const data_ord = new Date().toISOString().split('T')[0];

    // 1. FASE DI VALIDAZIONE
    // Controlliamo ogni riga prima di iniziare a scrivere nel database reale
    for (const item of items) {
      
      // A. Blocco Bozze (Righe Gialle)
      if (!item.cod_art) {
        return NextResponse.json(
          { error: `Errore: la riga "${item.descrizione_libera || 'sconosciuta'}" è incompleta.` },
          { status: 400 }
        );
      }

      // B. Controllo Stato Articolo
      const [artInfo]: any = await db.execute(
        'SELECT stato FROM anaart WHERE cod_art = ?', 
        [item.cod_art]
      );
      
      const stato = artInfo[0]?.stato?.toUpperCase() || '';
      if (BLOCKING_STATUSES.some(s => stato.includes(s))) {
         return NextResponse.json(
           { error: `Articolo ${item.cod_art} non ordinabile (${stato})` }, 
           { status: 403 }
         );
      }

      // C. Controllo Assortimento Cliente
      const [assortmentCheck]: any = await db.execute(
        `SELECT 1 FROM DUAL WHERE 
         NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ?) 
         OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ? AND cod_art = ?)`,
        [cod_cli, cod_cli, item.cod_art]
      );

      if (assortmentCheck.length === 0) {
        return NextResponse.json(
          { error: `Articolo ${item.cod_art} non presente nell'assortimento` }, 
          { status: 403 }
        );
      }
    }

    // 2. FASE DI SCRITTURA (Se siamo qui, tutti i controlli sono passati)
    for (const item of items) {
      await db.execute(
        'INSERT INTO ordclidet (cod_cli, cod_art, data_ord, qta_ordinata) VALUES (?, ?, ?, ?)',
        [cod_cli, item.cod_art, data_ord, item.qty]
      );
    }

    // 3. PULIZIA CARRELLO
    await db.execute('DELETE FROM preordclidet WHERE cod_cli = ?', [cod_cli]);

    return NextResponse.json({ success: true });
    
  } catch (error: any) {
    console.error("Order creation failed:", error);
    return NextResponse.json({ error: 'Errore interno durante la creazione ordine' }, { status: 500 });
  }
}