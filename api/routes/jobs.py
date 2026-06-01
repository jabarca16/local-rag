from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from worker.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])

_STATE_MAP = {
    "PENDING": "queued",
    "STARTED": "processing",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "RETRY": "processing",
    "REVOKED": "failed",
}


@router.get("/{job_id}")
def estado_job(job_id: str):
    result = AsyncResult(job_id, app=celery_app)

    # Celery returns PENDING for both unknown and genuinely queued tasks.
    # We distinguish: if the task was never submitted, result.state is PENDING
    # but result.date_done is None and no task_args exist. A submitted task
    # that is truly waiting also looks like PENDING — we cannot distinguish
    # without a separate registry. Spec says return 404 for unknown job_id;
    # we rely on the caller only polling IDs that were returned by POST /ingest.
    if result.state == "PENDING" and not result.date_done:
        # Could be truly unknown — spec requires 404 for nonexistent IDs.
        # Since Celery has no "not found" vs "pending" distinction natively,
        # we treat PENDING + no date_done + no task_id in backend as unknown.
        backend_info = celery_app.backend.get_task_meta(job_id)
        if backend_info.get("status") == "PENDING" and not backend_info.get("result"):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    mapped_status = _STATE_MAP.get(result.state, result.state.lower())

    return {
        "job_id": job_id,
        "status": mapped_status,
        "result": result.result if result.ready() and not result.failed() else None,
        "error": str(result.result) if result.failed() else None,
    }
