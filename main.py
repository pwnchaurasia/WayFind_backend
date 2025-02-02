from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError

from utils.app_helper import validation_exception_handler

load_dotenv('.env')
from utils.app_logger import createLogger

from fastapi import FastAPI
from fastapi.routing import APIRoute
from api import main


logger = createLogger("app")

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)


app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(main.api_router, prefix="/v1")
