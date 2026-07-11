"""Runs the decoder JSON evidence runner (inside the satnogs-decoder container).

Windows are always bounded — unbounded SatNOGS DB queries time out (spec).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta


def window_for(obs: dict, meta: dict | None) -> tuple[str, str]:
    if meta and meta.get("start") and meta.get("end"):
        return meta["start"], meta["end"]
    ts = datetime.fromisoformat(str(obs["timestamp"]).replace("Z", "+00:00"))
    return ((ts - timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
            (ts + timedelta(hours=12)).isoformat().replace("+00:00", "Z"))


def params_for(norad: int, start: str, end: str, module: str | None,
               infer: bool) -> dict:
    return {"norad": norad, "start": start, "end": end,
            "module": module, "infer": infer}


def run_decode(settings, obs_id: int, *, norad: int, start: str, end: str,
               module: str | None = None, ksy_path: str | None = None,
               infer: bool = False) -> tuple[dict, str | None]:
    argv = [*settings.decoder_cmd, "--norad", str(norad), "--start", start,
            "--end", end, "--obs-id", str(obs_id)]
    if module:
        argv += ["--module", module]
    if ksy_path:
        argv += ["--ksy", ksy_path]
    if infer:
        argv += ["--infer"]
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=settings.job_timeout_s)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise RuntimeError(f"decoder runner exit {proc.returncode}: {tail}")
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    try:
        result = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"decoder runner produced no JSON: {proc.stdout[-300:]}") from exc
    return result, result.get("engine_version")
