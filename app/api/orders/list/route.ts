import { NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const cod_cli = searchParams.get('cod_cli');

  if (!cod_cli) return NextResponse.json([]);

  try {
    const query = `
      SELECT 
        o.id, o.cod_art, o.data_ord, o.qta_ordinata, 
        a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um, a.linea, a.famiglia 
      FROM ordclidet o
      LEFT JOIN anaart a ON o.cod_art = a.cod_art
      WHERE o.cod_cli = ?
      ORDER BY o.data_ord DESC, o.id DESC
      LIMIT 50
    `;

    const [rows] = await db.execute(query, [cod_cli]);
    return NextResponse.json(rows);
  } catch (error: any) {
    return NextResponse.json({ error: 'Errore caricamento storico ordini' }, { status: 500 });
  }
}