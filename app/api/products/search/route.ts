import { NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get('q')?.trim();
  const cod_cli = searchParams.get('cod_cli');

  if (!q || q.length < 2 || !cod_cli) return NextResponse.json([]);

  try {
    const query = `
      SELECT 
        cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato, 
        linea, famiglia
      FROM anaart 
      WHERE (des_art LIKE ? OR cod_art LIKE ?)
      AND (
        NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ?) 
        OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = ? AND cod_art = anaart.cod_art)
      )
      LIMIT 20
    `;
    const params = [`%${q}%`, `${q}%`, cod_cli, cod_cli];

    const [rows] = await db.execute(query, params);

    return NextResponse.json(rows);
  } catch (error: any) {
    return NextResponse.json({ error: 'Errore ricerca prodotti' }, { status: 500 });
  }
}