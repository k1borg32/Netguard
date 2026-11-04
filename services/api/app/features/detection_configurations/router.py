from fastapi import APIRouter

from .activate_configuration.controller import router as activate_configuration_router
from .create_configuration.controller import router as create_configuration_router
from .get_configuration.controller import router as get_configuration_router
from .list_configurations.controller import router as list_configurations_router
from .update_configuration.controller import router as update_configuration_router

router = APIRouter(tags=["detection configurations"])
router.include_router(list_configurations_router, prefix="/api/v1/detection-configurations")
router.include_router(get_configuration_router, prefix="/api/v1/detection-configurations")
router.include_router(create_configuration_router, prefix="/api/v1/detection-configurations")
router.include_router(update_configuration_router, prefix="/api/v1/detection-configurations")
router.include_router(activate_configuration_router, prefix="/api/v1/detection-configurations")
