#!/usr/bin/env python3
"""
Agente de impresión · Print with Brilint
Corre en la laptop del mostrador: jala el siguiente pedido de la cola, normaliza
los archivos, los imprime en la HP y reporta el resultado.

Uso:
    python3 print_agent.py            # bucle continuo (lo normal)
    python3 print_agent.py --once     # procesa un pedido y sale
    python3 print_agent.py --dry-run  # normaliza y muestra el comando, sin imprimir
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
LOG_PATH = ROOT / "agent.log"
REVIEW_HOME = Path.home() / "Desktop" / "Impresiones"

PAPERS = {"letter": ("letter", 612, 792), "a4": ("a4", 595, 842)}


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class Agent:
    def __init__(self, cfg: dict, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.base = cfg["api_base"].rstrip("/")
        self.token = cfg["agent_token"]
        self.printer = cfg.get("printer", "HP_USB")
        self.paper_name, self.paper_w, self.paper_h = PAPERS.get(
            cfg.get("paper", "letter"), PAPERS["letter"]
        )
        self.spool = Path(cfg.get("workdir") or (ROOT / "spool"))
        self.spool.mkdir(parents=True, exist_ok=True)
        self.cover = bool(cfg.get("cover_sheet", True))
        self._last_purge = 0.0

    # -------- API -------- #
    def _req(self, path: str, method: str = "GET", body: dict | None = None,
             to_file: Path | None = None, timeout: int = 60):
        url = f"{self.base}{path}"
        data = None
        headers = {
            "x-agent-token": self.token,
            "accept": "application/json",
            # Cloudflare bloquea el User-Agent por defecto de urllib.
            "user-agent": "BrilintPrintAgent/1.0 (+https://brilint-print.pages.dev)",
        }
        if body is not None:
            data = json.dumps(body).encode()
            headers["content-type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if to_file is not None:
                to_file.parent.mkdir(parents=True, exist_ok=True)
                with to_file.open("wb") as fh:
                    shutil.copyfileobj(resp, fh)
                return to_file.stat().st_size
            return json.loads(resp.read().decode() or "{}")

    def claim(self, stage: str = "print") -> dict | None:
        return self._req("/api/agent/next", method="POST", body={"stage": stage}).get("job")

    def quote(self, folio: str, pages: list[dict]) -> dict:
        return self._req("/api/agent/quote", method="POST",
                         body={"folio": folio, "pages": pages}, timeout=120)

    def release(self, folio: str) -> dict:
        return self._req("/api/agent/release", method="POST",
                         body={"folio": folio}, timeout=60)

    def ack(self, folio: str, status: str, pages: int | None = None, error: str | None = None) -> None:
        if self.dry_run:
            log(f"  (dry-run) no se reporta {folio} como {status}")
            return
        self._req("/api/agent/ack", method="POST",
                  body={"folio": folio, "status": status,
                        "pages_verified": pages, "error": error})

    # -------- archivos -------- #
    def download(self, folio: str, f: dict, dest: Path) -> Path:
        q = urllib.parse.urlencode({"folio": folio, "i": f["index"]})
        size = self._req(f"/api/agent/file?{q}", to_file=dest, timeout=300)
        log(f"  ↓ {f['name']} ({size / 1048576:.1f} MB)")
        return dest

    def to_pdf(self, src: Path, dst: Path, mode: str) -> Path:
        if src.suffix.lower() == ".pdf":
            return self.normalize_pdf(src, dst, mode)
        return self.image_to_pdf(src, dst, mode)

    def normalize_pdf(self, src: Path, dst: Path, mode: str) -> Path:
        cmd = [
            "gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/prepress",
            "-dEmbedAllFonts=true", "-dSubsetFonts=true",
            "-dAutoRotatePages=/None", "-dFIXEDMEDIA",
            f"-sPAPERSIZE={self.paper_name}", "-dPDFFitPage",
            "-dDownsampleColorImages=true", "-dColorImageResolution=300",
            "-dDownsampleGrayImages=true", "-dGrayImageResolution=300",
            "-dPreserveAnnots=false",
            f"-sOutputFile={dst}", str(src),
        ]
        if mode == "bw":
            cmd[1:1] = ["-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray"]
        r = run(cmd)
        if r.returncode != 0 or not dst.exists():
            raise RuntimeError(f"ghostscript falló: {(r.stderr or r.stdout)[:200]}")
        return dst

    def image_to_pdf(self, src: Path, dst: Path, mode: str) -> Path:
        try:
            from PIL import Image
        except ImportError:
            # Sin PIL: que ghostscript intente leer la imagen directamente.
            cmd = ["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                   "-dFIXEDMEDIA", f"-sPAPERSIZE={self.paper_name}", "-dPDFFitPage",
                   f"-sOutputFile={dst}", str(src)]
            if run(cmd).returncode != 0:
                raise RuntimeError("no se pudo convertir la imagen")
            return dst

        img = Image.open(src)
        img = img.convert("L") if mode == "bw" else img.convert("RGB")
        # La página se arma en puntos (612x792 para carta) pero se rasteriza a 300 dpi:
        # PIL interpreta los píxeles con `resolution`, así que el lienzo va en px de 300 dpi.
        dpi = 300
        margin = 18 * dpi // 72                      # 18 pt de margen
        pw, ph = self.paper_w * dpi // 72, self.paper_h * dpi // 72
        box_w, box_h = pw - margin * 2, ph - margin * 2
        scale = min(box_w / img.width, box_h / img.height)
        new = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        img = img.resize(new, Image.LANCZOS)
        page = Image.new(img.mode, (pw, ph), 255)
        page.paste(img, ((pw - new[0]) // 2, (ph - new[1]) // 2))
        page.save(dst, "PDF", resolution=float(dpi))
        return dst

    def pages(self, pdf: Path) -> int:
        expr = f"({pdf}) (r) file runpdfbegin pdfpagecount = quit"
        r = run(["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c", expr], timeout=120)
        out = (r.stdout or "").strip().splitlines()
        for line in reversed(out):
            if line.strip().isdigit():
                return int(line.strip())
        raise RuntimeError("no se pudo contar las páginas")

    # -------- portada -------- #
    def cover_sheet(self, job: dict, dst: Path, verified: int) -> Path | None:
        ink, gray, lime, line = "#f5f5f1", "#a5a8b1", "#d4ff24", "#272a30"
        notes = (job.get("notes") or "").strip()
        esc = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        note_lines = []
        for i, chunk in enumerate([notes[i:i + 58] for i in range(0, len(notes), 58)][:4]):
            note_lines.append(
                f'<text x="48" y="{300 + i * 21}" font-family="Manrope" font-size="13" fill="{ink}">{esc(chunk)}</text>'
            )
        quoted = job.get("pages", 0)
        warning = ""
        if verified and quoted and verified != quoted:
            warning = (f'<text x="48" y="560" font-family="Manrope" font-size="13" fill="#ff8f85">'
                       f'Cobrar según páginas reales: {verified} (cotizado {quoted})</text>')

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.paper_w}" height="{self.paper_h}" viewBox="0 0 {self.paper_w} {self.paper_h}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <rect x="0" y="0" width="{self.paper_w}" height="8" fill="{lime}"/>
  <text x="48" y="72" font-family="Manrope" font-size="11" letter-spacing="2" fill="#5b6472">PRINT WITH BRILINT</text>
  <text x="48" y="150" font-family="Bebas Neue" font-size="64" fill="#030407">{esc(job['folio'])}</text>
  <line x1="48" y1="180" x2="{self.paper_w - 48}" y2="180" stroke="{line}" stroke-width="1"/>
  <text x="48" y="212" font-family="Manrope" font-size="12" fill="#5b6472">CLIENTE</text>
  <text x="48" y="234" font-family="Manrope" font-size="15" fill="#030407">{esc(job.get('customer', ''))}</text>
  <text x="48" y="260" font-family="Manrope" font-size="13" fill="#5b6472">{esc(job.get('phone', ''))}</text>
  <text x="330" y="212" font-family="Manrope" font-size="12" fill="#5b6472">TRABAJO</text>
  <text x="330" y="234" font-family="Manrope" font-size="15" fill="#030407">{'COLOR' if job.get('mode') == 'color' else 'BLANCO Y NEGRO'}</text>
  <text x="330" y="260" font-family="Manrope" font-size="13" fill="#5b6472">{job.get('copies', 1)} copia(s) · {verified or quoted} pág.</text>
  <text x="48" y="300" font-family="Manrope" font-size="12" fill="#5b6472">NOTAS</text>
  {''.join(note_lines) or f'<text x="48" y="300" font-family="Manrope" font-size="12" fill="{gray}"></text>'}
  <line x1="48" y1="470" x2="{self.paper_w - 48}" y2="470" stroke="{line}" stroke-width="1"/>
  <text x="48" y="500" font-family="Manrope" font-size="12" fill="#5b6472">ARCHIVOS</text>
  {''.join(f'<text x="48" y="{522 + i*20}" font-family="Manrope" font-size="12" fill="#030407">{esc(f["name"])[:64]} · {f.get("pages", 1)} pág.</text>' for i, f in enumerate(job.get("files", [])[:6]))}
  {warning}
  <text x="48" y="{self.paper_h - 40}" font-family="Manrope" font-size="10" fill="#5b6472">Generado por el agente de impresión · {datetime.now():%d/%m/%Y %H:%M}</text>
</svg>"""
        svg_path = dst.with_suffix(".svg")
        svg_path.write_text(svg, encoding="utf-8")
        r = run(["inkscape", str(svg_path), "--export-type=pdf",
                 f"--export-filename={dst}"], timeout=120)
        if r.returncode != 0 or not dst.exists():
            log(f"  ! portada no generada: {(r.stderr or '')[:160]}")
            return None
        return dst

    # -------- impresión -------- #
    def print_pdf(self, pdf: Path, copies: int, pages: int) -> None:
        if self.dry_run:
            log(f"  (dry-run) lp -d {self.printer} -n {copies} {pdf.name}")
            return
        cmd = ["lp", "-d", self.printer, "-n", str(max(1, copies)),
               "-o", "media=na_letter_8.5x11in" if self.paper_name == "letter" else "media=iso_a4_210x297mm",
               str(pdf)]
        r = run(cmd, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"lp falló: {(r.stderr or r.stdout).strip()[:200]}")
        job_id = None
        for token in (r.stdout or "").split():
            if token.startswith(self.printer + "-"):
                job_id = token
                break
        log(f"  → enviado a {self.printer} [{job_id or 'sin id'}] {pages * copies} páginas")
        self.wait_spool(job_id, pages * copies)

    def wait_spool(self, job_id: str | None, sheets: int) -> None:
        deadline = time.time() + max(180, sheets * 8)
        seen = False
        while time.time() < deadline:
            time.sleep(3)
            pending = self.pending()
            if job_id and job_id in pending:
                seen = True
                continue
            if seen or not pending:
                return
        raise RuntimeError("la impresora no terminó el trabajo (revisa papel, tinta o conexión)")

    def pending(self) -> str:
        try:
            return run(["lpstat", "-o", self.printer], timeout=30).stdout or ""
        except Exception:
            return ""

    def measure(self, pdf: Path) -> list[dict]:
        """Tinta por página (fracciones 0..1) del PDF que se va a imprimir."""
        r = run(["gs", "-q", "-o", "-", "-sDEVICE=inkcov", str(pdf)], timeout=900)
        pages = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                c, m, y, k = (float(x) for x in parts[:4])
            except ValueError:
                continue
            pages.append({
                "cov": round(min(1.0, c + m + y + k), 5),
                "chroma": round(min(1.0, (c + m + y) / 3), 5),
            })
        if not pages:
            raise RuntimeError("no se pudo medir la tinta del archivo")
        return pages

    def prepare(self, job: dict) -> tuple[list[tuple[Path, int]], int]:
        """Descarga y normaliza los archivos. Reutiliza lo ya preparado."""
        folio = job["folio"]
        work = self.workdir(job)
        work.mkdir(parents=True, exist_ok=True)
        ready: list[tuple[Path, int]] = []
        verified = 0
        for f in job["files"]:
            raw = work / f"{f['index']:02d}-{Path(f['name']).name}"
            pdf = raw.with_name(f"{raw.stem}-listo-para-imprimir.pdf")
            if not pdf.exists():
                if not raw.exists():
                    self.download(folio, f, raw)
                self.to_pdf(raw, pdf, job["mode"])
            n = self.pages(pdf)
            verified += n
            if n != f.get("pages"):
                log(f"  ! {f['name']}: {n} páginas reales, {f.get('pages')} declaradas")
            ready.append((pdf, n))
        return ready, verified

    def workdir(self, job: dict) -> Path:
        """Los pedidos con nota viven en el Escritorio para que el mostrador los edite."""
        if job.get("review"):
            return REVIEW_HOME / job["folio"]
        return self.spool / job["folio"]

    def notify(self, title: str, body: str) -> None:
        try:
            run(["notify-send", "-a", "Print with Brilint", "-u", "normal",
                 title, body[:200]], timeout=15)
        except Exception:
            pass

    def purge(self) -> None:
        """Pide al servidor qué pedidos ya expiraron y borra sus carpetas locales."""
        try:
            res = self._req("/api/agent/purge", method="POST", body={}, timeout=180)
        except Exception as exc:  # noqa: BLE001
            log(f"purga falló: {exc}")
            return
        for folio in res.get("folios", [])[:200]:
            for base in (self.spool, REVIEW_HOME):
                target = base / folio
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
        if res.get("purged"):
            log(f"♻ {res['purged']} pedidos purgados · {res.get('deleted', 0)} archivos borrados")
        self.sweep()

    def sweep(self) -> None:
        """Barrido de seguridad: carpetas huérfanas de más de 24 h."""
        now = time.time()
        for base in (self.spool, REVIEW_HOME):
            if not base.exists():
                continue
            for d in base.iterdir():
                if not d.is_dir():
                    continue
                try:
                    if now - d.stat().st_mtime > 24 * 3600:
                        shutil.rmtree(d, ignore_errors=True)
                        log(f"♻ carpeta huérfana borrada: {d.name}")
                except OSError:
                    continue

    def fail(self, folio: str, exc: Exception) -> None:
        msg = str(exc)[:280]
        log(f"✗ {folio}: {msg}")
        self.ack(folio, "error", None, msg)
        if self.dry_run:
            return
        try:
            dest = self.spool / "_errores" / folio
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.spool / folio), str(dest))
        except Exception:
            pass

    # -------- ciclo -------- #
    def prepare_review(self, job: dict) -> None:
        """Etapa 0: deja el pedido listo en el Escritorio y espera al mostrador."""
        folio = job["folio"]
        log(f"Por revisar {folio} · {job.get('notes', '')[:70]!r}")
        try:
            files, verified = self.prepare(job)
            folder = self.workdir(job)
            (folder / "notas.txt").write_text(
                f"Pedido {folio}\n"
                f"Modo: {'COLOR' if job['mode'] == 'color' else 'BLANCO Y NEGRO'}\n"
                f"Copias: {job['copies']}\n"
                f"Paginas: {verified}\n\n"
                f"INDICACIONES DEL CLIENTE\n{job.get('notes', '')}\n\n"
                f"El archivo que se imprime es el *-listo-para-imprimir.pdf.\n"
                f"Si lo editas, guardalo con el mismo nombre.\n"
                f"Cuando este listo:  python3 print_agent.py --liberar {folio}\n",
                encoding="utf-8",
            )
            self.notify(f"Pedido {folio} por revisar",
                        f"{job['copies']} copia(s) · {job.get('notes', '')[:120]}")
            log(f"  → {folder}")
        except Exception as exc:  # noqa: BLE001
            self.fail(folio, exc)

    def measure_job(self, job: dict) -> None:
        """Etapa 1: medir la tinta de cada página y devolver la cotización."""
        folio = job["folio"]
        log(f"Midiendo {folio} · {len(job['files'])} archivo(s) · "
            f"{'color' if job['mode'] == 'color' else 'B/N'}")
        try:
            files, verified = self.prepare(job)
            pages: list[dict] = []
            for pdf, _n in files:
                pages.extend(self.measure(pdf))
            if len(pages) != verified:
                raise RuntimeError(f"medí {len(pages)} páginas y conté {verified}")
            res = self.quote(folio, pages)
            log(f"✓ {folio} cotizado · {len(pages)} pág. · ${res.get('total', '?')}")
        except Exception as exc:  # noqa: BLE001
            self.fail(folio, exc)

    def print_job(self, job: dict) -> None:
        """Etapa 2: imprimir un pedido ya confirmado por el cliente."""
        folio = job["folio"]
        log(f"Imprimiendo {folio} · {job['copies']}× · "
            f"{'color' if job['mode'] == 'color' else 'B/N'} · {len(job['files'])} archivo(s)")
        work = self.spool / folio
        try:
            files, verified = self.prepare(job)
            if self.cover:
                cover = self.cover_sheet(job, work / "00-portada.pdf", verified)
                if cover:
                    self.print_pdf(cover, 1, 1)
            for pdf, n in files:
                self.print_pdf(pdf, job["copies"], n)
            # La carpeta NO se borra aquí: queda una hora por si hay que reimprimir.
            # De eso se encarga purge(), que corre cada 10 minutos.
            self.ack(folio, "done", verified)
            log(f"✓ {folio} listo · {verified} páginas por juego")
        except Exception as exc:  # noqa: BLE001
            self.fail(folio, exc)

    def loop(self) -> None:
        interval = int(self.cfg.get("poll_seconds", 8))
        log(f"Agente activo · {self.base} · impresora {self.printer} · cada {interval}s")
        while True:
            try:
                if time.time() - self._last_purge > 600:
                    self._last_purge = time.time()
                    self.purge()
                handled = False
                job = self.claim("review")
                if job:
                    self.prepare_review(job)
                    handled = True
                job = self.claim("quote")
                if job:
                    self.measure_job(job)
                    handled = True
                job = self.claim("print")
                if job:
                    self.print_job(job)
                    handled = True
                if not handled:
                    time.sleep(interval)
            except urllib.error.HTTPError as exc:
                log(f"HTTP {exc.code} al consultar la cola; reintento en {interval}s")
                time.sleep(interval)
            except urllib.error.URLError as exc:
                log(f"Sin conexión ({exc.reason}); reintento en {interval}s")
                time.sleep(interval)
            except KeyboardInterrupt:
                log("Agente detenido")
                return
            except Exception as exc:  # noqa: BLE001
                log(f"Error inesperado: {exc}")
                time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="Agente de impresión de Print with Brilint")
    ap.add_argument("--once", action="store_true", help="procesa un pedido y sale")
    ap.add_argument("--dry-run", action="store_true", help="normaliza sin imprimir ni reportar")
    ap.add_argument("--liberar", metavar="FOLIO",
                    help="autoriza un pedido en revisión y lo manda a cotizar")
    ap.add_argument("--config", default=str(CONFIG_PATH))
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"Falta {cfg_path}. Copia config.example.json y llena api_base y agent_token.", file=sys.stderr)
        return 2
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("api_base", "agent_token"):
        if not cfg.get(key):
            print(f"config.json: falta '{key}'", file=sys.stderr)
            return 2

    agent = Agent(cfg, dry_run=args.dry_run)
    if args.liberar:
        res = agent.release(args.liberar.strip().upper())
        log(f"{args.liberar} liberado → {res.get('status')}")
        return 0
    if args.once:
        worked = False
        job = agent.claim("review")
        if job:
            agent.prepare_review(job)
            worked = True
        job = agent.claim("quote")
        if job:
            agent.measure_job(job)
            worked = True
        job = agent.claim("print")
        if job:
            agent.print_job(job)
            worked = True
        if not worked:
            log("No hay pedidos en cola.")
        return 0
    agent.loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
