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
  } catch (error: any) {
    console.error("Errore GET /api/cart:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { action, cod_cli, cod_art, qta, id, descrizione_libera } = body;

    if (action === 'add') {
      const data_ord = new Date().toISOString().split('T')[0];
      await db.execute(
        `INSERT INTO preordclidet (cod_cli, cod_art, rif, data_ord, qta_ordinata) 
         VALUES (?, ?, ?, ?, ?)`,
        [parseInt(cod_cli), cod_art || null, descrizione_libera || null, data_ord, qta]
      );
    } 
    else if (action === 'remove') {
      await db.execute('DELETE FROM preordclidet WHERE id = ?', [id]);
    }

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error("Errore POST /api/cart:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}