import { NextRequest, NextResponse } from "next/server";
const ESCALATION_API_BASE =
  process.env.ESCALATION_API_URL ?? "http://localhost:8765";

export const revalidate = 0;

export async function GET(req: NextRequest) {
  const status = req.nextUrl.searchParams.get("status");
  const url = status
    ? `${ESCALATION_API_BASE}/api/escalations?status=${encodeURIComponent(status)}`
    : `${ESCALATION_API_BASE}/api/escalations`;

  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Escalation API proxy error:", err);
    return NextRequest.json(
      { error: "escalation_api_unavailable", escalations: [], total: 0 },
      { status: 503 }
    );
  }
}
