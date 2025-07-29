import os
import time
import azure.cognitiveservices.speech as speechsdk
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class VoiceTester:
    """Simple voice testing class to compare different Azure Speech voices"""

    def __init__(self):
        """Initialize Azure Speech configuration"""
        try:
            # Load Azure Speech credentials from environment or use defaults (same as main app)
            self.speech_key = os.getenv("AZURE_SPEECH_KEY")
            self.speech_region = os.getenv("AZURE_SPEECH_REGION")

            # Configure Azure Speech
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                region=self.speech_region
            )

            print(f"✅ Azure Speech initialized (Region: {self.speech_region})")

        except Exception as e:
            print(f"❌ Error initializing Azure Speech: {str(e)}")
            self.speech_config = None

    def get_available_voices(self):
        """Define available voices for testing - US and UK options"""
        return {
            "1": {
                "name": "en-US-AriaNeural",
                "description": "Aria (US) - Mature, attractive voice (Current)"
            },
            "2": {
                "name": "en-US-JaneNeural",
                "description": "Jane (US) - Professional, clear voice"
            },
            "3": {
                "name": "en-US-SaraNeural",
                "description": "Sara (US) - Warm, friendly voice"
            },
            "4": {
                "name": "en-GB-SoniaNeural",
                "description": "Sonia (UK) - Conversational British accent ⭐"
            },
            "5": {
                "name": "en-GB-LibbyNeural",
                "description": "Libby (UK) - Young, friendly British voice ⭐"
            },
            "6": {
                "name": "en-GB-AbbiNeural",
                "description": "Abbi (UK) - Cheerful British accent ⭐"
            },
            "7": {
                "name": "en-GB-MaisieNeural",
                "description": "Maisie (UK) - Warm British voice ⭐"
            },
            "8": {
                "name": "en-US-JennyNeural",
                "description": "Jenny (US) - Youthful, energetic voice"
            },
            "9": {
                "name": "en-US-NancyNeural",
                "description": "Nancy (US) - Sophisticated, confident voice"
            }
        }

    def create_engaging_ssml(self, text, voice_name, message_type="general"):
        """Create enhanced SSML with context-aware voice styling"""

        # Define voice styles based on message type
        style_config = {
            "greeting": {
                "style": "cheerful",
                "rate": "medium",
                "pitch": "+5%"
            },
            "instruction": {
                "style": "friendly",
                "rate": "medium",
                "pitch": "medium"
            },
            "success": {
                "style": "excited",
                "rate": "medium",
                "pitch": "+10%"
            },
            "confirmation": {
                "style": "confident",
                "rate": "medium",
                "pitch": "medium"
            },
            "error": {
                "style": "gentle",
                "rate": "medium",
                "pitch": "-5%"
            },
            "general": {
                "style": "friendly",
                "rate": "medium",
                "pitch": "medium"
            }
        }

        config = style_config.get(message_type, style_config["general"])

        # Add natural pauses and emphasis
        enhanced_text = self.add_natural_pauses_and_emphasis(text)

        # Create SSML with voice styling and proper namespace declaration
        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
    <voice name="{voice_name}">
        <mstts:express-as style="{config['style']}" styledegree="1.2">
            <prosody rate="{config['rate']}" pitch="{config['pitch']}">
                {enhanced_text}
            </prosody>
        </mstts:express-as>
    </voice>
