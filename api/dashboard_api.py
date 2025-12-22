from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.db_conn import get_db
from utils import app_logger
from utils.dependencies import get_current_user_web
from utils.templates import jinja_templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = app_logger.createLogger("app")

@router.get("/", name="dashboard_page")
async def dashboard(
        request: Request,
        current_user = Depends(get_current_user_web),
        db: Session = Depends(get_db),
):
    """Render dashboard page"""
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))

    return jinja_templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "dashboard"  # Pass active page
        }
    )
