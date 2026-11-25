#!/usr/bin/env python3
"""
Caja del mostrador · Print with Brilint

Se levanta desde el acceso directo del escritorio, atiende en 127.0.0.1:8787
y se apaga solo tras un rato sin uso. No abre puertos a la red.

    python3 tools/caja.py [--port 8787] [--idle 90]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "agent" / "config.json"
REVIEW_HOME = Path.home() / "Desktop" / "Impresiones"
LAST_HIT = time.time()
IDLE_MIN = 90

PAGE = """<!DOCTYPE html>
<html lang="es-MX"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caja · Print with Brilint</title>
<style>
  :root{--black:#030407;--panel:#080a0f;--white:#f5f5f1;--gray:#a5a8b1;--line:#272a30;
        --cobalt:#1558c9;--cobalt-ink:#7aa7ff;--lime:#d4ff24;--red:#ff8f85}
  *{box-sizing:border-box}
  body{margin:0;background:var(--black);color:var(--white);
       font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  header{display:flex;align-items:center;gap:14px;padding:18px 24px;border-bottom:1px solid var(--line)}
  header h1{margin:0;font-size:15px;letter-spacing:.16em;text-transform:uppercase;font-weight:700}
  header .dot{width:8px;height:8px;border-radius:50%;background:var(--lime)}
  header .sp{flex:1}
  header button{background:none;border:1px solid var(--line);color:var(--gray);
       border-radius:999px;padding:7px 14px;font:inherit;font-size:13px;cursor:pointer}
  main{padding:22px 24px 60px;max-width:1080px;margin:0 auto;display:grid;gap:14px}
  .empty{color:var(--gray);padding:40px 0;text-align:center}
  .job{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
  .job.nuevo{border-color:var(--cobalt)}
  .job.listo{border-color:#2f5c3f}
  .top{display:flex;align-items:flex-start;gap:18px;flex-wrap:wrap}
  .folio{font:700 34px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em}
  .meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;color:var(--gray);font-size:13px}
  .chip{border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
  .chip.review{color:var(--cobalt-ink);border-color:#24406f}
  .chip.quoted{color:var(--lime);border-color:#3d5220}
  .chip.done{color:#8ee0b0;border-color:#2f5c3f}
  .chip.error{color:var(--red);border-color:#5d2b26}
  .total{margin-left:auto;text-align:right}
  .total b{display:block;font-size:38px;line-height:1;font-variant-numeric:tabular-nums}
  .total span{font-size:12px;color:var(--gray);letter-spacing:.08em;text-transform:uppercase}
  .notes{margin:14px 0 0;padding:12px 14px;border-left:2px solid var(--lime);
         background:#0d1017;border-radius:0 6px 6px 0;font-size:15px}
  .notes .lbl{display:block;font-size:11px;letter-spacing:.14em;color:var(--gray);
         text-transform:uppercase;margin-bottom:5px}
  .acts{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
  .act{border:1px solid var(--line);background:#0d1017;color:var(--white);border-radius:8px;
       padding:11px 16px;font:inherit;font-size:14px;font-weight:600;cursor:pointer}
  .act:hover{border-color:#3a4050}
  .act.primary{background:var(--lime);color:var(--black);border:0}
  .act.ghost{color:var(--cobalt-ink);border-color:#24406f}
  .lines{margin:10px 0 0;padding:0;list-style:none;font-size:13px;color:var(--gray)}
  .lines li{display:flex;justify-content:space-between;padding:3px 0}
  footer{position:fixed;left:0;right:0;bottom:0;padding:10px 24px;background:var(--black);
         border-top:1px solid var(--line);color:var(--gray);font-size:12px;display:flex;gap:16px}
  .toast{position:fixed;bottom:52px;left:50%;transform:translateX(-50%);background:var(--lime);
         color:var(--black);padding:10px 18px;border-radius:999px;font-weight:700;font-size:14px;
         opacity:0;transition:opacity .2s;pointer-events:none}
  .toast.on{opacity:1}
</style></head>
<body>
<header>
  <span class="dot"></span><h1>Caja · Print with Brilint</h1>
  <span class="sp"></span>
  <button onclick="cargar()">Actualizar</button>
</header>
<main id="lista"><div class="empty">Cargando pedidos…</div></main>
<div class="toast" id="toast"></div>
<footer><span id="pie">—</span><span>Se apaga solo si no se usa</span></footer>
<script>
const LBL={review:"Por revisar",reviewing:"En revisión",quoting:"Cotizando",measuring:"Midiendo",
           quoted:"Cotizado",queued:"En fila",printing:"Imprimiendo",done:"Impreso",error:"Error"};
const fmt=n=>new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN"}).format(n||0);
function toast(t){const e=document.getElementById("toast");e.textContent=t;e.classList.add("on");
  setTimeout(()=>e.classList.remove("on"),2200);}
async function cargar(){
  try{
    const r=await fetch("/api/pedidos");const d=await r.json();
    document.getElementById("pie").textContent=`Actualizado ${new Date().toLocaleTimeString("es-MX")} · ${d.jobs.length} pedidos`;
    pintar(d.jobs||[]);
  }catch(e){document.getElementById("lista").innerHTML='<div class="empty">No pude leer la cola.</div>';}
}
function pintar(jobs){
  const l=document.getElementById("lista");
  if(!jobs.length){l.innerHTML='<div class="empty">Sin pedidos por ahora.</div>';return;}
  l.innerHTML=jobs.map(j=>{
    const cls=j.status==="done"?"job listo":(["review","reviewing","quoted"].includes(j.status)?"job nuevo":"job");
    const lines=(j.quote&&j.quote.lines)||[];
    const acts=[];
    if(["review","reviewing"].includes(j.status)){
      acts.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
      acts.push(`<button class="act primary" onclick="accion('${j.folio}','liberar')">Liberar y cotizar</button>`);
    }
    if(j.status==="quoted"){
      acts.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
      acts.push(`<button class="act primary" onclick="accion('${j.folio}','imprimir')">Confirmar e imprimir</button>`);
    }
    if(["queued","printing"].includes(j.status)) acts.push(`<span class="act ghost">Saliendo…</span>`);
    return `<div class="${cls}">
      <div class="top">
        <div>
          <div class="folio">${j.folio}</div>
          <div class="meta">
            <span class="chip ${j.status}">${LBL[j.status]||j.status}</span>
            <span>${j.copies} ${j.copies==1?"copia":"copias"}</span>
            <span>${j.pages} pág.</span>
            <span>${j.mode==="color"?"Color":"B/N"}</span>
            <button class="act" style="padding:4px 10px;font-size:12px" onclick="copiar('${j.folio}')">Copiar folio</button>
          </div>
        </div>
        <div class="total"><b>${j.total?fmt(j.total):"—"}</b><span>Total</span></div>
      </div>
      ${j.notes?`<div class="notes"><span class="lbl">Indicaciones del cliente</span>${j.notes}</div>`:""}
      ${lines.length?`<ul class="lines">${lines.map(x=>`<li><span>${x.label} · ${x.pages} pág.</span><span>${fmt(x.subtotal)}</span></li>`).join("")}</ul>`:""}
      <div class="acts">${acts.join("")}</div>
    </div>`;
  }).join("");
}
function copiar(f){navigator.clipboard.writeText(f).then(()=>toast("Folio copiado: "+f));}
async function accion(folio,accion){
  try{
    const r=await fetch("/accion",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({folio,accion})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"falló");
    toast(accion==="liberar"?"Liberado · midiendo":accion==="imprimir"?"Confirmado · imprimiendo":"Carpeta abierta");
    setTimeout(cargar,1200);
  }catch(e){toast("Error: "+e.message);}
}
cargar();setInterval(cargar,5000);
</script></body></html>
"""


def cfg() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def api(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    c = cfg()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        c["api_base"].rstrip("/") + path, data=data, method=method,
        headers={"x-agent-token": c["agent_token"], "accept": "application/json",
                 "content-type": "application/json",
                 "user-agent": "BrilintCaja/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {"error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return 599, {"error": str(e)[:120]}


def abrir_carpeta(folio: str) -> bool:
    target = REVIEW_HOME / folio
    if not target.exists():
        target = REVIEW_HOME
        if not target.exists():
            return False
    subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "brilint-caja/1.0"

    def log_message(self, *a):  # silencioso
        pass

    def _send(self, code: int, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        global LAST_HIT
        LAST_HIT = time.time()
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if self.path == "/api/ping":
            return self._json(200, {"ok": True})
        if self.path.startswith("/api/pedidos"):
            code, data = api("/api/agent/jobs?limit=14")
            return self._json(code if code < 500 else 502, data)
        self._json(404, {"error": "no existe"})

    def do_POST(self):
        global LAST_HIT
        LAST_HIT = time.time()
        if self.path != "/accion":
            return self._json(404, {"error": "no existe"})
        try:
            n = int(self.headers.get("content-length") or 0)
            payload = json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:
            return self._json(400, {"error": "cuerpo inválido"})
        folio = str(payload.get("folio") or "").upper()
        accion = str(payload.get("accion") or "")
        if not folio:
            return self._json(400, {"error": "falta folio"})

        if accion == "abrir":
            ok = abrir_carpeta(folio)
            return self._json(200 if ok else 404, {"ok": ok, "error": None if ok else "carpeta no encontrada"})
        if accion == "liberar":
            code, data = api("/api/agent/release", "POST", {"folio": folio})
            return self._json(code, data)
        if accion == "imprimir":
            code, data = api(f"/api/jobs/{folio}/confirm", "POST", {})
            return self._json(code, data)
        return self._json(400, {"error": f"acción desconocida: {accion}"})


def vigilante(idle_min: int):
    while True:
        time.sleep(30)
        if time.time() - LAST_HIT > idle_min * 60:
            print("Caja sin uso: cerrando", flush=True)
            os._exit(0)


def main() -> int:
    global IDLE_MIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--idle", type=int, default=90, help="minutos sin uso antes de cerrarse")
    args = ap.parse_args()
    IDLE_MIN = args.idle

    threading.Thread(target=vigilante, args=(args.idle,), daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Caja lista en http://127.0.0.1:{args.port} (se cierra a los {args.idle} min sin uso)", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
