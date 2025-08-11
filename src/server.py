from fastapi import FastAPI

from model import MessagePayload
import logging
from fastapi import Body

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s: %(message)s"
)

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Voice Agent API is running."}

@app.post("/message")
async def voice_agent(payload: MessagePayload = Body(...)):
    return {"received": payload}
