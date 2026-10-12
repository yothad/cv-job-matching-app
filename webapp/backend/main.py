import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers.gaps import router as gaps_router
from routers.jobs import router as jobs_router
from routers.scoring import router as scoring_router
from routers.user import router as user_router

log = logging.getLogger("careerwatch")

app = FastAPI(title="CareerWatch API")


# Registered BEFORE CORSMiddleware so it sits inside it: an unhandled exception
# becomes a JSON 500 that still passes through CORS. Starlette's default 500 is
# emitted outside CORS (no Access-Control-* headers), which the browser reports
# as an opaque "Failed to fetch". The detail is generic - never leak secrets.
@app.middleware("http")
async def json_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side - please try again in a minute"},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gaps_router)
app.include_router(jobs_router)
app.include_router(scoring_router)
app.include_router(user_router)

@app.get("/health")
def health():
    return {"status": "ok"}
