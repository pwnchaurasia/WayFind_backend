from dotenv import load_dotenv
# load .env file , all the imports must happen after this, so that envs are access to every file
load_dotenv('.env')

from fastapi import FastAPI
from fastapi.routing import APIRoute

from api import main




def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title="wayfind",
    generate_unique_id_function=custom_generate_unique_id
)



app.include_router(main.api_router, prefix="/v1")
