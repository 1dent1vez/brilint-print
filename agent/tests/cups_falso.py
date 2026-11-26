#!/usr/bin/env python3
"""CUPS de mentira para las pruebas del agente.

Se copia con los nombres lp, lpstat, cancel, cupsenable y cupsaccept, y guarda su
estado en el archivo que apunte $CUPS_FALSO_STATE (JSON). Así se puede reproducir
un trabajo ajeno atorado, una impresora detenida o un trabajo cancelado sin papel.

Estado:
    {"enabled": true, "reason": "", "jobs": {"HP_USB-31": {"state": "pending", "ticks": 2}}}
    state: pending | held | completed | cancelled
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ["CUPS_FALSO_STATE"])
NAME = Path(sys.argv[0]).name


def load() -> dict:
    return json.loads(STATE.read_text())


def save(st: dict) -> None:
    STATE.write_text(json.dumps(st))


def printer_from(args: list[str]) -> str:
    for a in args:
        if not a.startswith("-"):
            return a
    return "HP_USB"


def main() -> int:
    args = sys.argv[1:]
    st = load()

    if NAME == "lpstat":
        if "-p" in args:
            p = printer_from(args[args.index("-p") + 1:])
            if st["enabled"]:
                print(f"printer {p} is idle.  enabled since Thu 01 Jan 2026 10:00:00 AM CST")
            else:
                print(f"printer {p} disabled since Thu 01 Jan 2026 10:00:00 AM CST - "
                      f"{st.get('reason') or 'reason unknown'}")
            return 0
        want_completed = "-W" in args and args[args.index("-W") + 1] == "completed"
        p = printer_from(args)
        changed = False
        for jid, job in list(st["jobs"].items()):
            if want_completed:
                if job["state"] in ("completed", "cancelled"):
                    print(f"{jid} identivez 414720 Thu 01 Jan 2026 10:00:00 AM CST")
                continue
            if job["state"] in ("completed", "cancelled"):
                continue
            if job["state"] == "pending" and job.get("ticks", 0) > 0:
                job["ticks"] -= 1
                changed = True
                if job["ticks"] <= 0:
                    job["state"] = "completed"
                    continue
            if job["state"] == "held":
                print(f"{jid} identivez 1024 Thu 01 Jan 2026 10:00:00 AM CST")
                if "-l" in args:
                    print("\tAlerts: job-hold-until-specified")
                    print(f"\tqueued for {printer_from(args[args.index('-o') + 1:])}")
                continue
            print(f"{jid} identivez 414720 Thu 01 Jan 2026 10:00:00 AM CST")
        if changed:
            save(st)
        return 0

    if NAME == "lp":
        if "-i" in args and "-H" in args:      # lp -i HP_USB-31 -H resume
            jid = args[args.index("-i") + 1]
            if jid in st["jobs"] and st["jobs"][jid]["state"] == "held":
                st["jobs"][jid]["state"] = "pending"
                st["jobs"][jid]["ticks"] = 1
                save(st)
            return 0
        p = printer_from(args[args.index("-d") + 1:]) if "-d" in args else "HP_USB"
        if not st["enabled"] and st.get("reject") is True:
            print("lp: The printer or class does not exist.", file=sys.stderr)
            return 1
        n = 1
        for i, a in enumerate(args):
            if a == "-n":
                n = int(args[i + 1])
        num = 1 + max([int(j.split("-")[-1]) for j in st["jobs"]] or [0])
        jid = f"{p}-{num}"
        st["jobs"][jid] = {"state": "pending", "ticks": int(os.environ.get("CUPS_FALSO_TICKS", "2"))}
        st.setdefault("sends", []).append({"id": jid, "copies": n})
        save(st)
        print(f"request id is {jid} (1 file(s))")
        return 0

    if NAME == "cancel":
        jid = args[0] if args else ""
        if jid in st["jobs"]:
            st["jobs"][jid]["state"] = "cancelled"
            save(st)
            return 0
        return 1

    if NAME in ("cupsenable", "cupsaccept"):
        st["enabled"] = True
        st.pop("reason", None)
        save(st)
        return 0

    print(f"{NAME}: no implementado", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
