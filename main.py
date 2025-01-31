from dotenv import load_dotenv

from utils.app_logger import createLogger
from utils.conn import RabbitMQ

# load .env file , all the imports must happen after this, so that envs are access to every file
load_dotenv('.env')

from fastapi import FastAPI
from fastapi.routing import APIRoute
from api import main


rabbit = RabbitMQ()
rabbit.publish("location", "Some message")

logger = createLogger("app")

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)



app.include_router(main.api_router, prefix="/v1")