</speak>'''

        return ssml

    def add_natural_pauses_and_emphasis(self, text):
        """Add strategic pauses and emphasis to make speech more engaging"""

        # Add emphasis to key words
        emphasis_words = ["Great", "Perfect", "Wonderful", "Excellent", "Amazing", "Fantastic"]
        for word in emphasis_words:
            if word in text:
                text = text.replace(word, f'<emphasis level="moderate">{word}</emphasis>')

        # Add pauses after exclamations
        text = text.replace("!", '!<break time="300ms"/>')

        # Add pauses after questions
        text = text.replace("?", '?<break time="400ms"/>')

        # Add pauses after sentences
        text = text.replace(". ", '.<break time="250ms"/> ')

        return text

    def text_to_speech(self, text, voice_name, message_type="general"):
        """Convert text to speech using specified voice"""
        if not self.speech_config:
            print("❌ Speech configuration not available")
            return False

        try:
            # Create SSML with enhancements
            ssml_text = self.create_engaging_ssml(text, voice_name, message_type)

            print(f"🗣️  Speaking with {voice_name} ({message_type} tone)...")
            print(f"📝 Text: {text}")

            # Configure synthesizer
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            # Speak the SSML
            result = synthesizer.speak_ssml_async(ssml_text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print("✅ Speech synthesis completed successfully")
                return True
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"❌ Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.error_details:
                    print(f"Error details: {cancellation_details.error_details}")
                return False

        except Exception as e:
            print(f"❌ Error in text-to-speech: {str(e)}")
            return False

    def test_voice_samples(self):
        """Test predefined samples with different voices"""

        # Sample messages for different contexts
        test_samples = {
            "greeting": "Good morning! Welcome to Travel Hands. How can I help you with your journey today?",
            "instruction": "Could you please provide the first line of your pickup address?",
            "success": "Excellent! I found 2 volunteers available for your journey.",
            "confirmation": "Perfect! Your journey booking has been confirmed successfully.",
            "error": "I'm sorry, there was a problem with your request. Please try again."
        }

        voices = self.get_available_voices()

        print("\n" + "="*60)
        print("🎤 VOICE TESTING SYSTEM")
        print("="*60)

        while True:
            print("\n📋 Available Voices:")
            for key, voice in voices.items():
                print(f"  {key}. {voice['description']}")
            print("  10. Test all voices with same message")
            print("  11. Custom message test")
            print("  0. Exit")

            choice = input("\n🎯 Select voice to test (0-11): ").strip()

            if choice == "0":
                print("👋 Goodbye!")
                break

            elif choice in voices:
                voice_name = voices[choice]["name"]
                voice_desc = voices[choice]["description"]

                print(f"\n🎭 Testing {voice_desc}")
                print("="*40)

                for msg_type, sample_text in test_samples.items():
                    print(f"\n🎪 {msg_type.upper()} Message:")
                    self.text_to_speech(sample_text, voice_name, msg_type)

                    # Wait between samples
                    time.sleep(1)

                    # Ask if user wants to continue
                    continue_choice = input("   Continue to next sample? (y/n): ").strip().lower()
                    if continue_choice == 'n':
                        break

            elif choice == "10":
                # Test all voices with the same message
                test_msg = "Hello! This is a voice comparison test. I'm here to help you with your journey booking today."

                print(f"\n🎭 VOICE COMPARISON TEST")
                print("="*40)

                for key, voice in voices.items():
                    print(f"\n🎤 Voice {key}: {voice['description']}")
                    self.text_to_speech(test_msg, voice["name"], "greeting")
                    time.sleep(2)  # Pause between voices

            elif choice == "11":
                # Custom message test
                custom_text = input("\n📝 Enter your custom message: ").strip()
                if custom_text:

                    print("\n🎭 Message Types:")
                    print("  1. greeting  2. instruction  3. success  4. confirmation  5. error  6. general")
                    msg_type_choice = input("Select message type (1-6): ").strip()

                    msg_types = ["greeting", "instruction", "success", "confirmation", "error", "general"]
                    msg_type = msg_types[int(msg_type_choice)-1] if msg_type_choice.isdigit() and 1 <= int(msg_type_choice) <= 6 else "general"

                    voice_choice = input("Select voice (1-9): ").strip()
                    if voice_choice in voices:
                        voice_name = voices[voice_choice]["name"]
                        self.text_to_speech(custom_text, voice_name, msg_type)

            else:
                print("❌ Invalid choice. Please try again.")

def main():
    """Main function to run the voice tester"""
    print("🎤 Voice Tester for Travel Hands Application")
    print("=" * 50)

    # Check if environment variables are set
    if not os.getenv("AZURE_SPEECH_KEY"):
        print("⚠️  AZURE_SPEECH_KEY environment variable not found")
        print("   You may need to set this for the voice functionality to work")
        print()

    # Initialize and run voice tester
    tester = VoiceTester()

    if tester.speech_config:
        tester.test_voice_samples()
    else:
        print("❌ Cannot start voice testing due to configuration issues")
        print("💡 Please check your Azure Speech Service credentials")

if __name__ == "__main__":
    main()
