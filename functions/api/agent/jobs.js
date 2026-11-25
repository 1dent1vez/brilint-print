import { json, bad, isAgent } from "../../_lib.js";

// Lista de pedidos para la caja del mostrador.
export async function onRequestGet({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, parseInt(url.searchParams.get("limit") || "14", 10)));

  const res = await env.DB.prepare(
    `SELECT folio, created_at, status, mode, copies, pages, pages_verified, total,
            notes, review, quote_json, printed_at
       FROM jobs
      ORDER BY created_at DESC
      LIMIT ?`
  ).bind(limit).all();

  const jobs = (res.results || []).map((r) => ({
    folio: r.folio,
    created_at: r.created_at,
    status: r.status,
    mode: r.mode,
    copies: r.copies,
    pages: r.pages_verified || r.pages,
    total: r.total,
    notes: r.notes || "",
    review: r.review || 0,
    quote: r.quote_json ? JSON.parse(r.quote_json) : null,
    printed_at: r.printed_at,
  }));

  return json({ jobs });
}
