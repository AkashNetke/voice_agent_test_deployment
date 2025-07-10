import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SpeechServices:
    def __init__(self):
        """Initialize speech config with Azure credentials."""
        speech_key = os.environ.get('AZURE_SPEECH_KEY')
        speech_region = os.environ.get('AZURE_SPEECH_REGION')

        if not speech_key or not speech_region:
            raise ValueError("Azure Speech credentials not found. Please check your .env file.")

        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=speech_region
        )
        self.speech_config.speech_recognition_language = "en-US"
        self.speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"  # Pick your preferred voice
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        self._init_stream()

    def _init_stream(self):
        self.stream = speechsdk.audio.PushAudioInputStream()
        self.audio_config = speechsdk.AudioConfig(stream=self.stream)
        self.recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=self.audio_config
        )

    def write_audio_bytes(self, audio_bytes: bytes):
        self.stream.write(audio_bytes)

    def transcribe(self):
        self.stream.close()
        
        result = self.recognizer.recognize_once_async().get()
        self._init_stream()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return None
        elif result.reason == speechsdk.ResultReason.Canceled:
            return f"Error: {result.cancellation_details.reason}"

    def synthesize_text_to_speech(self, text: str) -> bytes:
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
        result = speech_synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_stream = speechsdk.AudioDataStream(result)
            audio_bytes = bytearray()
            buffer = bytes(4096)
            while True:
                bytes_read = audio_stream.read_data(buffer)
                if bytes_read == 0:
                    break
                audio_bytes.extend(buffer[:bytes_read])

            return bytes(audio_bytes)
        
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            return f"Speech synthesis canceled: {cancellation_details.reason}"

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

    def text_to_speech(self, text):
        """
        Convert text to speech and play it through default speakers.
        Args:
            text (str): The text to convert to speech
        """
        # Create a speech synthesizer
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)

        # Synthesize the text
        result = speech_synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return "Speech synthesis completed successfully."
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            return f"Speech synthesis canceled: {cancellation_details.reason}"
