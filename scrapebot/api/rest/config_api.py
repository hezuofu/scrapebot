"""Configuration management REST API — full CRUD for all config sections."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

config_router = APIRouter()

_store: Any = None


def set_config_store(store: Any) -> None:
    global _store
    _store = store


def _require_store() -> Any:
    if _store is None:
        raise HTTPException(status_code=503, detail="Config store not initialized")
    return _store


# ── Task Templates ────────────────────────────────────────────

@config_router.get("/tasks")
async def get_task_config() -> dict[str, Any]:
    return _require_store().get_task_config()


@config_router.get("/tasks/{name}")
async def get_task_template(name: str) -> dict[str, Any]:
    store = _require_store()
    tmpl = store.get_task_template(name)
    if tmpl is None:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return tmpl


@config_router.put("/tasks/{name}")
async def save_task_template(name: str, data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.save_task_template(name, data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save template")
    return {"status": "ok", "name": name}


@config_router.delete("/tasks/{name}")
async def delete_task_template(name: str) -> dict[str, Any]:
    store = _require_store()
    ok = await store.delete_task_template(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return {"status": "ok", "name": name, "deleted": True}


# ── Proxy Config ──────────────────────────────────────────────

@config_router.get("/proxy")
async def get_proxy_config() -> dict[str, Any]:
    return _require_store().get_proxy_config()


@config_router.put("/proxy")
async def update_proxy_config(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.update_proxy_config(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update proxy config")
    return {"status": "ok"}


@config_router.post("/proxy/servers/{pool_name}")
async def add_proxy_server(pool_name: str, server: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.add_proxy_server(pool_name, server)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add proxy server")
    return {"status": "ok", "pool": pool_name}


@config_router.delete("/proxy/servers/{pool_name}")
async def remove_proxy_server(
    pool_name: str,
    host: str = Query(...),
    port: int = Query(...),
) -> dict[str, Any]:
    store = _require_store()
    ok = await store.remove_proxy_server(pool_name, host, port)
    if not ok:
        raise HTTPException(status_code=404, detail="Proxy server not found")
    return {"status": "ok", "pool": pool_name, "host": host, "port": port, "deleted": True}


# ── Auth Config ───────────────────────────────────────────────

@config_router.get("/auth")
async def get_auth_config() -> dict[str, Any]:
    return _require_store().get_auth_config()


@config_router.put("/auth/sites/{domain}")
async def save_site_auth(domain: str, data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.save_site_auth(domain, data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save site auth")
    return {"status": "ok", "domain": domain}


@config_router.delete("/auth/sites/{domain}")
async def delete_site_auth(domain: str) -> dict[str, Any]:
    store = _require_store()
    ok = await store.delete_site_auth(domain)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Site auth for '{domain}' not found")
    return {"status": "ok", "domain": domain, "deleted": True}


# ── Storage Config ────────────────────────────────────────────

@config_router.get("/storage")
async def get_storage_config() -> dict[str, Any]:
    return _require_store().get_storage_config()


@config_router.put("/storage")
async def update_storage_config(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.update_storage_config(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update storage config")
    return {"status": "ok"}


# ── Site Rules ────────────────────────────────────────────────

@config_router.get("/rules/sites")
async def get_site_rules() -> dict[str, Any]:
    return _require_store().get_site_rules()


@config_router.put("/rules/sites")
async def update_site_rules(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.update_site_rules(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update site rules")
    return {"status": "ok"}


# ── Anti-Ban Rules ───────────────────────────────────────────

@config_router.get("/rules/anti-ban")
async def get_anti_ban_rules() -> dict[str, Any]:
    return _require_store().get_anti_ban_rules()


@config_router.put("/rules/anti-ban")
async def update_anti_ban_rules(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.update_anti_ban_rules(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update anti-ban rules")
    return {"status": "ok"}


# ── Parse Rules ───────────────────────────────────────────────

@config_router.get("/rules/parse")
async def get_parse_rules() -> dict[str, Any]:
    return _require_store().get_parse_rules()


@config_router.put("/rules/parse")
async def update_parse_rules(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.update_parse_rules(data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update parse rules")
    return {"status": "ok"}


# ── Import / Export ───────────────────────────────────────────

@config_router.get("/export")
async def export_all_configs() -> dict[str, Any]:
    return _require_store().export_all()


@config_router.post("/import")
async def import_all_configs(data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    results = await store.import_all(data)
    return {"status": "ok", "results": results}


# ── Scrape Jobs ───────────────────────────────────────────────

@config_router.get("/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    store = _require_store()
    jobs = store.get_jobs()
    return [{"job_id": jid, **data} for jid, data in jobs.items()]


@config_router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    store = _require_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@config_router.put("/jobs/{job_id}")
async def save_job(job_id: str, data: dict[str, Any]) -> dict[str, Any]:
    store = _require_store()
    ok = await store.save_job(job_id, data)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save job")
    return {"status": "ok", "job_id": job_id}


@config_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, Any]:
    store = _require_store()
    ok = await store.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"status": "ok", "job_id": job_id, "deleted": True}


@config_router.post("/jobs/{job_id}/expand")
async def expand_job(job_id: str) -> dict[str, Any]:
    store = _require_store()
    result = await store.run_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return result


# ── Change Log ────────────────────────────────────────────────

@config_router.get("/changelog")
async def get_change_log(limit: int = Query(default=50, le=200)) -> list[dict[str, Any]]:
    return _require_store().get_change_log(limit)


# ── Dirty Status ──────────────────────────────────────────────

@config_router.get("/status")
async def get_config_status() -> dict[str, Any]:
    store = _require_store()
    return {
        "dirty_sections": store.dirty_sections,
        "needs_save": len(store.dirty_sections) > 0,
    }


@config_router.post("/save")
async def save_all_configs() -> dict[str, Any]:
    store = _require_store()
    results = await store.save_all()
    return {"status": "ok", "results": results}
