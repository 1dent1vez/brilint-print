#!/usr/bin/env python3
"""Prueba de los handlers reales de Pages con D1/KV locales. Nunca imprime papel."""
from __future__ import annotations

import argparse
import concurrent.futures
import unittest
from urllib.parse import urlsplit

from prueba_flujo import Cliente


class ConfirmacionEspecial(unittest.TestCase):
    cliente: Cliente

    def job(self, status: str) -> dict:
        job = self.cliente.crear("Imprimir solo una página", copias=2)
        self.assertEqual(job["status"], status)
        return job

    def api(self, job: dict, path: str = "", body: dict | None = None, status: int = 200) -> dict:
        http, data = self.cliente._req(f"/api/jobs/{job['folio']}{path}", "POST" if body is not None else "GET", body)
        self.assertEqual(http, status, data)
        return data

    def agent(self, path: str, expected_http: int = 200, **body) -> dict:
        http, data = self.cliente.agente(f"/api/agent/{path}", body)
        self.assertEqual(http, expected_http, data)
        return data

    def test_codigo_y_total_medido_sin_segunda_confirmacion(self):
        job = self.job("review_pending")
        folio = job["folio"]
        self.assertIsNone(job.get("code"))
        self.assertIsNone(self.api(job)["total"])
        self.assertIsNone(self.agent("next", stage="review")["job"])
        self.agent("release", 409, folio=folio)
        self.agent("manual", 409, action="release", folio=folio)
        self.api(job, "/confirm", {}, status=400)
        self.api(job, "/tap", {"tag": "AA:BB:CC:DD:EE:FF"}, status=409)

        accepted = self.api(job, "/confirm", {"price_terms": "variable"})
        self.assertEqual(accepted["status"], "review_held")
        self.assertRegex(accepted["code"], r"^\d{4}$")
        self.assertIsNone(self.agent("next", stage="review")["job"])
        self.agent("manual", 409, action="release", folio=folio)
        self.api(job, "/tap", {"tag": "00:11:22:33:44:55"}, status=403)

        released = self.agent("manual", action="release", code=accepted["code"])
        self.assertEqual(released["status"], "review")
        self.agent("release", 409, folio=folio)
        self.assertTrue(self.agent("manual", action="release", code=accepted["code"])["already"])
        self.assertEqual(self.agent("next", stage="review")["job"]["folio"], folio)
        self.agent("release", 409, folio=folio)
        self.assertTrue(self.agent("ack", folio=folio, status="prepared")["review_ready"])
        self.assertIsNone(self.agent("next", stage="print")["job"])
        self.assertEqual(self.agent("release", folio=folio)["status"], "quoting")
        repeated_ack = self.agent("ack", folio=folio, status="prepared")
        self.assertTrue(repeated_ack["already"])
        self.assertEqual(repeated_ack["status"], "quoting")
        self.assertEqual(self.agent("next", stage="quote")["job"]["folio"], folio)
        # El ajuste puede cambiar la cantidad de páginas declaradas (1 → 4).
        measurement = [{"cov": 0.02, "chroma": 0}] * 4
        final = self.agent("quote", folio=folio, pages=measurement)
        self.assertEqual((final["status"], final["total"]), ("queued", 12))
        self.assertTrue(self.agent("quote", folio=folio, pages=measurement)["already"])
        public = self.api(job)
        self.assertEqual((public["status"], public["pages"], public["total"], public["quote"]["copies"]), ("queued", 4, 12, 2))
        self.assertEqual(self.agent("next", stage="print")["job"]["folio"], folio)
        self.assertTrue(self.agent("ack", folio=folio, status="sent")["print"])
        self.agent("ack", folio=folio, status="done", pages_verified=4)
        self.assertEqual((self.api(job)["status"], self.api(job)["total"]), ("done", 12))
        self.assertIsNone(self.agent("next", stage="print")["job"])

    def test_nfc_y_codigo_concurrentes_no_duplican_ni_reabren(self):
        job = self.job("review_pending")
        folio = job["folio"]
        accepted = self.api(job, "/confirm", {"price_terms": "variable"})
        with concurrent.futures.ThreadPoolExecutor(2) as workers:
            tap = workers.submit(self.api, job, "/tap", {"tag": "AA:BB:CC:DD:EE:FF"})
            code = workers.submit(self.agent, "manual", action="release", code=accepted["code"])
            results = [tap.result(), code.result()]
        self.assertEqual([r.get("already", False) for r in sorted(results, key=lambda r: bool(r.get("already")))], [False, True])
        self.assertEqual(self.agent("next", stage="review")["job"]["folio"], folio)
        self.assertIsNone(self.agent("next", stage="review")["job"])
        self.agent("ack", folio=folio, status="prepared")
        self.agent("release", folio=folio)
        self.agent("next", stage="quote")
        self.agent("manual", action="printed_here", folio=folio)
        result = self.agent("quote", 409, folio=folio, pages=[{"cov": 0.4, "chroma": 0}])
        self.assertIn("done", result["error"])
        self.assertEqual(self.api(job)["status"], "done")
        self.assertIsNone(self.agent("next", stage="print")["job"])

    def test_error_de_preparacion_no_permite_imprimir_sin_total(self):
        job = self.job("review_pending")
        folio = job["folio"]
        self.api(job, "/confirm", {"price_terms": "variable"})
        self.assertEqual(self.api(job, "/tap", {"tag": "AA:BB:CC:DD:EE:FF"})["status"], "review")
        self.agent("next", stage="review")
        self.agent("ack", folio=folio, status="error", error="No se pudo preparar")
        self.assertEqual(self.api(job)["status"], "error")
        self.agent("manual", 409, folio=folio, action="requeue")
        self.assertIsNone(self.agent("next", stage="print")["job"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8788")
    parser.add_argument("--token", default="token-de-prueba")
    args = parser.parse_args()
    if urlsplit(args.api).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("La prueba solo se permite contra Pages local.")
    ConfirmacionEspecial.cliente = Cliente(args.api, args.token)
    unittest.main(argv=[__file__], verbosity=2)
