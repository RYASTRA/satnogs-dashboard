"""JSON evidence runner around satnogs-decoder. Runs INSIDE its container
(Python 3.14 + kaitai ksc + satnogsdecoders reference package + .env token).

Inferred .ksy output is REVIEW EVIDENCE for maintainers, never a decoder.
Exit 0 whenever a JSON object was printed; failures are states.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter


def _jsonable(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)  # enums, bytes reprs, anything exotic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--norad", type=int, required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--obs-id", type=int, default=None)
    ap.add_argument("--module", default=None)
    ap.add_argument("--ksy", default=None)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--infer", action="store_true")
    ap.add_argument("--sat-id", default=None)
    args = ap.parse_args()

    out: dict = {"obs_id": args.obs_id, "norad": args.norad, "status": "failed",
                 "frame_count": 0, "frame_lengths": {}, "modal_frame_length": None,
                 "reference_module": args.module, "decode_success_count": None,
                 "decode_rate": None, "sample_decode": None, "coverage": None,
                 "crosscheck": None, "structure_hints": None,
                 "engine_version": "satnogs-decoder@container"}

    try:
        from satnogs_decoder.shared.satnogs_db import fetch_frames
    except Exception as exc:
        out["error"] = f"import failed: {exc}"
        json.dump(out, sys.stdout)
        return 0

    try:
        frames = fetch_frames(args.norad, start=args.start, end=args.end,
                              limit=args.limit)
    except RuntimeError as exc:  # verified: raised when no token configured
        out["status"] = "no_token" if "token" in str(exc).lower() else "failed"
        out["error"] = str(exc)
        json.dump(out, sys.stdout)
        return 0
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        json.dump(out, sys.stdout)
        return 0

    if args.obs_id is not None:
        scoped = [f for f in frames if f.observation_id == args.obs_id]
        if scoped:  # spec: filter by observation_id when the API supplies it
            frames = scoped

    lengths = Counter(len(f.data) for f in frames)
    out["frame_count"] = len(frames)
    out["frame_lengths"] = {str(k): v for k, v in lengths.most_common(8)}
    out["modal_frame_length"] = lengths.most_common(1)[0][0] if frames else None

    if not frames:
        out["status"] = "no_frames"
        json.dump(out, sys.stdout)
        return 0

    out["status"] = "raw_frames"

    if args.module:
        try:
            from satnogs_decoder.shared.reference import decode_reference
            decodes = [decode_reference(args.module, f.data) for f in frames]
            good = [d for d in decodes if d]
            out["status"] = "known_decoder"
            out["decode_success_count"] = len(good)
            out["decode_rate"] = round(len(good) / len(frames), 4)
            if good:
                sample = {k: _jsonable(v) for k, v in list(good[0].items())[:12]}
                out["sample_decode"] = sample
        except Exception as exc:
            out["error"] = f"reference decode failed: {type(exc).__name__}: {exc}"

    if args.module and args.ksy:
        try:
            from pathlib import Path

            from satnogs_decoder.shared.kaitai import compile_ksy
            from satnogs_decoder.validate.engine import validate
            parser_cls = compile_ksy(Path(args.ksy).read_text())
            report = validate(parser_cls, frames, ref_module=args.module)
            out["coverage"] = _jsonable(report.coverage)
            out["crosscheck"] = _jsonable(report.crosscheck)
        except Exception as exc:
            out["error"] = f"validate/crosscheck failed: {type(exc).__name__}: {exc}"

    if args.infer:
        try:
            from satnogs_decoder.infer.infer import infer_ksy, load_model
            ksy_text = infer_ksy([f.data for f in frames], load_model(),
                                 args.sat_id or str(args.norad))
            out["structure_hints"] = {
                "ksy_text": ksy_text,
                "note": ("Inferred structure — maintainer review evidence only. "
                         "Boundary F1 roughly ties a u8 baseline; NOT a decoder."),
            }
            if out["status"] == "raw_frames":
                out["status"] = "inferred_hints"
        except Exception as exc:
            out["error"] = f"inference failed: {type(exc).__name__}: {exc}"

    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
