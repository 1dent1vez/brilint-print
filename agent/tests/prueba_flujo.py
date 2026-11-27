#!/usr/bin/env python3
"""Prueba de humo del flujo de estados contra un servidor real.

Sirve contra `wrangler pages dev` (D1 local), contra el mock (tools/mock_api.py)
o contra producción, con el token del agente:

    python3 agent/tests/prueba_flujo.py --api http://127.0.0.1:8788 --token token-de-prueba

Recorre el caso que rompía: un pedido con indicaciones que el mostrador imprime
a mano, y el pedido siguiente que va directo a la impresora.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

ok = 0
fallos: list[str] = []


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {nombre}")
    else:
        fallos.append(nombre + (f" · {detalle}" if detalle else ""))
        print(f"  ✗ {nombre} {detalle}")


class Cliente:
    def __init__(self, api: str, token: str):
        self.api = api.rstrip("/")
        self.token = token

    def _req(self, path: str, method: str = "GET", body: dict | None = None,
             raw: bytes | None = None, headers: dict | None = None) -> tuple[int, dict]:
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"accept": "application/json", "user-agent": "BrilintPrueba/1.0"}
        h.update(headers or {})
        if body is not None:
            h["content-type"] = "application/json"
        req = urllib.request.Request(self.api + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            with e:
                try:
                    return e.code, json.loads(e.read().decode() or "{}")
                except Exception:
                    return e.code, {"error": "sin cuerpo"}

    def agente(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        return self._req(path, "POST", body, headers={"x-agent-token": self.token})

    def crear_intento(self, notas: str = "", review: bool = False, copias: int = 1) -> tuple[int, dict]:
        """Como crear(), pero devuelve el código HTTP en vez de lanzar."""
        try:
            return 200, self.crear(notas, review=review, copias=copias)
        except RuntimeError as e:
            msg = str(e)
            code = int(msg.split(":")[1].split()[0]) if ":" in msg else 0
            return code, {"error": msg}

    def crear(self, notas: str, review: bool = True, copias: int = 1) -> dict:
        b = "----prueba" + uuid.uuid4().hex
        partes = []
        campos = {"mode": "bw", "copies": str(copias), "pages": json.dumps([1]),
                  "notes": notas, "customer": "Prueba", "phone": "5555555555"}
        if review:
            campos["review"] = "1"
        for k, v in campos.items():
            partes.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        partes.append(f"--{b}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"prueba.pdf\"\r\n"
                      f"Content-Type: application/pdf\r\n\r\n".encode() + PDF + b"\r\n")
        partes.append(f"--{b}--\r\n".encode())
        cuerpo = b"".join(partes)
        code, data = self._req("/api/jobs", "POST", raw=cuerpo,
                               headers={"content-type": f"multipart/form-data; boundary={b}"})
        if code != 200:
            raise RuntimeError(f"no se pudo crear el pedido: {code} {data}")
        return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8788")
    ap.add_argument("--token", default="token-de-prueba")
    args = ap.parse_args()
    c = Cliente(args.api, args.token)

    print("\n0 · Filtro de presencialidad: el código del cliente libera la impresión")
    j0 = c.crear_intento()[1]
    check("el pedido nace con código de 4 dígitos", bool(j0.get("code")) and len(j0["code"]) == 4, str(j0)[:120])
    code0 = j0.get("code")

    c.agente("/api/agent/next", {"stage": "quote"})
    c.agente("/api/agent/quote", {"folio": j0["folio"], "pages": [{"cov": 0.02, "chroma": 0.01}]})
    code, d = c._req(f"/api/jobs/{j0['folio']}/confirm", "POST", {})
    check("al confirmar NO se imprime: queda esperando", d.get("status") == "held", str(d))
    check("el código sigue visible para el cliente", d.get("code") == code0, str(d))

    code, d = c.agente("/api/agent/next", {"stage": "print"})
    check("sin código el agente no lo toma", (d.get("job") or {}).get("folio") != j0["folio"], str(d)[:120])

    code, d = c.agente("/api/agent/manual", {"action": "release", "code": "0000" if code0 != "0000" else "1111"})
    check("código equivocado no libera nada", code == 404, f"{code} {d}")

    code, d = c.agente("/api/agent/manual", {"action": "release", "code": code0})
    check("con su código el pedido entra a imprimir", d.get("status") == "queued", str(d))
    c.agente("/api/agent/manual", {"folio": j0["folio"], "action": "printed_here"})

    print("\n1 · Pedido con indicaciones: el mostrador lo imprime a mano")
    j1 = c.crear("Imagen de 10x10 en hoja opalina")
    check("nace esperando confirmación", j1["status"] == "review_pending", j1["status"])
    f1 = j1["folio"]
    code, d = c._req(f"/api/jobs/{f1}/confirm", "POST", {"price_terms": "variable"})
    check("acepta precio variable y espera presencia", code == 200 and d.get("status") == "review_held", str(d))
    code, d = c.agente("/api/agent/manual", {"action": "release", "code": d.get("code")})
    check("con código entra a revisión", code == 200 and d.get("status") == "review", str(d))

    code, d = c.agente("/api/agent/next", {"stage": "review"})
    check("el agente lo toma para revisión", d.get("job") and d["job"]["folio"] == f1,
          str(d)[:120])

    code, d = c.agente("/api/agent/manual", {"folio": f1, "action": "printed_here"})
    check("se cierra como impreso a mano", d.get("status") == "done", str(d)[:120])
    check("queda registrado quién lo imprimió", d.get("printed_by") == "mostrador", str(d))

    code, d = c.agente("/api/agent/next", {"stage": "print"})
    # Puede haber otros pedidos en la fila: lo que importa es que éste no vuelva.
    check("no se reimprime solo", (d.get("job") or {}).get("folio") != f1, str(d)[:120])

    print("\n2 · Pedido sin indicaciones: va directo y sale por la app")
    j2 = c.crear("", review=False)
    f2 = j2["folio"]
    check("nace en quoting", j2["status"] == "quoting", j2["status"])
    c.agente("/api/agent/next", {"stage": "quote"})
    code, d = c.agente("/api/agent/quote", {"folio": f2, "pages": [{"cov": 0.02, "chroma": 0.01}]})
    check("se cotiza", code == 200, f"{code} {d}")
    code, d = c._req(f"/api/jobs/{f2}/confirm", "POST", {})
    check("el cliente confirma y queda esperando", d.get("status") == "held", str(d))
    code, d = c.agente("/api/agent/manual", {"action": "release", "code": j2["code"]})
    check("el mostrador teclea su código y entra", d.get("status") == "queued", str(d))
    code, d = c.agente("/api/agent/next", {"stage": "print"})
    check("el agente lo toma para imprimir", d.get("job") and d["job"]["folio"] == f2, str(d)[:120])
    code, d = c.agente("/api/agent/ack", {"folio": f2, "status": "sent"})
    check("el servidor autoriza imprimir", d.get("print") is True, str(d))
    code, d = c.agente("/api/agent/ack", {"folio": f2, "status": "done", "pages_verified": 1})
    check("queda impreso", d.get("status") == "done", str(d))

    print("\n3 · Carrera: el agente va a imprimir pero el mostrador ya lo cerró")
    j3 = c.crear("", review=False)
    f3 = j3["folio"]
    c.agente("/api/agent/next", {"stage": "quote"})
    c.agente("/api/agent/quote", {"folio": f3, "pages": [{"cov": 0.02, "chroma": 0.01}]})
    code, d = c._req(f"/api/jobs/{f3}/confirm", "POST", {})
    c.agente("/api/agent/manual", {"action": "release", "code": j3["code"]})
    code, d = c.agente("/api/agent/next", {"stage": "print"})
    check("el agente lo tiene en la mano", d.get("job") and d["job"]["folio"] == f3, str(d)[:120])
    c.agente("/api/agent/manual", {"folio": f3, "action": "printed_here"})
    code, d = c.agente("/api/agent/ack", {"folio": f3, "status": "sent"})
    check("el servidor veta la impresión doble", d.get("print") is False, str(d))
    code, d = c.agente("/api/agent/ack", {"folio": f3, "status": "done", "pages_verified": 1})
    check("no reabre un pedido ya cerrado", d.get("already") is True or d.get("status") == "done", str(d))

    print("\n4 · Error real: se puede reimprimir")
    code, d = c.agente("/api/agent/manual", {"folio": f1, "action": "requeue"})
    check("un pedido cerrado no se reimprime por error", code == 409, f"{code} {d}")
    c.agente("/api/agent/manual", {"folio": f3, "action": "printed_here"})

    print(f"\n{ok} comprobaciones bien, {len(fallos)} mal")
    for f in fallos:
        print(f"  · {f}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    raise SystemExit(main())
