import os
from dotenv import load_dotenv

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
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)


app.mount("/templates", StaticFiles(directory="templates"), name="templates")
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

os.makedirs("uploads/logos", exist_ok=True)


@app.get("/api/status")
async def status():
    return {"status": "API is running"}


@app.get("/", name="root")
async def root(request: Request, current_user = Depends(get_current_user_web)):
    if not current_user:
        return RedirectResponse(url=request.url_for('login_page'))
    return RedirectResponse(url=request.url_for('dashboard_page'))
    return jinja_templates.TemplateResponse("index.html", {"request": request})



app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(main.api_router, prefix="/v1")
