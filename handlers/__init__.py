from .start import router as start_router
from .orders import router as orders_router
from .reviews import router as reviews_router
from .admin import router as admin_router
from .funnels import router as funnels_router

all_routers = [
    start_router,
    orders_router,
    reviews_router,
    admin_router,
    funnels_router,
]