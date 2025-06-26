from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Voice Agent API is running."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("WebSocket connection established.")
    await websocket.close()
