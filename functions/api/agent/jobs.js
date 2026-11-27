import { json, bad, isAgent } from "../../_lib.js";

// Lista de pedidos para la caja del mostrador.
export async function onRequestGet({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, parseInt(url.searchParams.get("limit") || "14", 10)));

  const res = await env.DB.prepare(
    `SELECT folio, created_at, status, mode, copies, pages, pages_verified, total,
            notes, review, quote_json, printed_at, printed_by, error, attempts,
            claimed_at, attempted_at, confirmed_at, purged_at,
            json_extract(plan_json, '$.prepared_at') AS prepared_at,
            json_extract(plan_json, '$.price_terms') AS price_terms
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
    notes: ["review_pending", "review_held"].includes(r.status) ? "" : r.notes || "",
    review: r.review || 0,
    review_authorized: Boolean(r.review && r.confirmed_at && r.price_terms === "variable"),
    review_ready: Boolean(r.prepared_at && !r.purged_at),
    quote: r.quote_json ? JSON.parse(r.quote_json) : null,
    printed_at: r.printed_at,
    printed_by: r.printed_by || null,
    error: r.error || null,
    attempts: r.attempts || 0,
    claimed_at: r.claimed_at || null,
    attempted_at: r.attempted_at || null,
  }));

  return json({ jobs });
}
