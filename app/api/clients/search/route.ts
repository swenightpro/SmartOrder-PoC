import { NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get('q')?.trim();

  if (!q || q.length === 0) return NextResponse.json([]);

  try {
  const [rows] = await db.execute(
    `SELECT cod_cli, rag_soc 
     FROM anacli 
     WHERE rag_soc ILIKE ? OR CAST(cod_cli AS TEXT) = ? 
     LIMIT 10`,
    [`%${q}%`, q]
  );
  
  return NextResponse.json(rows);
  } catch (error: any) {
    console.error("Errore ricerca clienti:", error); // Aggiungi questo per vedere l'errore nei log
    return NextResponse.json({ error: 'Errore ricerca clienti' }, { status: 500 });
  }
}
