from fastapi import APIRouter

from app.api.v1 import analyses, auth, jobs, resumes, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(resumes.router)
api_router.include_router(jobs.router)
api_router.include_router(analyses.router)
