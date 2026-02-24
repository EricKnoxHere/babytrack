"""API routes — all FastAPI routers."""

from .analysis import router as analysis_router
from .babies import router as babies_router
from .feedings import router as feedings_router
from .health import router as health_router
from .weights import router as weights_router

__all__ = ["health_router", "babies_router", "feedings_router", "analysis_router", "weights_router"]
