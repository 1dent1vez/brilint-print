#!/usr/bin/env python3
"""
Caja del mostrador · Print with Brilint

Se levanta desde el acceso directo del escritorio, atiende en 127.0.0.1:8787
y se apaga solo tras un rato sin uso. No abre puertos a la red.

    python3 tools/caja.py [--port 8787] [--idle 90]

Además de la cola de pedidos, muestra el estado de la impresora y permite
liberarla (aceptar, activar y tirar lo atorado) sin abrir una terminal.
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
CUPS_ENV = {"LC_ALL": "C", "LANG": "C"}

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
  .job.roto{border-color:#5d2b26}
  .top{display:flex;align-items:flex-start;gap:18px;flex-wrap:wrap}
  .folio{font:700 34px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em}
  .meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;color:var(--gray);font-size:13px}
  .chip{border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
  .chip.review,.chip.reviewing,.chip.quoting,.chip.measuring{color:var(--cobalt-ink);border-color:#24406f}
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
  .fallo{margin:14px 0 0;padding:11px 14px;border-left:2px solid var(--red);
         background:#150d0c;border-radius:0 6px 6px 0;font-size:14px;color:#ffd9d4}
  .fallo .lbl{display:block;font-size:11px;letter-spacing:.14em;color:var(--red);
         text-transform:uppercase;margin-bottom:4px}
  .acts{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;align-items:center}
  .act{border:1px solid var(--line);background:#0d1017;color:var(--white);border-radius:8px;
       padding:11px 16px;font:inherit;font-size:14px;font-weight:600;cursor:pointer}
  .act:hover{border-color:#3a4050}
  .act.primary{background:var(--lime);color:var(--black);border:0}
  .act.ghost{color:var(--cobalt-ink);border-color:#24406f}
  .act.hecho{color:#8ee0b0;border-color:#2f5c3f}
  .act.malo{color:var(--red);border-color:#5d2b26}
  .nota{color:var(--gray);font-size:12px}
  .lines{margin:10px 0 0;padding:0;list-style:none;font-size:13px;color:var(--gray)}
  .lines li{display:flex;justify-content:space-between;padding:3px 0}
  .printer{display:flex;align-items:center;gap:12px;border:1px solid var(--line);
           border-radius:10px;padding:12px 16px;background:var(--panel);font-size:14px}
  .printer.mal{border-color:#5d2b26;background:#150d0c}
  .printer .pdot{width:10px;height:10px;border-radius:50%;background:var(--lime);flex:none}
  .printer.mal .pdot{background:var(--red)}
  .printer .sp{flex:1}
  .printer b{display:block;font-size:14px}
  .printer small{color:var(--gray);font-size:12px}
  .claimbar{display:flex;align-items:center;gap:16px;border:1px solid var(--line);
            border-radius:10px;padding:14px 18px;background:var(--panel)}
  .claimbar small{display:block;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--gray)}
  .claimbar input{width:190px;padding:10px 12px;background:var(--black);color:var(--lime);
    border:1px solid #2f3a1c;border-radius:8px;text-align:center;
    font:700 34px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.22em;
    font-variant-numeric:tabular-nums}
  .claimbar input::placeholder{color:#2a2e36;letter-spacing:.22em}
  .claimbar input:focus-visible{outline:2px solid var(--lime);outline-offset:2px}
  .claimbar .sp{flex:1}
  .claimbar.err{border-color:#5d2b26;background:#150d0c}
  footer{position:fixed;left:0;right:0;bottom:0;padding:10px 24px;background:var(--black);
         border-top:1px solid var(--line);color:var(--gray);font-size:12px;display:flex;gap:16px}
  .toast{position:fixed;bottom:52px;left:50%;transform:translateX(-50%);background:var(--lime);
         color:var(--black);padding:10px 18px;border-radius:999px;font-weight:700;font-size:14px;
         opacity:0;transition:opacity .2s;pointer-events:none;max-width:80vw;text-align:center}
  .toast.on{opacity:1}
  .toast.malo{background:var(--red)}
</style></head>
<body>
<header>
  <span class="dot"></span><h1>Caja · Print with Brilint</h1>
  <span class="sp"></span>
  <button onclick="cargar();cargarImpresora()">Actualizar</button>
</header>
<main>
  <section class="claimbar" id="claimbar">
    <div><small>Código del cliente</small></div>
    <input id="codigo" inputmode="numeric" maxlength="4" placeholder="0000"
           autocomplete="off" aria-label="Código del cliente">
    <button class="act primary" onclick="liberarCodigo()">Liberar e imprimir</button>
    <span class="sp"></span>
    <span class="nota" id="codenote">lo dicta el cliente y aquí se teclea</span>
  </section>
  <section class="printer" id="imp">
    <span class="pdot"></span>
    <div><b id="pname">Impresora</b><small id="pmeta">consultando…</small></div>
    <span class="sp"></span>
    <button class="act malo" id="pbtn" onclick="liberarImpresora()">Liberar impresora</button>
  </section>
  <div id="lista"><div class="empty">Cargando pedidos…</div></div>
</main>
<div class="toast" id="toast"></div>
<footer><span id="pie">—</span><span>Se apaga solo si no se usa</span></footer>
<script>
const LBL={review:"Por revisar",reviewing:"En revisión",quoting:"Cotizando",measuring:"Midiendo",held:"Espera código",
           quoted:"Cotizado",queued:"En fila",printing:"Imprimiendo",done:"Impreso",error:"Error"};
const fmt=n=>new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN"}).format(n||0);
let IMP=null;
function toast(t,malo){const e=document.getElementById("toast");e.textContent=t;
  e.classList.toggle("malo",!!malo);e.classList.add("on");setTimeout(()=>e.classList.remove("on"),3200);}
function hace(iso){
  if(!iso)return "";
  const min=Math.round((Date.now()-new Date(iso).getTime())/60000);
  if(!isFinite(min)||min<1)return "hace segundos";
  if(min<60)return `hace ${min} min`;
  return `hace ${Math.round(min/60)} h`;
}
async function cargarImpresora(){
  try{
    const r=await fetch("/api/impresora");const d=await r.json();
    IMP=d;
    const box=document.getElementById("imp");
    const ok=d.exists&&d.enabled&&d.accepting;
    box.classList.toggle("mal",!ok);
    document.getElementById("pname").textContent=`Impresora ${d.printer||""}`;
    const jobs=(d.jobs||[]).length;
    document.getElementById("pmeta").textContent= ok
      ? (jobs?`lista · ${jobs} trabajo${jobs==1?"":"s"} en cola`:"lista · sin trabajos en cola")
      : `DETENIDA · ${d.reason||"no acepta trabajos"} · ${jobs} atorado${jobs==1?"":"s"}`;
    document.getElementById("pbtn").textContent= ok ? "Liberar impresora" : "Liberar impresora ahora";
  }catch(e){
    document.getElementById("pmeta").textContent="no pude consultar la impresora";
    document.getElementById("imp").classList.add("mal");
  }
}
async function liberarImpresora(){
  const n=(IMP&&IMP.jobs||[]).length;
  const msg=n?`Se van a cancelar ${n} trabajo${n==1?"":"s"} en la cola y se va a reactivar la impresora. ¿Sigo?`
             :"Se va a reactivar la impresora. ¿Sigo?";
  if(!confirm(msg))return;
  try{
    const r=await fetch("/accion",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({accion:"liberar-impresora"})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"falló");
    const c=(d.cancelados||[]).length;
    toast(c?`Impresora libre · ${c} trabajo(s) cancelado(s)`:"Impresora reactivada");
    cargarImpresora();
  }catch(e){toast("Error: "+e.message,true);}
}
async function cargar(){
  try{
    const r=await fetch("/api/pedidos");const d=await r.json();
    document.getElementById("pie").textContent=`Actualizado ${new Date().toLocaleTimeString("es-MX")} · ${d.jobs.length} pedidos`;
    pintar(d.jobs||[]);
  }catch(e){document.getElementById("lista").innerHTML='<div class="empty">No pude leer la cola.</div>';}
}
function acciones(j){
  const a=[];
  if(["review","reviewing"].includes(j.status)){
    a.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
    a.push(`<button class="act primary" onclick="accion('${j.folio}','liberar')">Liberar y cotizar</button>`);
    a.push(`<button class="act hecho" onclick="accion('${j.folio}','ya-salio')">Ya se imprimió a mano</button>`);
  }
  if(j.status==="quoted"){
    a.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
    a.push(`<button class="act primary" onclick="accion('${j.folio}','imprimir')">Confirmar e imprimir</button>`);
    a.push(`<button class="act hecho" onclick="accion('${j.folio}','ya-salio')">Ya se imprimió a mano</button>`);
  }
  if(j.status==="held"){
    a.push(`<span class="nota">Esperando que el cliente dicte su código</span>`);
    a.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
    a.push(`<button class="act" onclick="accion('${j.folio}','liberar-folio')">Liberar igual</button>`);
  }
  if(["queued","printing"].includes(j.status)){
    a.push(`<span class="act ghost" style="cursor:default">Saliendo…</span>`);
    a.push(`<button class="act hecho" onclick="accion('${j.folio}','ya-salio')">Ya salió</button>`);
    a.push(`<button class="act malo" onclick="accion('${j.folio}','reimprimir')">Se atoró · reimprimir</button>`);
  }
  if(j.status==="error"){
    a.push(`<button class="act ghost" onclick="accion('${j.folio}','abrir')">Abrir carpeta</button>`);
    a.push(`<button class="act hecho" onclick="accion('${j.folio}','ya-salio')">Ya salió · cobrar</button>`);
    a.push(`<button class="act malo" onclick="accion('${j.folio}','reimprimir')">Reimprimir</button>`);
    a.push(`<button class="act" onclick="liberarImpresora()">Liberar impresora</button>`);
  }
  if(j.status==="done"){
    a.push(`<span class="nota">${j.printed_by==="mostrador"?"Impreso en el mostrador":"Impreso por la app"} ${hace(j.printed_at)}</span>`);
  }
  return a.join("");
}
function pintar(jobs){
  const l=document.getElementById("lista");
  if(!jobs.length){l.innerHTML='<div class="empty">Sin pedidos por ahora.</div>';return;}
  l.innerHTML=jobs.map(j=>{
    const cls=["done"].includes(j.status)?"job listo":j.status==="error"?"job roto"
      :(["review","reviewing","quoted"].includes(j.status)?"job nuevo":"job");
    const lines=(j.quote&&j.quote.lines)||[];
    const fallo=j.error?`<div class="fallo"><span class="lbl">Por qué no salió</span>${j.error}
      ${j.attempts?`<div class="nota" style="margin-top:6px">Se mandó ${j.attempts} vez/veces a la impresora · ${hace(j.attempted_at)}</div>`:""}</div>`:"";
    return `<div class="${cls}">
      <div class="top">
        <div>
          <div class="folio">${j.folio}</div>
          <div class="meta">
            <span class="chip ${j.status}">${LBL[j.status]||j.status}</span>
            <span>${j.copies} ${j.copies==1?"copia":"copias"}</span>
            <span>${j.pages} pág.</span>
            <span>${j.mode==="color"?"Color":"B/N"}</span>
            <span class="nota">${hace(j.created_at)}</span>
            <button class="act" style="padding:4px 10px;font-size:12px" onclick="copiar('${j.folio}')">Copiar folio</button>
          </div>
        </div>
        <div class="total"><b>${j.total?fmt(j.total):"—"}</b><span>Total</span></div>
      </div>
      ${j.notes?`<div class="notes"><span class="lbl">Indicaciones del cliente</span>${j.notes}</div>`:""}
      ${fallo}
      ${lines.length?`<ul class="lines">${lines.map(x=>`<li><span>${x.label} · ${x.pages} pág.</span><span>${fmt(x.subtotal)}</span></li>`).join("")}</ul>`:""}
      <div class="acts">${acciones(j)}</div>
    </div>`;
  }).join("");
}
function copiar(f){navigator.clipboard.writeText(f).then(()=>toast("Folio copiado: "+f));}
async function accion(folio,accion){
  const etiqueta={liberar:"Liberado · midiendo",imprimir:"Confirmado · imprimiendo",
                  "ya-salio":"Cerrado · quedó como impreso","reimprimir":"De vuelta en la fila",
                  abrir:"Carpeta abierta"}[accion]||"Hecho";
  try{
    const r=await fetch("/accion",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({folio,accion})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"falló");
    toast(etiqueta);
    setTimeout(()=>{cargar();cargarImpresora();},800);
  }catch(e){toast("Error: "+e.message,true);}
}
async function liberarCodigo(){
  const inp=document.getElementById("codigo");
  const code=(inp.value||"").replace(/[^0-9]/g,"").slice(0,4);
  const bar=document.getElementById("claimbar");
  const note=document.getElementById("codenote");
  if(code.length!==4){bar.classList.add("err");note.textContent="Faltan dígitos";return;}
  try{
    const r=await fetch("/accion",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({accion:"liberar-codigo",codigo:code})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||"no encontré ese código");
    bar.classList.remove("err");
    inp.value="";
    note.textContent=d.already?`Ya iba en camino · ${d.folio}`:`${d.folio} → imprimiendo`;
    toast(d.already?`${d.folio} ya estaba liberado`:`${d.folio} · a la impresora`);
    setTimeout(()=>{cargar();cargarImpresora();},700);
  }catch(e){
    bar.classList.add("err");
    note.textContent=e.message;
    inp.select();
  }
}
document.addEventListener("DOMContentLoaded",()=>{
  const inp=document.getElementById("codigo");
  if(!inp) return;
  inp.addEventListener("input",()=>{
    const limpio=(inp.value||"").replace(/[^0-9]/g,"").slice(0,4);
    if(inp.value!==limpio) inp.value=limpio;
    document.getElementById("claimbar").classList.remove("err");
    if(limpio.length===4) liberarCodigo();
  });
  inp.addEventListener("keydown",e=>{if(e.key==="Enter") liberarCodigo();});
  inp.focus();
});
cargar();cargarImpresora();
setInterval(()=>{cargar();},5000);
setInterval(()=>{cargarImpresora();},8000);
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


def cups(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **CUPS_ENV})


def impresora_info() -> dict:
    """Estado real de la cola de CUPS: habilitada, aceptando y qué hay atorado."""
    printer = cfg().get("printer", "HP_USB")
    out = (cups(["lpstat", "-p", printer]).stdout or "").strip()
    flat = " ".join(out.split())
    low = flat.lower()
    info = {"printer": printer, "exists": bool(flat), "enabled": True,
            "accepting": True, "reason": "", "line": flat, "jobs": []}
    if "disabled" in low or "deshabilitada" in low:
        info["enabled"] = False
        info["reason"] = flat.split(" - ", 1)[1] if " - " in flat else "sin razón reportada"
    if "not accepting" in low or "no acepta" in low:
        info["accepting"] = False
    cola = (cups(["lpstat", "-W", "not-completed", "-o", printer]).stdout or "")
    for line in cola.splitlines():
        parts = line.split()
        if parts and parts[0].startswith(printer + "-"):
            info["jobs"].append({"id": parts[0], "detail": line.strip()})
    return info


def liberar_impresora() -> dict:
    """Acepta, activa y tira lo atorado: lo mismo que se hacía a mano."""
    info = impresora_info()
    printer = info["printer"]
    cups(["cupsaccept", printer])
    cups(["cupsenable", printer])
    cancelados, fallos = [], []
    for job in info["jobs"]:
        r = cups(["cancel", job["id"]])
        if r.returncode == 0:
            cancelados.append(job["id"])
        else:
            fallos.append(f"{job['id']}: {(r.stderr or r.stdout).strip()[:120]}")
    time.sleep(1)
    after = impresora_info()
    return {"cancelados": cancelados, "fallos": fallos, "impresora": after,
            "error": None if after["enabled"] else f"sigue detenida: {after['reason']}"}


def abrir_carpeta(folio: str) -> bool:
    target = REVIEW_HOME / folio
    if not target.exists():
        target = REVIEW_HOME
        if not target.exists():
            return False
    subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "brilint-caja/1.1"

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
        if self.path == "/api/impresora":
            try:
                return self._json(200, impresora_info())
            except Exception as e:  # noqa: BLE001
                return self._json(500, {"error": str(e)[:160]})
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
        if not folio and accion != "liberar-impresora":
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
        if accion == "ya-salio":
            code, data = api("/api/agent/manual", "POST",
                             {"folio": folio, "action": "printed_here"})
            return self._json(code, data)
        if accion == "reimprimir":
            code, data = api("/api/agent/manual", "POST",
                             {"folio": folio, "action": "requeue"})
            return self._json(code, data)
        if accion == "liberar-impresora":
            try:
                res = liberar_impresora()
            except Exception as e:  # noqa: BLE001
                return self._json(500, {"error": str(e)[:160]})
            return self._json(500 if res.get("error") else 200, res)
        if accion == "liberar-codigo":
            codigo = str(payload.get("codigo") or "").strip()
            code, data = api("/api/agent/manual", "POST", {"action": "release", "code": codigo})
            return self._json(code, data)
        if accion == "liberar-folio":
            code, data = api("/api/agent/manual", "POST", {"action": "release", "folio": folio})
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
