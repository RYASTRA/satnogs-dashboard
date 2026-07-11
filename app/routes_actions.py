from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from . import db as ddb
from .adapters import decoder, identity
from .routes_analysis import _panel_response, load_obs

router = APIRouter()


def _respond(request: Request, obs_id: int, panel: str):
    if request.headers.get("HX-Request"):
        return _panel_response(request, obs_id, panel)
    return RedirectResponse(f"/observations/{obs_id}/analysis", status_code=303)


@router.post("/observations/{obs_id}/actions/identify")
def action_identify(request: Request, obs_id: int, intdes: str = Form(""),
                    catalog: str = Form(""), rerun: str = Form("")):
    s = request.app.state.settings
    params = identity.params_for(intdes or None, catalog or None)
    request.app.state.jobs.submit(
        "identity", obs_id, params,
        lambda: identity.run_identify(s, obs_id, intdes=intdes or None,
                                      catalog=catalog or None),
        rerun=rerun == "1")
    return _respond(request, obs_id, "identity")


@router.post("/observations/{obs_id}/actions/decode_check")
def action_decode(request: Request, obs_id: int, rerun: str = Form(""),
                  infer: str = Form("")):
    s = request.app.state.settings
    conn = request.app.state.db
    obs = load_obs(request, obs_id)
    if obs is None:
        return _respond(request, obs_id, "decode")
    cached_meta = ddb.get_result(conn, "network_meta", obs_id, {"v": 1})
    meta = cached_meta["result"] if cached_meta and cached_meta.get("result") else None
    start, end = decoder.window_for(obs, meta)
    entry = ddb.registry_lookup(conn, obs["norad"]) if obs.get("norad") is not None else None
    module = entry["module"] if entry else None
    ksy_path = entry.get("ksy_path") if entry else None
    params = decoder.params_for(obs["norad"], start, end, module, infer == "1")
    request.app.state.jobs.submit(
        "decoder", obs_id, params,
        lambda: decoder.run_decode(s, obs_id, norad=obs["norad"], start=start,
                                   end=end, module=module, ksy_path=ksy_path,
                                   infer=infer == "1"),
        rerun=rerun == "1")
    return _respond(request, obs_id, "decode")


@router.get("/observations/{obs_id}/artifacts/ksy")
def ksy_artifact(request: Request, obs_id: int):
    row = ddb.latest_results(request.app.state.db, "decoder", obs_id)
    hints = (row or {}).get("result") or {}
    hints = hints.get("structure_hints") or {}
    if not hints.get("ksy_text"):
        return PlainTextResponse("no inferred ksy cached for this observation",
                                 status_code=404)
    return PlainTextResponse(hints["ksy_text"], headers={
        "Content-Disposition":
            f"attachment; filename=obs{obs_id}_inferred_REVIEW_ONLY.ksy"})
