#!/usr/bin/env python3
"""
Servidor local que imita Cloudflare Pages + D1 + R2 para probar el flujo completo
sin desplegar. Sirve site/ y las mismas rutas /api/*.

    python3 tools/mock_api.py [--port 8799]

Guarda los pedidos en tools/.mock/db.json y los archivos en tools/.mock/r2/.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import random
import re
import string
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MOCK = ROOT / "tools" / ".mock"
DB = MOCK / "db.json"
R2 = MOCK / "r2"
TOKEN = "token-de-prueba"
PRICES = {"bw": 2, "color": 8, "currency": "MXN", "max_mb": 80,
          "max_files": 8, "max_copies": 200, "paper": "letter"}
PRICES_BW = [
    {"id": "texto", "label": "Texto normal", "price": 1.5, "max_cov": 0.10},
    {"id": "grafico", "label": "Gráficos o fondo oscuro", "price": 3.0, "max_cov": 1.01},
]
PRICES_COLOR = [
    {"id": "ligero", "label": "Color ligero", "price": 3.0, "max_chroma": 0.03},
    {"id": "normal", "label": "Color normal", "price": 5.0, "max_chroma": 0.10},
    {"id": "abundante", "label": "Color abundante", "price": 8.0, "max_chroma": 0.30},
    {"id": "total", "label": "Color total", "price": 12.0, "max_chroma": 0.70},
    {"id": "saturado", "label": "Página saturada", "price": 15.0, "max_chroma": 1.01},
]
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def load_db() -> dict:
    if DB.exists():
        return json.loads(DB.read_text())
    return {"jobs": []}


def save_db(db: dict) -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(db, indent=2, ensure_ascii=False))


def make_folio() -> str:
    now = time.gmtime()
    return f"{now.tm_year % 100:02d}{now.tm_mon:02d}{now.tm_mday:02d}-" + "".join(
        random.choice(ALPHA) for _ in range(4))


def parse_multipart(body: bytes, boundary: bytes) -> list[dict]:
    parts = []
    for chunk in body.split(b"--" + boundary):
        if not chunk.strip(b"\r\n-"):
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        headers = {}
        for line in head.decode("latin-1").split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        disp = headers.get("content-disposition", "")
        name = re.search(r'name="([^"]*)"', disp)
        filename = re.search(r'filename="([^"]*)"', disp)
        parts.append({
            "name": name.group(1) if name else "",
            "filename": filename.group(1) if filename else None,
            "content_type": headers.get("content-type", "application/octet-stream"),
            "data": data,
        })
    return parts


class Handler(BaseHTTPRequestHandler):
    server_version = "mock-pages/1.0"

    def log_message(self, fmt, *args):  # silencioso
        pass

    # ---------------- helpers ---------------- #
    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_bytes(self, raw: bytes, ctype="application/octet-stream", status=200):
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def agent_ok(self) -> bool:
        return self.headers.get("x-agent-token") == TOKEN

    # ---------------- rutas ---------------- #
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)

        if path == "/api/prices":
            return self.send_json(PRICES)

        m = re.fullmatch(r"/api/jobs/([0-9]{6}-[A-Z2-9]{4})", path)
        if m:
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == m.group(1)), None)
            if not job:
                return self.send_json({"error": "No encontramos ese folio."}, 404)
            return self.send_json({k: job.get(k) for k in
                                   ("folio", "created_at", "status", "mode", "copies",
                                    "pages", "pages_verified", "total", "printed_at", "quote")})

        if path == "/api/agent/jobs":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            db = load_db()
            jobs = [{k: j.get(k) for k in ("folio", "created_at", "status", "mode", "copies",
                                           "pages", "pages_verified", "total", "notes", "review",
                                           "quote", "printed_at", "printed_by", "error",
                                           "attempts", "claimed_at", "attempted_at")}
                    for j in sorted(db["jobs"], key=lambda x: x["created_at"], reverse=True)]
            return self.send_json({"jobs": jobs})

        if path == "/api/agent/file":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            db = load_db()
            folio = (qs.get("folio") or [""])[0]
            idx = int((qs.get("i") or ["0"])[0])
            job = next((j for j in db["jobs"] if j["folio"] == folio), None)
            if not job or idx >= len(job["files"]):
                return self.send_json({"error": "Archivo no encontrado."}, 404)
            f = job["files"][idx]
            raw = (R2 / f["key"]).read_bytes()
            return self.send_bytes(raw, f["type"])

        # estáticos
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (SITE / rel).resolve()
        if not str(target).startswith(str(SITE.resolve())) or not target.is_file():
            return self.send_bytes(b"no encontrado", "text/plain", 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix == ".woff2":
            ctype = "font/woff2"
        return self.send_bytes(target.read_bytes(), ctype)

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)

        if u.path == "/api/jobs":
            return self.create_job(body)
        if u.path == "/api/agent/next":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            try:
                stage = (json.loads(body or b"{}") or {}).get("stage", "print")
            except json.JSONDecodeError:
                stage = "print"
            from_status, to_status = {"quote": ("quoting", "measuring"),
                                      "review": ("review", "reviewing")}.get(stage, ("queued", "printing"))
            db = load_db()
            job = next((j for j in db["jobs"] if j["status"] == from_status), None)
            if not job:
                return self.send_json({"stage": stage, "job": None})
            job["status"] = to_status
            job["claimed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_db(db)
            return self.send_json({"stage": stage, "job": {k: job[k] for k in
                                           ("folio", "created_at", "mode", "copies", "pages",
                                            "total", "customer", "phone", "notes")
                                            if k in job}
                                   | {"review": job.get("review", 0),
                                      "files": [{"index": i, **{kk: f[kk] for kk in ("name", "pages", "size", "type")}}
                                                for i, f in enumerate(job["files"])]}})
        if u.path == "/api/agent/quote":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            payload = json.loads(body or b"{}")
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == payload.get("folio")), None)
            if not job:
                return self.send_json({"error": "Pedido no encontrado."}, 404)
            if job["status"] in ("quoted", "queued", "printing", "done"):
                return self.send_json({"ok": True, "already": True})
            table = PRICES_COLOR if job["mode"] == "color" else PRICES_BW
            counts = {t["id"]: 0 for t in table}
            for p in payload.get("pages", []):
                value = p["chroma"] if job["mode"] == "color" else p["cov"]
                key = "max_chroma" if job["mode"] == "color" else "max_cov"
                tier = next((t for t in table if value <= t[key]), table[-1])
                counts[tier["id"]] += 1
            lines = [{"id": t["id"], "label": t["label"], "pages": counts[t["id"]],
                      "price": t["price"], "subtotal": round(counts[t["id"]] * t["price"], 2)}
                     for t in table if counts[t["id"]]]
            per_copy = round(sum(l["subtotal"] for l in lines), 2)
            job["status"] = "quoted"
            job["quote"] = {"lines": lines, "per_copy": per_copy,
                            "total": round(per_copy * job["copies"], 2),
                            "copies": job["copies"], "pages": len(payload.get("pages", []))}
            job["total"] = job["quote"]["total"]
            job["pages_verified"] = job["quote"]["pages"]
            save_db(db)
            return self.send_json({"ok": True, "folio": job["folio"], "total": job["total"], "lines": lines})
        m = re.fullmatch(r"/api/jobs/([0-9]{6}-[A-Z2-9]{4})/confirm", u.path)
        if m:
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == m.group(1)), None)
            if not job:
                return self.send_json({"error": "No encontramos ese folio."}, 404)
            if job["status"] == "quoted":
                job["status"] = "held"          # espera el código del cliente
                save_db(db)
            return self.send_json({"folio": job["folio"], "status": job["status"],
                                   "total": job["total"], "code": job.get("claim_code")})
        if u.path == "/api/agent/release":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            payload = json.loads(body or b"{}")
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == payload.get("folio")), None)
            if not job:
                return self.send_json({"error": "No encontramos ese folio."}, 404)
            if job["status"] not in ("review", "reviewing"):
                return self.send_json({"error": f"El pedido está en estado {job['status']}."}, 409)
            job["status"] = "quoting"
            job["claimed_at"] = None
            save_db(db)
            return self.send_json({"ok": True, "folio": job["folio"], "status": "quoting"})
        if u.path == "/api/agent/manual":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            payload = json.loads(body or b"{}")
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == payload.get("folio")), None)
            if not job:
                return self.send_json({"error": "No encontramos ese folio."}, 404)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            action = payload.get("action")
            if action == "printed_here":
                job["status"] = "done"
                job["printed_at"] = job.get("printed_at") or now
                job["printed_by"] = "mostrador"
                job["claimed_at"] = None
                job["error"] = None
                save_db(db)
                return self.send_json({"ok": True, "folio": job["folio"], "status": "done"})
            if action == "requeue":
                if job["status"] not in ("error", "queued", "printing"):
                    return self.send_json({"error": f"No hace falta reimprimir: {job['status']}."}, 409)
                job["status"] = "queued"
                job["claimed_at"] = None
                job["attempts"] = 0
                job["error"] = None
                job["printed_at"] = None
                save_db(db)
                return self.send_json({"ok": True, "folio": job["folio"], "status": "queued"})
            if action == "release":
                codigo = str(payload.get("code") or "").strip()
                folio_j = str(payload.get("folio") or "").upper()
                job = next((j for j in db["jobs"]
                            if j["status"] in ("held", "quoted")
                            and ((codigo and j.get("claim_code") == codigo)
                                 or (folio_j and j["folio"] == folio_j))), None)
                if not job:
                    return self.send_json({"error": "Ningún pedido esperando con ese código."}, 404)
                job["status"] = "queued"
                job["claimed_at"] = None
                save_db(db)
                return self.send_json({"ok": True, "folio": job["folio"], "status": "queued",
                                       "total": job.get("total")})
            return self.send_json({"error": "acción desconocida"}, 400)
        if u.path == "/api/agent/ack":
            if not self.agent_ok():
                return self.send_json({"error": "No autorizado."}, 401)
            payload = json.loads(body or b"{}")
            db = load_db()
            job = next((j for j in db["jobs"] if j["folio"] == payload.get("folio")), None)
            if not job:
                return self.send_json({"error": "Pedido no encontrado."}, 404)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            status = payload.get("status")
            if status == "sent":
                if job["status"] != "printing":
                    return self.send_json({"ok": True, "print": False, "folio": job["folio"],
                                           "status": job["status"],
                                           "reason": f"el pedido está en {job['status']}"})
                job["attempts"] = job.get("attempts", 0) + 1
                job["attempted_at"] = now
                save_db(db)
                return self.send_json({"ok": True, "print": True, "folio": job["folio"],
                                       "status": "printing"})
            if job["status"] not in ("printing", "queued"):
                save_db(db)
                return self.send_json({"ok": True, "already": True, "folio": job["folio"],
                                       "status": job["status"]})
            job["status"] = status
            job["pages_verified"] = payload.get("pages_verified") or job.get("pages_verified")
            job["error"] = payload.get("error")
            job["claimed_at"] = None
            if status == "done":
                job["printed_at"] = now
                job["printed_by"] = job.get("printed_by") or "agente"
            save_db(db)
            return self.send_json({"ok": True, "folio": job["folio"], "status": status})
        return self.send_json({"error": "ruta desconocida"}, 404)

    def create_job(self, body: bytes):
        ctype = self.headers.get("content-type", "")
        if "multipart/form-data" not in ctype:
            return self.send_json({"error": "Se esperaba multipart"}, 400)
        boundary = re.search(r"boundary=([^;]+)", ctype).group(1).encode()
        parts = parse_multipart(body, boundary)
        fields = {p["name"]: p["data"].decode("utf-8", "replace") for p in parts if not p["filename"]}
        files = [p for p in parts if p["filename"]]

        if not files:
            return self.send_json({"error": "No llegó ningún archivo."}, 400)
        if len(files) > PRICES["max_files"]:
            return self.send_json({"error": "Demasiados archivos."}, 400)
        for f in files:
            if f["content_type"] not in ("application/pdf", "image/jpeg", "image/png"):
                return self.send_json({"error": f"Formato no aceptado: {f['filename']}"}, 400)
        total_bytes = sum(len(f["data"]) for f in files)
        if total_bytes > PRICES["max_mb"] * 1024 * 1024:
            return self.send_json({"error": "El pedido pasa del límite."}, 413)

        # Código del cliente: 4 dígitos que él dicta en el mostrador.
        abiertos = {j.get("claim_code") for j in load_db()["jobs"]
                    if j["status"] not in ("done", "error")}
        claim = "%04d" % random.randrange(10000)
        while claim in abiertos:
            claim = "%04d" % random.randrange(10000)

        mode = fields.get("mode", "bw")
        copies = int(fields.get("copies", 1))
        try:
            pages = json.loads(fields.get("pages", "[]"))
        except json.JSONDecodeError:
            pages = []
        pages = [max(1, int(p)) for p in pages] or [1] * len(files)
        total_pages = sum(pages)
        folio = make_folio()

        db = load_db()
        stored = []
        for i, f in enumerate(files):
            key = f"jobs/{folio}/{i:02d}_{f['filename']}"
            dest = R2 / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(f["data"])
            stored.append({"name": f["filename"], "type": f["content_type"],
                           "size": len(f["data"]), "pages": pages[i], "key": key})

        db["jobs"].append({
            "folio": folio,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "review" if (fields.get("review") == "1" and len(fields.get("notes", "")) >= 4) else "quoting",
            "mode": mode, "copies": copies,
            "pages": total_pages, "pages_verified": None,
            "total": 0, "quote": None,
            "customer": fields.get("customer", ""), "phone": fields.get("phone", ""),
            "notes": fields.get("notes", ""), "files": stored,
            "review": 1 if (fields.get("review") == "1" and len(fields.get("notes", "")) >= 4) else 0,
            "claim_code": claim,
            "claimed_at": None, "printed_at": None, "printed_by": None, "error": None,
            "attempts": 0, "attempted_at": None,
        })
        save_db(db)
        return self.send_json({
            "folio": folio, "code": claim,
            "status": "review" if (fields.get("review") == "1" and len(fields.get("notes", "")) >= 4) else "quoting",
            "mode": mode, "copies": copies,
            "pages": total_pages,
            "currency": PRICES["currency"],
            "files": [{"name": s["name"], "pages": s["pages"]} for s in stored],
        })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    MOCK.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock en http://127.0.0.1:{args.port} · token {TOKEN}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
