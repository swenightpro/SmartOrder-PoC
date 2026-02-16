import { NextResponse } from 'next/server';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const { message, clientId, history } = await request.json();

    const response = await fetch(`${PYTHON_SERVICE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        client_id: clientId,
        history: history ?? [],
      }),
    });

    if (!response.ok) {
        return NextResponse.json(
            { 
                success: false, 
                error: `Errore dal servizio Python: ${response.status} ${response.statusText}` 
            },
            { status: response.status >= 500 ? 502 : response.status }
        );
    }

    const data = await response.json();

    console.log('=== RISPOSTA COMPLETA ===');
    console.log(data);
    console.log('========================');

    return NextResponse.json({
      success: true,
      response: data.message || data.response,
      product_codes: data.product_codes || [],
      order_confirmed: data.order_confirmed ?? false,
    });
  } catch (error: unknown) {
    console.error('Chat API error:', error);

    const err = error instanceof Error 
      ? error 
      : { message: String(error), code: undefined };
    const errorWithCode = error as { code?: string; message?: string };
    
    const isConnectionError = 
      errorWithCode.code === 'ECONNREFUSED' || 
      errorWithCode.code === 'ENOTFOUND' ||
      err.message?.includes('fetch failed') ||
      err.message?.includes('ECONNREFUSED');

    if (isConnectionError) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'Servizio chat non disponibile. Verifica che il servizio Python sia attivo sulla porta 8000.' 
        },
        { status: 503 }
      );
    }

    return NextResponse.json(
      { 
        success: false, 
        error: err.message || 'Errore nella comunicazione con il servizio chat' 
      },
      { status: 500 }
    );
  }
}
