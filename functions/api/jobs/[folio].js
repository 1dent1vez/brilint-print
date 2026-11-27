import { json, bad } from "../../_lib.js";

export async function onRequestGet({ params, env }) {
  const folio = String(params.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.", 404);

  const row = await env.DB.prepare(
    `SELECT folio, created_at, status, mode, copies, pages, pages_verified, total,
            printed_at, quote_json, claim_code
       FROM jobs WHERE folio = ?`
  ).bind(folio).first();

  if (!row) return bad("No encontramos ese folio.", 404);

  return json({
    folio: row.folio,
    created_at: row.created_at,
    status: row.status,
    mode: row.mode,
    copies: row.copies,
    pages: row.pages_verified || row.pages,
    total: row.total,
    quote: row.quote_json ? JSON.parse(row.quote_json) : null,
    code: row.claim_code || null,
    ready_at: row.status === "done" ? row.printed_at : null,
  });
}
