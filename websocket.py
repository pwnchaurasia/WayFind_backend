import os
from dotenv import load_dotenv
load_dotenv('.env')


from location_sharing.connection_factory import ConnectionManagerFactory
from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from utils.app_logger import createLogger

app = FastAPI()






logger = createLogger("websocket")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv('WEBSOCKET_ALLOWED_ORIGIN')],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


use_redis = bool(os.getenv('WEB_SOCKET_CONN_USE_REDIS', False))

connection_factory = ConnectionManagerFactory(use_redis=use_redis)
manager = connection_factory.get_manager()



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, group_id="abcd"):
    await manager.connect(websocket, group_id)
    logger.debug("Connection stablisted")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
            logger.debug(f"Message was {data}")
            await manager.broadcast(f"Message from group abcd: {data}", group_id)
    except Exception as e:
        logger.error(f"Error in websocket_endpoint, Error: {e}")
    finally:
        manager.disconnect(websocket=websocket, group_id=group_id)
