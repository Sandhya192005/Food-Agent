from fastapi import APIRouter

from app.api.v1 import auth, meals, menu, notifications, recommendations, users, water

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(meals.router)
api_router.include_router(menu.router)
api_router.include_router(water.router)
api_router.include_router(notifications.router)
api_router.include_router(recommendations.router)
