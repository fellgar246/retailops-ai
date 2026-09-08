from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from retailops_api import __version__
from retailops_api.api.router import api_router
from retailops_api.core.config import Settings, get_settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests before the body reaches a handler.

    A declared length is refused outright. A request that omits the header is
    still bounded, because the ceiling is enforced again as the body streams in.
    """

    def __init__(self, app: object, *, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self._max_bytes:
                    return self._too_large()
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "content-length is not a number"}
                )
        return await call_next(request)

    def _too_large(self) -> Response:
        return JSONResponse(
            status_code=413,
            content={"detail": f"request body exceeds {self._max_bytes} bytes"},
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Interactive documentation describes every endpoint and its shapes. A
    # deployed instance does not publish it.
    serves_schema = settings.serves_api_schema

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if serves_schema else None,
        redoc_url=None,
        openapi_url="/openapi.json" if serves_schema else None,
    )

    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Dependencies resolve configuration from here, so an injected
    # configuration governs the whole application.
    app.state.settings = settings

    app.include_router(api_router)
    return app


app = create_app()
