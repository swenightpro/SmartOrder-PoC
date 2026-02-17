import { NextResponse } from 'next/server';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') ?? formData.get('audio');
    if (!file || !(file instanceof Blob)) {
      return NextResponse.json(
        { error: 'File audio mancante. Invia un campo "file" o "audio".' },
        { status: 400 }
      );
    }
    const forwardForm = new FormData();
    forwardForm.append('file', file, (file as File).name || 'audio.webm');
    const response = await fetch(`${PYTHON_SERVICE_URL}/transcribe`, {
      method: 'POST',
      body: forwardForm,
    });
    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json(
        { error: errText || 'Errore trascrizione' },
        { status: response.status >= 500 ? 502 : response.status }
      );
    }
    const data = await response.json();
    return NextResponse.json({ text: data.text ?? '' });
  } catch (error: unknown) {
    console.error('Transcribe API error:', error);
    const err = error instanceof Error ? error : { message: String(error) };
    const isConnectionError =
      (err as { code?: string }).code === 'ECONNREFUSED' ||
      (err as { code?: string }).code === 'ENOTFOUND' ||
      (err as Error).message?.includes('fetch failed');
    if (isConnectionError) {
      return NextResponse.json(
        { error: 'Servizio trascrizione non disponibile. Avvia il backend Python.' },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: (err as Error).message || 'Errore durante la trascrizione' },
      { status: 500 }
    );
  }
}
