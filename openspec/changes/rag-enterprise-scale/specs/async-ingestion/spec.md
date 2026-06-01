# Async Ingestion Specification

## Purpose

Defines the Celery + Redis background task pipeline for file and crawl ingestion. Ingest endpoints MUST return immediately with a job reference; the actual embed+index work happens in a background worker process.

## Requirements

### Requirement: Immediate Job Dispatch on Ingest

`POST /ingest/file` and `POST /ingest/crawl/download` MUST return HTTP 202 with `{"job_id": "<uuid>", "status": "queued"}` within 200 ms. The endpoints SHALL NOT block on embedding or indexing.

#### Scenario: File ingest returns job_id immediately

- GIVEN the API and Celery worker are running
- WHEN `POST /ingest/file` is called with a valid file upload
- THEN the response is HTTP 202 with `{"job_id": "<uuid>", "status": "queued"}`
- AND the response is received in under 200 ms

#### Scenario: Crawl ingest returns job_id immediately

- GIVEN the API and Celery worker are running
- WHEN `POST /ingest/crawl/download` is called with a valid URL list
- THEN the response is HTTP 202 with `{"job_id": "<uuid>", "status": "queued"}`

#### Scenario: Worker unavailable at dispatch time

- GIVEN the Celery worker container is down
- WHEN `POST /ingest/file` is called
- THEN the response is still HTTP 202 with `{"job_id": "<uuid>", "status": "queued"}`
- AND the task remains in the Redis queue until a worker picks it up

---

### Requirement: Job Status Polling

The system MUST expose `GET /jobs/{job_id}` returning `{job_id, status, created_at, updated_at, result?, error?}`. Valid status values are: `queued`, `processing`, `completed`, `failed`. The endpoint SHALL be accessible without modifying existing routes.

#### Scenario: Poll a queued job

- GIVEN a job was dispatched and no worker has started it yet
- WHEN `GET /jobs/{job_id}` is called
- THEN the response is `{"job_id": "...", "status": "queued", "created_at": "...", "updated_at": "..."}`

#### Scenario: Poll a completed job

- GIVEN a worker successfully embedded and indexed the file
- WHEN `GET /jobs/{job_id}` is called
- THEN `status` is `"completed"` and `result` contains indexing summary metadata

#### Scenario: Poll a failed job

- GIVEN the worker raised an exception during indexing
- WHEN `GET /jobs/{job_id}` is called
- THEN `status` is `"failed"` and `error` contains the exception message

#### Scenario: Poll an unknown job_id

- GIVEN `job_id` does not exist in the result backend
- WHEN `GET /jobs/{job_id}` is called
- THEN the response is HTTP 404

---

### Requirement: Worker Process Isolation

The Celery worker MUST run as a separate Docker service with `--concurrency=1`. One model instance SHALL be loaded per worker process. The worker MUST read uploaded files from a shared Docker volume, not from API memory.

#### Scenario: Worker processes a file ingest task

- GIVEN a file was written to the shared `uploads/` volume by the API
- WHEN the Celery worker picks up the task
- THEN the worker reads the file from the volume, embeds it, indexes it into Qdrant
- AND updates the job status to `completed` in Redis

#### Scenario: Shared volume missing

- GIVEN the `uploads/` volume is not mounted on the worker container
- WHEN the worker attempts to read the uploaded file
- THEN the task fails with status `"failed"` and the error is logged
- AND the API and Qdrant services remain unaffected

#### Scenario: Concurrent tasks are serialized

- GIVEN two ingest tasks arrive simultaneously
- WHEN the worker (concurrency=1) processes them
- THEN the tasks are executed sequentially, not in parallel
- AND both eventually reach `completed` status

---

### Requirement: Infrastructure — Celery + Redis

Redis MUST run as a self-hosted Docker service (`redis:7-alpine`). Celery MUST use Redis as both the broker and the result backend. No external queue or cache service SHALL be used.

#### Scenario: Docker Compose starts all four services

- GIVEN a valid `docker-compose.yml` with `api`, `worker`, `qdrant`, `redis` services
- WHEN `docker compose up` is executed
- THEN all four services are healthy and the API accepts requests
- AND the worker connects to Redis and begins polling the queue
