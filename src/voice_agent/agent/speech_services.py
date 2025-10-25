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
        self.speech_config.speech_synthesis_voice_name = "en-US-AnaNeural"  # Pick your preferred voice
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )
        
        logger.info("✅ Azure Speech Services initialized successfully")
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

        # Set neural voice - choose one of these options:
        # Option 1: Libby UK - Young, friendly British voice ✅ ACTIVE
        self.speech_config.speech_synthesis_voice_name = "en-GB-LibbyNeural"

        # Option 2: Jane - Optimized for conversational AI agents
        # self.speech_config.speech_synthesis_voice_name = "en-US-JaneNeural"

        # Option 3: Sara - Conversational, natural female voice
        # self.speech_config.speech_synthesis_voice_name = "en-US-SaraNeural"

        # Option 4: Jenny - Professional, clear female voice
        # self.speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

        # Option 5: Davis - Warm, friendly male voice
        # self.speech_config.speech_synthesis_voice_name = "en-US-DavisNeural"

        # Option 6: Guy - Professional male voice
        # self.speech_config.speech_synthesis_voice_name = "en-US-GuyNeural"

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

    def text_to_speech(self, text, message_type="general"):
        """
        Convert text to speech with enhanced SSML markup for engaging delivery.
        Args:
            text (str): The text to convert to speech
            message_type (str): Type of message to adjust tone accordingly
                - "greeting": Warm, welcoming tone
                - "instruction": Clear, patient tone
                - "success": Excited, positive tone
                - "error": Gentle, reassuring tone
                - "confirmation": Confident tone
                - "general": Default conversational tone
        """
        # Create an audio config for the default speaker
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

        # For greetings, use simplified fast mode
        if message_type == "greeting":
            # Simple SSML for faster processing
            simple_ssml = f'''
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-GB">
                <voice name="en-GB-LibbyNeural">
                    <prosody rate="medium" pitch="+10%">
                        {text}
                    </prosody>
                </voice>
            </speak>
            '''
            ssml_text = simple_ssml.strip()
        else:
            # Create enhanced SSML with context-aware adjustments for other message types
            ssml_text = self._create_engaging_ssml(text, message_type)

        # Create a speech synthesizer with both speech config and audio config
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )

        # Synthesize the SSML text for more engaging speech
        result = speech_synthesizer.speak_ssml_async(ssml_text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return "Speech synthesis completed successfully."
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            return f"Speech synthesis canceled: {cancellation_details.reason}"

    def _create_engaging_ssml(self, text, message_type):
        """Create SSML markup for engaging speech delivery"""

        # Define tone parameters for different message types
        tone_settings = {
            "greeting": {
                "rate": "medium",
                "pitch": "+15%",
                "volume": "+20%",
                "style": "excited"
            },
            "instruction": {
                "rate": "medium",
                "pitch": "+5%",
                "volume": "+5%",
                "style": "friendly"
            },
            "success": {
                "rate": "medium",
                "pitch": "+20%",
                "volume": "+15%",
                "style": "excited"
            },
            "error": {
                "rate": "medium",
                "pitch": "-5%",
                "volume": "default",
                "style": "gentle"
            },
            "confirmation": {
                "rate": "medium",
                "pitch": "+10%",
                "volume": "+10%",
                "style": "confident"
            },
            "general": {
                "rate": "medium",
                "pitch": "+8%",
                "volume": "+5%",
                "style": "conversational"
            }
        }

        settings = tone_settings.get(message_type, tone_settings["general"])

        # Add strategic pauses and emphasis
        enhanced_text = self._add_natural_pauses_and_emphasis(text, message_type)

        # Create SSML with prosody adjustments
        ssml = f'''
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
               xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-GB">
            <voice name="en-GB-LibbyNeural">
                <mstts:express-as style="{settings['style']}">
                    <prosody rate="{settings['rate']}" pitch="{settings['pitch']}" volume="{settings['volume']}">
                        {enhanced_text}
                    </prosody>
                </mstts:express-as>
            </voice>
        </speak>
        '''

        return ssml.strip()

    def _add_natural_pauses_and_emphasis(self, text, message_type):
        """Add strategic pauses and emphasis to make speech more engaging"""

        # Add emphasis to important words/phrases
        emphasis_words = {
            "Great": "<emphasis level='strong'>Great</emphasis>",
            "Perfect": "<emphasis level='strong'>Perfect</emphasis>",
            "Excellent": "<emphasis level='strong'>Excellent</emphasis>",
            "Wonderful": "<emphasis level='strong'>Wonderful</emphasis>",
            "Success": "<emphasis level='strong'>Success</emphasis>",
            "Booking": "<emphasis level='moderate'>Booking</emphasis>",
            "journey": "<emphasis level='moderate'>journey</emphasis>",
            "volunteer": "<emphasis level='moderate'>volunteer</emphasis>",
        }

        # Apply emphasis
        for word, emphasized in emphasis_words.items():
            text = text.replace(word, emphasized)

        # Special handling for greetings - keep it energetic and fast
        if message_type == "greeting":
            # Make greeting super energetic with minimal pauses
            text = text.replace("Hello", "<emphasis level='strong'>Hello</emphasis>")
            text = text.replace("Welcome", "<emphasis level='strong'>Welcome</emphasis>")
            text = text.replace("Travel Hands", "<emphasis level='strong'>Travel Hands</emphasis>")
            text = text.replace("plan your journey", "<emphasis level='moderate'>plan your journey</emphasis>")

            # Smooth flow for greetings - minimal pauses for natural speech
            text = text.replace("!", "!")  # No pause after exclamations in greetings
            text = text.replace("?", "?<break time='250ms'/>")  # Brief pause after questions only
            text = text.replace(".", ".<break time='150ms'/>")  # Very short pause after sentences
            text = text.replace(", ", ", ")  # No pause after commas in greetings

        elif message_type == "success":
            # Special handling for success messages
            text = text.replace("successful", "<emphasis level='strong'>successful</emphasis>")
            text = text.replace("booked", "<emphasis level='strong'>booked</emphasis>")
            text = text.replace("confirmed", "<emphasis level='strong'>confirmed</emphasis>")

            # Normal pauses for success messages
            text = text.replace("!", "!<break time='300ms'/>")  # Pause after exclamations
            text = text.replace("?", "?<break time='400ms'/>")  # Pause after questions
            text = text.replace(".", ".<break time='250ms'/>")  # Short pause after sentences
            text = text.replace(", ", ",<break time='200ms'/> ")  # Brief pause after commas

        else:
            # Normal pauses for other message types
            text = text.replace("!", "!<break time='300ms'/>")  # Pause after exclamations
            text = text.replace("?", "?<break time='400ms'/>")  # Pause after questions
            text = text.replace(".", ".<break time='250ms'/>")  # Short pause after sentences
            text = text.replace(", ", ",<break time='200ms'/> ")  # Brief pause after commas

        # Add longer pauses for section breaks
        text = text.replace("\n\n", "<break time='500ms'/>")

        return text

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
