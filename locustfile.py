from locust import HttpUser, task, between
import websockets
import asyncio


def run_async(coro):
    """Runs an async coroutine safely in a new event loop if needed"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as e:  # ✅ No running loop → create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.create_task(coro)

class WebSocketUser(HttpUser):
    wait_time = between(1, 5)
    host = "ws://127.0.0.1:8001"  # ✅ Dummy host to satisfy Locust

    @task
    def send_message(self):
       run_async(self._send_websocket_message())

    async def _send_websocket_message(self):
        uri = f"{self.host}/ws"
        async with websockets.connect(uri=uri) as websocket:
            await websocket.send("Hello, server!")
            response = await websocket.recv()
            print(f"Received: {response}")