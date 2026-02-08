import os
from dotenv import load_dotenv

from db.schemas.user import NotifyMe

load_dotenv('.env')


from fastapi.exceptions import RequestValidationError
from utils.app_helper import validation_exception_handler
from utils.app_logger import createLogger
from fastapi import FastAPI, Request, Depends
from fastapi.routing import APIRoute
from api import main
from utils.templates import jinja_templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from utils.dependencies import get_current_user_web




logger = createLogger("app")

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0] if route.tags else ['abcd']}-{route.name}"


app = FastAPI(
    title="Squadra",
    generate_unique_id_function=custom_generate_unique_id
)


app.mount("/templates", StaticFiles(directory="templates"), name="templates")
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

os.makedirs("uploads/logos", exist_ok=True)
os.makedirs("uploads/avatars", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/api/status")
async def status():
    return {"status": "API is running"}


@app.get("/", name="root")
async def root(request: Request, current_user = Depends(get_current_user_web)):
    # if not current_user:
    #     return RedirectResponse(url=request.url_for('login_page'))
    # return RedirectResponse(url=request.url_for('dashboard_page'))
    return jinja_templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/notify-me", name="notify_me")
async def notify_me(request: NotifyMe):
    pass
    return jinja_templates.TemplateResponse("index.html", {"request": request})



app.add_exception_handler(RequestValidationError, validation_exception_handler)

from api import web_api

app.include_router(main.api_router, prefix="/v1")
app.include_router(web_api.router) # Root level for .well-known and /join
