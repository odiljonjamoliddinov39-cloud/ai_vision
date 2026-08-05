# API Guide

The existing API is served below `/api`; access-control endpoints remain under
`/api/v2`. Camera operations include list, health, test, activate, and removal.
All new production endpoints must use plural resource names, standard HTTP status
codes, and the response envelope `{data, meta}`. Errors use `{error_code, message,
service, camera_id, timestamp, stacktrace}`; stack traces are omitted externally
unless debug mode is explicitly enabled.

OpenAPI is available at `/docs` and `/openapi.json` when the FastAPI server runs.
