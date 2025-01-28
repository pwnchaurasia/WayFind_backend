from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.routing import APIRoute

from api import main
# load .env file
load_dotenv()


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)



app.include_router(main.api_router, prefix="/v1")
