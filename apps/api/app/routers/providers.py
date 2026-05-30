from fastapi import APIRouter

from app.services.providers import ProviderReadiness, get_provider_readiness

router = APIRouter()


@router.get("/readiness")
def provider_readiness() -> ProviderReadiness:
    return get_provider_readiness()
