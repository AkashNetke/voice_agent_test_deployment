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

    # to be deleted with streamlit code
    def speech_to_text(self):
        """
        Convert speech from microphone to text.
        Returns the recognized text.
        """
        # Create a speech recognizer using the default microphone
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config)

        print("Speak into your microphone...")

        # Start speech recognition
        result = speech_recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return f"No speech could be recognized: {result.no_match_details}"
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            return f"Speech Recognition canceled: {cancellation_details.reason}"

    # to be deleted with streamlit code
    def text_to_speech_streamlit(self, text, message_type="general"):
        """
        Streamlit-compatible text-to-speech that uses file output and system playback.
        This works around Streamlit's audio output limitations.
        """
        try:
            import os
            import subprocess
            import tempfile
            import time

            # Create a temporary audio file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name

            # Create audio file output config
            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_filename)
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            # Synthesize speech to file
            result = speech_synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # Check if file was created and has content
                if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                    try:
                        # Play the audio file using system command
                        subprocess.run(['afplay', temp_filename], timeout=30, check=True)

                        # Clean up the temporary file after a short delay
                        time.sleep(0.5)
                        try:
                            os.unlink(temp_filename)
                        except:
                            pass  # Don't fail if cleanup doesn't work

                        return "Speech synthesis completed successfully."
                    except subprocess.TimeoutExpired:
                        return "Speech synthesis timeout - audio file may be too long."
                    except subprocess.CalledProcessError as e:
                        return f"Audio playback failed: {e}"
                    except Exception as e:
                        return f"Audio playback error: {e}"
                else:
                    return "Audio file creation failed - file is empty or doesn't exist."
            else:
                error_msg = "Speech synthesis failed"
                if result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    error_msg += f": {cancellation_details.reason}"
                    if cancellation_details.error_details:
                        error_msg += f" - {cancellation_details.error_details}"
                return error_msg

        except Exception as e:
            return f"Speech synthesis error: {str(e)}"
