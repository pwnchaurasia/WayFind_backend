from dotenv import load_dotenv
load_dotenv('.env')


from fastapi.exceptions import RequestValidationError
from utils.app_helper import validation_exception_handler
from utils.app_logger import createLogger
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from api import main
from fastapi.templating import Jinja2Templates



logger = createLogger("app")

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0] if route.tags else ['abcd']}-{route.name}"


app = FastAPI(
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)


jinja_templates = Jinja2Templates(directory="templates")



@app.get("/", name="root")
async def root(request: Request):
    return jinja_templates.TemplateResponse("index.html", {"request": request})




app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(main.api_router, prefix="/v1")
