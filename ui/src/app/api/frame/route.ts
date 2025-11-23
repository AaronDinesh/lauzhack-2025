import { NextResponse } from 'next/server';
import { Buffer } from 'buffer';

// A tiny in-memory buffer; CameraView will post frames here.
let latestFrame: { data: Uint8Array; contentType: string } | null = null;

export function POST(req: Request) {
  return req
    .arrayBuffer()
    .then((buf) => {
      const contentType = req.headers.get('content-type') || 'image/jpeg';
      latestFrame = { data: new Uint8Array(buf), contentType };
      return NextResponse.json({ status: 'ok' });
    })
    .catch((err) => {
      console.error('[frame POST] failed:', err);
      return NextResponse.json({ status: 'error', error: 'failed to store frame' }, { status: 500 });
    });
}

export function GET() {
  if (!latestFrame) {
    return NextResponse.json({ status: 'error', error: 'no frame available' }, { status: 404 });
  }
  // Wrap in Buffer to satisfy BodyInit typing in Next.js build.
  return new NextResponse(Buffer.from(latestFrame.data), {
    status: 200,
    headers: {
      'Content-Type': latestFrame.contentType,
      'Cache-Control': 'no-store',
    },
  });
}
