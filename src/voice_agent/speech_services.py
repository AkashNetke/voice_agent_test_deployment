import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

class SpeechServices:
    def __init__(self):
        """Initialize speech config with Azure credentials."""
        speech_key = os.environ.get('AZURE_SPEECH_KEY')
        speech_region = os.environ.get('AZURE_SPEECH_REGION')

        logger.info(f"🔑 Initializing Azure Speech Services...")
        logger.info(f"🌍 Region: {speech_region}")
        logger.info(f"🔐 API Key: {'***' + (speech_key[-4:] if speech_key else 'None')}")

        if not speech_key or not speech_region:
            logger.error("❌ Azure Speech credentials not found!")
            raise ValueError("Azure Speech credentials not found. Please check your .env file.")

        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        self.speech_config.speech_recognition_language = "en-US"
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        logger.info("✅ Azure Speech Services initialized successfully")
