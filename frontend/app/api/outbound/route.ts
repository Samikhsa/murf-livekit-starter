import { NextResponse } from 'next/server';
import { AccessToken, RoomServiceClient, type AccessTokenOptions, type VideoGrant } from 'livekit-server-sdk';
import { RoomConfiguration } from '@livekit/protocol';

const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const AGENT_NAME = process.env.AGENT_NAME ?? 'my-agent';

export const revalidate = 0;

export async function POST(req: Request) {
  try {
    if (!LIVEKIT_URL || !API_KEY || !API_SECRET) {
      return NextResponse.json({ error: 'LiveKit credentials missing' }, { status: 500 });
    }

    const body = await req.json().catch(() => ({}));
    const customerName = body.customer_name || 'Ramesh Kumar';
    const phoneNumber = body.phone_number || '+91 98765 43210';
    const restockItem = body.restock_item || 'Basmati Rice 5kg & Wheat Flour 10kg';
    const outcome = body.simulate_outcome || 'CONNECTED';

    const userId = `user_${phoneNumber.replace(/\D/g, '') || '9876543210'}`;
    const roomName = `outbound_${Math.floor(Math.random() * 10_000)}`;

    const metadata = JSON.stringify({
      call_type: 'outbound',
      customer_name: customerName,
      phone_number: phoneNumber,
      restock_item: restockItem,
      user_id: userId,
      simulate_outcome: outcome,
    });

    const roomConfig = RoomConfiguration.fromJson(
      { agents: [{ agent_name: AGENT_NAME }] },
      { ignoreUnknownFields: true }
    );

    // Create participant token for joining the outbound room
    const at = new AccessToken(API_KEY, API_SECRET, {
      identity: userId,
      name: customerName,
      ttl: '15m',
      metadata,
    });

    const grant: VideoGrant = {
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canPublishData: true,
      canSubscribe: true,
    };
    at.addGrant(grant);
    at.roomConfig = roomConfig;

    const participantToken = await at.toJwt();

    // Optionally set room metadata on server
    try {
      const httpUrl = LIVEKIT_URL.replace('wss://', 'https://').replace('ws://', 'http://');
      const svc = new RoomServiceClient(httpUrl, API_KEY, API_SECRET);
      await svc.createRoom({ name: roomName, metadata });
    } catch {
      // Ignore if room auto-creates on join
    }

    return NextResponse.json({
      serverUrl: LIVEKIT_URL,
      roomName,
      participantName: customerName,
      participantToken,
      call_metadata: {
        call_type: 'outbound',
        customer_name: customerName,
        phone_number: phoneNumber,
        restock_item: restockItem,
        user_id: userId,
        simulate_outcome: outcome,
      },
      mandatory_opening: {
        who: `Hello ${customerName}! This is ShopMitra calling from ABC Local Store...`,
        why: `...I'm calling to check if you would like to restock your monthly order of ${restockItem}.`,
        opt_out: `If you prefer not to receive these restock call reminders, just say opt out or let me know anytime.`,
      },
    });
  } catch (error: any) {
    console.error('Outbound API Error:', error);
    return NextResponse.json({ error: error.message || 'Internal error' }, { status: 500 });
  }
}
