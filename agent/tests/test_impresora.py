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
from pathlib import Path

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
