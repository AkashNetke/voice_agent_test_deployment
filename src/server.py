from fastapi import FastAPI, WebSocket
from .agent.speech_services import SpeechServices
import logging
import ffmpeg
import io

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s: %(message)s"
)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Voice Agent API is running."}

@app.websocket("/audio")
async def audio_websocket(websocket: WebSocket):
    await websocket.accept()
    speechServices = SpeechServices()
    
    try:
        while True:
            # Expecting PCM audio bytes from the client for now..
            # if we need to support other compression formats, then need to add the conversion logic
            audio_bytes = await websocket.receive_bytes()
            logging.info("Received audio bytes from client.")
            if not audio_bytes:
                logging.info("No audio bytes received, closing connection!")
                await websocket.close()
                return

            logging.debug("Processing received audio bytes..")
            speechServices.write_audio_bytes(audio_bytes)

            speech_text = speechServices.transcribe()
            logging.info("Transcribed audio bytes to text as: %s", speech_text)
            if not speech_text:
                logging.warning("No speech text recognized, closing connection!")
                await websocket.close()
                return
            
            # TODO: Send speech text to LLM to get payload for TravelHands API request
            
            # For now, just responding with the same text
            response_audio_bytes = speechServices.synthesize_text_to_speech(speech_text)
            logging.info("Responding with synthesized audio bytes..")
            await websocket.send_bytes(response_audio_bytes)
    except Exception:
        logging.error("An error occurred during audio processing!", exc_info=True)
        await websocket.close()