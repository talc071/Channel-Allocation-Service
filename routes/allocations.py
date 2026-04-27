from fastapi import APIRouter, Depends, Request, status

from modules.requests import AllocateRequest, CancelRequest, FreeRequest
from modules.responses import AllocationResponse, CancelResponse, FreeResponse
from services.allocation_service import AllocationService


def get_service(request: Request) -> AllocationService:
    """Pulls the singleton AllocationService stored on the FastAPI app state."""
    return request.app.state.allocation_service


router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post("", response_model=AllocationResponse, status_code=status.HTTP_201_CREATED)
async def allocate(
    body: AllocateRequest,
    service: AllocationService = Depends(get_service),
) -> AllocationResponse:
    return await service.allocate(body)


@router.post("/free", response_model=FreeResponse)
async def free(
    body: FreeRequest,
    service: AllocationService = Depends(get_service),
) -> FreeResponse:
    return await service.free(body)


@router.post("/cancel", response_model=CancelResponse)
async def cancel(
    body: CancelRequest,
    service: AllocationService = Depends(get_service),
) -> CancelResponse:
    return await service.cancel(body)


@router.get("", response_model=list[AllocationResponse])
async def list_active(
    service: AllocationService = Depends(get_service),
) -> list[AllocationResponse]:
    return service.list_active()
