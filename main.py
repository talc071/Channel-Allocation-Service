from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.clock import Clock
from core.exceptions import DomainError
from modules.responses import ErrorResponse
from repositories.allocation_repository import AllocationRepository
from routes.allocations import router as allocations_router
from services.allocation_service import AllocationService


def create_app(service: AllocationService | None = None) -> FastAPI:
    """Build the FastAPI app. Pass a custom service in tests to inject a clock or repo."""
    app = FastAPI(title="Channel Allocation Service", version="0.1.0")

    if service is None:
        service = AllocationService(AllocationRepository(), Clock())
    app.state.allocation_service = service

    app.include_router(allocations_router)

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        body = ErrorResponse(error_code=exc.error_code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
