import { NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const cod_cli = searchParams.get('cod_cli');

  if (!cod_cli) return NextResponse.json([]);

  try {
    const query = `
      SELECT 
        p.id, p.cod_art, p.qta_ordinata, p.rif as descrizione_libera,
        a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um, a.linea, a.famiglia
      FROM preordclidet p 
      LEFT JOIN anaart a ON p.cod_art = a.cod_art 
      WHERE p.cod_cli = ?
    `;
    
    const [rows] = await db.execute(query, [parseInt(cod_cli)]);
    return NextResponse.json(rows);
  } catch (error: unknown) {
    console.error("Errore GET /api/cart:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Errore server' },
      { status: 500 }
    );
  }
}

/** Verifica se il prodotto è disponibile per il cliente (assortimento + stato). */
async function isProductAvailableForClient(cod_cli: number, cod_art: string): Promise<{ available: boolean; error?: string }> {
  const [rows] = await db.execute(
    `SELECT 1 FROM anaart a
     WHERE a.cod_art = ?
       AND (a.stato IS NULL OR a.stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))
       AND (
         NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ?)
         OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ? AND cod_art = a.cod_art)
       )
     LIMIT 1`,
    [cod_art, cod_cli, cod_cli]
  );
  const available = Array.isArray(rows) && rows.length > 0;
  return { available, error: available ? undefined : 'Prodotto non disponibile o non presente nell\'assortimento cliente' };
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { action, cod_cli, cod_art, qta, id, descrizione_libera } = body;

    if (action === 'add') {
      const cod_cli_num = parseInt(cod_cli);
      if (!cod_art) {
        return NextResponse.json({ success: false, error: 'Codice articolo mancante' }, { status: 400 });
      }
      const { available, error: availError } = await isProductAvailableForClient(cod_cli_num, cod_art);
      if (!available) {
        return NextResponse.json(
          { success: false, error: availError || 'Prodotto non disponibile per il cliente' },
          { status: 400 }
        );
      }
      const data_ord = new Date().toISOString().split('T')[0];
      await db.execute(
        `INSERT INTO preordclidet (cod_cli, cod_art, rif, data_ord, qta_ordinata) 
         VALUES (?, ?, ?, ?, ?)`,
        [cod_cli_num, cod_art, descrizione_libera || null, data_ord, qta ?? 1]
      );
    } 
    else if (action === 'remove') {
      if (!id) return NextResponse.json({ success: false, error: 'ID riga mancante' }, { status: 400 });
      await db.execute('DELETE FROM preordclidet WHERE id = ?', [id]);
    }
    else if (action === 'update_quantity') {
      const qtaNum = qta != null ? Number(qta) : null;
      if (id == null || qtaNum == null || qtaNum < 0.001) {
        return NextResponse.json({ success: false, error: 'id e qta obbligatori (qta > 0)' }, { status: 400 });
      }
      await db.execute('UPDATE preordclidet SET qta_ordinata = ? WHERE id = ?', [qtaNum, id]);
    }

    return NextResponse.json({ success: true });
  } catch (error: unknown) {
    console.error("Errore POST /api/cart:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Errore server' },
      { status: 500 }
    );
  }
}