import { NextResponse } from 'next/server';

import { API_ORIGIN } from '@/lib/server/auth-config';
import { readToken } from '@/lib/server/session';

/**
 * Server-side boundary between the browser and the API.
 *
 * The credential is attached here, from an httpOnly cookie, so no page script
 * ever holds it. The API origin stays on the server too, which is why the
 * browser needs no build-time knowledge of where the API listens.
 */

const FORWARDED_REQUEST_HEADERS = ['content-type', 'accept'];
const FORWARDED_RESPONSE_HEADERS = ['content-type', 'www-authenticate', 'retry-after'];

async function forward(request: Request, path: string[]): Promise<NextResponse> {
  const token = await readToken();
  if (!token) {
    return NextResponse.json({ detail: 'authentication required' }, { status: 401 });
  }

  const incoming = new URL(request.url);
  const target = `${API_ORIGIN}/${path.join('/')}${incoming.search}`;

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.text() : undefined,
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json({ detail: 'the API is unreachable' }, { status: 502 });
  }

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) {
      responseHeaders.set(name, value);
    }
  }
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  }) as NextResponse;
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, context: Context): Promise<NextResponse> {
  return forward(request, (await context.params).path);
}

export async function POST(request: Request, context: Context): Promise<NextResponse> {
  return forward(request, (await context.params).path);
}

export async function PUT(request: Request, context: Context): Promise<NextResponse> {
  return forward(request, (await context.params).path);
}

export async function PATCH(request: Request, context: Context): Promise<NextResponse> {
  return forward(request, (await context.params).path);
}

export async function DELETE(request: Request, context: Context): Promise<NextResponse> {
  return forward(request, (await context.params).path);
}
