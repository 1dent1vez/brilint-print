#!/usr/bin/env python3
"""Pruebas del agente contra una CUPS de mentira.

Cubre el caso del mostrador: un pedido con indicaciones se imprime a mano, la
cola queda con un trabajo ajeno atorado y el agente NO debe marcar en error los
pedidos que llegan después. También cubre la impresora detenida (el fallo real
del 24/11: backend ipp sin servicio → cola deshabilitada).

    cd agent && python3 -m unittest tests.test_impresora -v
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import print_agent  # noqa: E402


class ColaFalsa(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cups-falso-"))
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        falso = Path(__file__).resolve().parent / "cups_falso.py"
        for name in ("lp", "lpstat", "cancel", "cupsenable", "cupsaccept"):
            dest = self.bin / name
            shutil.copy2(falso, dest)
            dest.chmod(0o755)
        self.state = self.tmp / "state.json"
        self.state.write_text(json.dumps({"enabled": True, "reason": "", "jobs": {}}))
        self._env = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "CUPS_FALSO_STATE": str(self.state),
            "CUPS_FALSO_TICKS": "2",
        }
        self._prev = {k: os.environ.get(k) for k in self._env}
        os.environ.update(self._env)
        cfg = {
            "api_base": "http://127.0.0.1:9",
            "agent_token": "prueba",
            "printer": "HP_USB",
            "paper": "letter",
            "cover_sheet": False,
            "workdir": str(self.tmp / "spool"),
        }
        self.agent = print_agent.Agent(cfg, dry_run=False)
        print_agent.LOG_PATH = self.tmp / "agent.log"

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- helpers ---- #
    def guardar(self, st: dict) -> None:
        self.state.write_text(json.dumps(st))

    def leer(self) -> dict:
        return json.loads(self.state.read_text())

    def pdf(self, nombre: str = "x.pdf") -> Path:
        p = self.tmp / nombre
        p.write_bytes(b"%PDF-1.4\n%prueba\n")
        return p

    # ---- casos ---- #
    def test_preparacion_que_pierde_el_ack_conserva_el_pdf(self):
        root = self.tmp / "review"
        folder = root / "261127-TEST"
        folder.mkdir(parents=True)
        pdf = folder / "00-foto-listo-para-imprimir.pdf"
        pdf.write_bytes(b"prueba")
        job = {"folio": folder.name, "review": 1, "review_authorized": True, "mode": "bw", "copies": 1}
        def respond(_folio, status, *args, **kwargs):
            if status == "prepared":
                raise TimeoutError("respuesta perdida")
            return {"status": "quoting"}
        with (patch.object(print_agent, "REVIEW_HOME", root),
              patch.object(self.agent, "prepare", return_value=([(pdf, 1)], 1)),
              patch.object(self.agent, "ack", side_effect=respond) as ack,
              patch.object(self.agent, "notify")):
            self.agent.prepare_review(job)
        self.assertTrue(pdf.is_file())
        self.assertTrue((folder / "notas.txt").is_file())
        self.assertTrue(all(call.args[1] == "prepared" for call in ack.call_args_list))

    def test_no_envia_sin_respuesta_explicita_del_servidor(self):
        error = urllib.error.HTTPError(self.agent.base, 503, "indisponible", Message(), None)
        with patch.object(self.agent, "ack", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "permiso de impresión"):
                self.agent.mark_sent("261127-TEST")
        with patch.object(self.agent, "ack", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "permiso de impresión"):
                self.agent.mark_sent("261127-TEST")
        with patch.object(self.agent, "ack", return_value={"print": False}):
            self.assertFalse(self.agent.mark_sent("261127-TEST"))

    def test_cuenta_pdf_con_parentesis_suelto_en_el_nombre(self):
        source = ROOT.parent / "samples" / "documento-3-paginas.pdf"
        pdf = self.tmp / "presupuesto ) final.pdf"
        shutil.copyfile(source, pdf)
        self.assertEqual(self.agent.pages(pdf), 3)

    def test_imagen_color_no_llena_los_margenes_de_rojo(self):
        from PIL import Image

        jpg = self.tmp / "foto.jpg"
        pdf = self.tmp / "foto.pdf"
        preview = self.tmp / "prueba.png"
        Image.new("RGB", (80, 100), "blue").save(jpg)
        self.agent.image_to_pdf(jpg, pdf, "color")
        proc = print_agent.run(["gs", "-q", "-sDEVICE=png16m", "-r24", "-o", str(preview), str(pdf)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with Image.open(preview) as page:
            self.assertEqual(page.getpixel((2, 2)), (255, 255, 255))

    def test_trabajo_ajeno_atorado_no_falla_al_siguiente(self):
        """El error encadenado: un trabajo de la impresión a mano se queda en la
        cola y antes hacía fallar todos los pedidos que llegaban después."""
        self.guardar({"enabled": True, "reason": "",
                      "jobs": {"HP_USB-31": {"state": "pending", "ticks": 9999}}})
        job_id = self.agent.print_pdf(self.pdf(), 1, 1)
        self.assertEqual(job_id, "HP_USB-32")
        t0 = time.time()
        self.agent.wait_spool(job_id, 1)          # no debe lanzar
        self.assertLess(time.time() - t0, 30)
        cola = self.leer()["jobs"]
        self.assertEqual(cola["HP_USB-31"]["state"], "pending")  # el ajeno sigue ahí

    def test_impresora_detenida_falla_rapido_con_motivo(self):
        os.environ["CUPS_FALSO_TICKS"] = "9999"   # el trabajo se queda atorado
        self.guardar({"enabled": False, "reason": "cups-ipp-missing-job-state",
                      "jobs": {}, "reject": False})
        job_id = self.agent.print_pdf(self.pdf(), 1, 1)
        t0 = time.time()
        with self.assertRaises(RuntimeError) as ctx:
            self.agent.wait_spool(job_id, 1)
        self.assertIn("se detuvo", str(ctx.exception))
        self.assertIn("cups-ipp-missing-job-state", str(ctx.exception))
        self.assertLess(time.time() - t0, 20)     # no espera los 4 minutos

    def test_preflight_reactiva_la_cola(self):
        self.guardar({"enabled": False, "reason": "paused", "jobs": {}})
        self.agent.preflight()
        self.assertTrue(self.leer()["enabled"])

    def test_preflight_reporta_si_no_aguanta(self):
        self.guardar({"enabled": False, "reason": "media-empty", "jobs": {}})
        # cupsenable no levanta la cola (papel agotado): se simula no-op
        real_run = print_agent.run
        noop = lambda cmd, timeout=600: print_agent.subprocess.CompletedProcess(cmd, 0, "", "")  # noqa: E731
        print_agent.run = lambda cmd, timeout=600: noop(cmd) \
            if cmd[0] in ("cupsenable", "cupsaccept") else real_run(cmd, timeout=timeout)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.agent.preflight()
            self.assertIn("media-empty", str(ctx.exception))
        finally:
            print_agent.run = real_run

    def test_trabajo_que_desaparece_avisa(self):
        self.guardar({"enabled": True, "jobs": {}})
        job_id = self.agent.print_pdf(self.pdf(), 1, 1)
        # el trabajo se esfuma de la cola y del histórico
        st = self.leer()
        st["jobs"].pop(job_id)
        self.guardar(st)
        with self.assertRaises(RuntimeError) as ctx:
            self.agent.wait_spool(job_id, 1)
        self.assertIn("canceló", str(ctx.exception))

    def test_trabajo_en_pausa_se_reanuda(self):
        self.guardar({"enabled": True, "jobs": {}})
        job_id = self.agent.print_pdf(self.pdf(), 1, 1)
        st = self.leer()
        st["jobs"][job_id] = {"state": "held", "ticks": 0}
        self.guardar(st)
        self.agent.wait_spool(job_id, 1)
        self.assertNotEqual(self.leer()["jobs"][job_id]["state"], "held")

    def test_sin_id_no_espera_eterno(self):
        t0 = time.time()
        self.agent.wait_spool(None, 1)
        self.assertLess(time.time() - t0, 10)

    def test_liberar_impresora_cancela_lo_atorado(self):
        self.guardar({"enabled": False, "reason": "paused",
                      "jobs": {"HP_USB-31": {"state": "pending", "ticks": 0}}})
        res = self.agent.liberate_printer()
        self.assertEqual(res["cancelled"], ["HP_USB-31"])
        self.assertTrue(res["state"]["enabled"])
        self.assertEqual(res["state"]["jobs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
