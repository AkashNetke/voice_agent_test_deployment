"""
Audio processing utilities for the voice agent.
Handles Base64 audio conversion and Azure Speech Services integration.
"""

import os
import base64
import tempfile
import requests
import json
import struct
import subprocess
from typing import Optional, Dict
import azure.cognitiveservices.speech as speechsdk
from voice_agent.agent.speech_services import SpeechServices
import logging

logger = logging.getLogger(__name__)

class AudioFormatAnalyzer:
    """Analyzes audio format and provides conversion utilities"""
    
    def __init__(self):
        self.supported_formats = {
            'wav': b'RIFF',
            'webm': b'\x1a\x45\xdf\xa3',
            'ogg': b'OggS',
            'mp3': b'ID3',
            'mp4': b'ftyp',
            'flac': b'fLaC'
        }
    
    def analyze_audio_header(self, audio_data: bytes) -> Dict:
        """Analyze audio data header to determine format"""
        if len(audio_data) < 16:
            return {"error": "Audio data too short for analysis"}
        
        header = audio_data[:16]
        header_hex = header.hex()
        
        result = {
            "header_bytes": header,
            "header_hex": header_hex,
            "size": len(audio_data),
            "detected_format": "unknown"
        }
        
        # Check against known formats
        for format_name, signature in self.supported_formats.items():
            if header.startswith(signature):
                result["detected_format"] = format_name
                break
            
        # Special case for WAV files
        if header.startswith(b'RIFF') and b'WAVE' in audio_data[:20]:
            result["detected_format"] = "wav"
            result["is_valid_wav"] = True
        else:
            result["is_valid_wav"] = False
            
        return result
    
    def convert_to_wav_ffmpeg(self, input_data: bytes) -> Optional[bytes]:
        """Convert audio data to WAV format using FFmpeg"""
        input_temp = None
        output_temp = None
        
        try:
            # Create temporary input file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
                input_temp = f.name
                f.write(input_data)
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                output_temp = f.name
            
            # FFmpeg command to convert to WAV format suitable for Azure Speech Services
            # Azure prefers: 16kHz, 16-bit, mono PCM WAV
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite output file
                '-i', input_temp,  # Input file
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',  # Mono
                '-f', 'wav',  # WAV format
                output_temp
            ]
            
            logger.info(f"🔄 Running FFmpeg conversion: {' '.join(cmd)}")
            
            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Read converted audio
                with open(output_temp, 'rb') as f:
                    converted_data = f.read()
                
                logger.info(f"✅ FFmpeg conversion successful: {len(converted_data)} bytes")
                return converted_data
            else:
                logger.error(f"❌ FFmpeg conversion failed:")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("❌ FFmpeg conversion timed out")
            return None
        except FileNotFoundError:
            logger.error("❌ FFmpeg not found. Please install FFmpeg")
            return None
        except Exception as e:
            logger.error(f"❌ FFmpeg conversion error: {str(e)}")
            return None
        finally:
            # Clean up temporary files
            for temp_file in [input_temp, output_temp]:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to clean up {temp_file}: {e}")


class AudioProcessor:
    """
    Audio processing utilities using Azure Speech Services REST API.
    Uses the REST API for speech-to-text (more reliable) and Speech SDK for text-to-speech.
    """
    
    def __init__(self, speech_services: SpeechServices):
        self.speech_services = speech_services
        self.debug_mode = True
        self.debug_dir = tempfile.mkdtemp(prefix="voice_agent_debug_")
        
        # Get Azure Speech configuration
        self.speech_key = os.getenv('AZURE_SPEECH_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION')
        
        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech Service key and region must be configured")
        
        # REST API endpoint for speech-to-text (Microsoft's recommended approach)
        self.stt_endpoint = f"https://{self.speech_region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        
        logger.info(f"🔍 AudioProcessor initialized with debug mode enabled")
        logger.info(f"🔍 Debug files will be saved to: {self.debug_dir}")
        logger.info(f"🔍 Using Azure REST API endpoint: {self.stt_endpoint}")

    def base64_to_audio_file(self, base64_audio: str) -> str:
        """Convert Base64 encoded audio to temporary audio file"""
        try:
            audio_data = base64.b64decode(base64_audio)
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_filename = temp_file.name
            
            logger.info(f"🔍 Created temporary audio file: {temp_filename} ({len(audio_data)} bytes)")
            return temp_filename
            
        except Exception as e:
            logger.error(f"❌ Failed to decode Base64 audio: {str(e)}")
            raise ValueError(f"Invalid Base64 audio data: {str(e)}")
    
    def audio_file_to_base64(self, audio_file_path: str) -> str:
        """Convert audio file to Base64 encoded string"""
        try:
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                base64_audio = base64.b64encode(audio_data).decode('utf-8')
            
            logger.info(f"🔍 Encoded audio file to Base64: {audio_file_path} ({len(audio_data)} bytes)")
            return base64_audio
            
        except FileNotFoundError:
            logger.error(f"❌ Audio file not found: {audio_file_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to encode audio file: {str(e)}")
            raise ValueError(f"Error reading audio file: {str(e)}")

    def speech_to_text_from_base64(self, base64_audio_data: str) -> str:
        """
        Convert Base64-encoded audio to text using Azure Speech-to-Text REST API.
        This approach follows Microsoft's recommendations for better compatibility.
        Now includes automatic format detection and conversion.
        """
        if not base64_audio_data or not base64_audio_data.strip():
            logger.info("🔇 Empty audio data - treating as silence")
            return ""  # Return empty string for silence, not error message

        try:
            logger.info(f"🎤 Starting speech-to-text conversion from Base64 audio")
            logger.info(f"🔍 Base64 audio length: {len(base64_audio_data)} characters")
            
            # Decode Base64 audio data
            try:
                decoded_audio_data = base64.b64decode(base64_audio_data)
                logger.info(f"🔍 Decoded audio data size: {len(decoded_audio_data)} bytes")
            except Exception as e:
                logger.error(f"❌ Failed to decode Base64 audio: {str(e)}")
                return ""  # Return empty string for invalid audio

            # Check for very small audio files (likely silence)
            if len(decoded_audio_data) < 1000:  # Less than 1KB is likely just noise
                logger.info("🔇 Audio data too small - likely silence or noise")
                return ""  # Return empty string for tiny audio

            # Analyze audio format and convert if needed
            analyzer = AudioFormatAnalyzer()
            format_info = analyzer.analyze_audio_header(decoded_audio_data)
            
            logger.info(f"🔍 Detected audio format: {format_info['detected_format']}")
            
            # Convert to WAV if not already in WAV format
            if not format_info.get('is_valid_wav', False):
                logger.info("🔄 Converting audio to WAV format for Azure compatibility...")
                converted_data = analyzer.convert_to_wav_ffmpeg(decoded_audio_data)
                if converted_data:
                    decoded_audio_data = converted_data
                    logger.info("✅ Audio converted to WAV successfully")
                    
                    # Verify conversion
                    verify_info = analyzer.analyze_audio_header(decoded_audio_data)
                    logger.info(f"🔍 Post-conversion format: {verify_info['detected_format']}")
                else:
                    logger.error("❌ Audio conversion failed")
                    return ""
            else:
                logger.info("✅ Audio is already in WAV format")

            # Create temporary file for debugging
            temp_filename = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(decoded_audio_data)
                    temp_filename = temp_file.name
                
                logger.info(f"🔍 Created temporary audio file: {temp_filename} ({len(decoded_audio_data)} bytes)")
                
                # Save debug copy if enabled
                if self.debug_mode:
                    debug_file = os.path.join(self.debug_dir, f"processed_audio_{os.path.basename(temp_filename)}")
                    with open(debug_file, 'wb') as f:
                        f.write(decoded_audio_data)
                    logger.info(f"🔍 Debug: Saved processed audio to {debug_file}")

                # Check final WAV file format
                if len(decoded_audio_data) >= 16:
                    header = decoded_audio_data[:16]
                    logger.info(f"🔍 Final audio file size: {os.path.getsize(temp_filename)} bytes")
                    logger.info(f"🔍 Final audio header (first 16 bytes): {header}")
                    logger.info(f"🔍 Final header as hex: {header.hex()}")
                    
                    if header.startswith(b'RIFF') and b'WAVE' in header:
                        logger.info("✅ Final audio file is a valid WAV file")
                    else:
                        logger.warning("⚠️ Final audio file may still not be a valid WAV format")

                # Use Azure Speech-to-Text REST API
                return self._perform_azure_rest_stt(decoded_audio_data)

            finally:
                # Clean up temporary file
                if temp_filename and os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                    logger.info(f"🧹 Cleaned up temporary file: {temp_filename}")

        except Exception as e:
            logger.error(f"❌ Speech to text conversion failed: {str(e)}")
            return ""  # Return empty string instead of throwing exception

    def _perform_azure_rest_stt(self, audio_data: bytes) -> str:
        """
        Perform speech recognition using Azure Speech-to-Text REST API.
        This follows Microsoft's recommended approach for short audio files.
        """
        try:
            logger.info("🌐 Using Azure Speech-to-Text REST API...")
            
            # Prepare headers according to Microsoft documentation
            headers = {
                'Ocp-Apim-Subscription-Key': self.speech_key,
                'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
                'Accept': 'application/json'
            }
            
            # Query parameters according to Microsoft documentation
            params = {
                'language': 'en-US',
                'format': 'detailed',
                'profanity': 'masked'
            }
            
            logger.info(f"🔍 Making REST API request to: {self.stt_endpoint}")
            logger.info(f"🔍 Audio data size: {len(audio_data)} bytes")
            
            # Make the REST API call
            response = requests.post(
                self.stt_endpoint,
                headers=headers,
                params=params,
                data=audio_data,
                timeout=30
            )
            
            logger.info(f"🔍 Azure API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"🔍 Azure API response: {json.dumps(result, indent=2)}")
                
                # Parse response according to Microsoft documentation
                recognition_status = result.get('RecognitionStatus')
                
                if recognition_status == 'Success':
                    recognized_text = result.get('DisplayText', '').strip()
                    if recognized_text:
                        logger.info(f"✅ Speech successfully recognized: '{recognized_text}'")
                        return recognized_text
                    else:
                        logger.info("🔇 Speech recognition succeeded but no text detected (silence)")
                        return ""  # Empty string for silence
                        
                elif recognition_status == 'InitialSilenceTimeout':
                    logger.info("🔇 Initial silence timeout - no speech detected")
                    return ""  # Empty string for silence
                    
                elif recognition_status == 'BabbleTimeout':
                    logger.info("🔇 Babble timeout - unclear audio detected") 
                    return ""  # Empty string for unclear audio
                    
                elif recognition_status == 'NoMatch':
                    logger.info("🔇 No speech match found in audio")
                    return ""  # Empty string for no match
                    
                else:
                    logger.warning(f"⚠️ Unhandled recognition status: {recognition_status}")
                    return ""  # Empty string for other statuses
            
            elif response.status_code == 400:
                logger.error(f"❌ Bad request (400): {response.text}")
                return ""  # Empty string for bad request
                
            elif response.status_code == 401:
                logger.error(f"❌ Unauthorized (401): Check Azure Speech Service credentials")
                return ""  # Empty string for auth error
                
            else:
                logger.error(f"❌ Azure API error {response.status_code}: {response.text}")
                return ""  # Empty string for other errors

        except requests.exceptions.Timeout:
            logger.error("❌ Azure API request timeout")
            return ""  # Empty string for timeout
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error calling Azure API: {str(e)}")
            return ""  # Empty string for network error
            
        except Exception as e:
            logger.error(f"❌ Unexpected error in Azure REST API call: {str(e)}")
            return ""  # Empty string for unexpected error

    def text_to_speech_base64(self, text: str, message_type: str = "general") -> Optional[str]:
        """
        Convert text to speech and return as Base64-encoded audio using Azure Speech SDK.
        The Speech SDK works well for text-to-speech, so we keep using it for TTS.
        """
        if not text or not text.strip():
            logger.warning("⚠️ Empty text provided for TTS")
            return None

        temp_filename = None
        try:
            logger.info(f"🔊 Starting text-to-speech conversion for: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            logger.info(f"🔍 Message type: {message_type}")
            
            # Create temporary file for audio output
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
            
            logger.info(f"🔍 TTS output file: {temp_filename}")
            
            # Configure audio output to file using Speech SDK
            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_filename)
            
            # Create speech synthesizer
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_services.speech_config,
                audio_config=audio_config
            )
            
            logger.info("🔄 Synthesizing text to speech...")
            
            # Synthesize speech
            result = speech_synthesizer.speak_text_async(text).get()
            
            # Check synthesis result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("✅ Speech synthesis completed successfully")
                
                # Read the generated audio file
                logger.info("🔄 Reading generated audio file...")
                if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                    with open(temp_filename, 'rb') as audio_file:
                        audio_data = audio_file.read()
                        base64_audio = base64.b64encode(audio_data).decode('utf-8')
                    
                    logger.info(f"🔍 Encoded audio file to Base64: {temp_filename} ({len(audio_data)} bytes)")
                    
                    # Save debug copy if enabled
                    if self.debug_mode:
                        debug_file = os.path.join(self.debug_dir, f"output_audio_{os.path.basename(temp_filename)}")
                        with open(debug_file, 'wb') as f:
                            f.write(audio_data)
                        logger.info(f"🔍 Debug: Saved TTS output to {debug_file}")
                    
                    logger.info("✅ Text-to-speech synthesis completed successfully")
                    return base64_audio
                else:
                    logger.error(f"❌ Generated audio file is empty or missing: {temp_filename}")
                    return None
                    
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = speechsdk.CancellationDetails(result)
                logger.error(f"❌ Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"❌ Error details: {cancellation_details.error_details}")
                return None
            else:
                logger.error(f"❌ Speech synthesis failed: {result.reason}")
                return None

        except Exception as e:
            logger.error(f"❌ Text-to-speech conversion failed: {str(e)}")
            return None
        
        finally:
            # Clean up temporary file
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                    logger.info(f"🧹 Cleaned up TTS temporary file: {temp_filename}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to clean up temporary file {temp_filename}: {str(e)}")

    def cleanup_temp_files(self, file_paths: list):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.info(f"🧹 Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean up {file_path}: {str(e)}")

    def cleanup(self):
        """Clean up debug directory and temporary files"""
        try:
            if os.path.exists(self.debug_dir):
                import shutil
                shutil.rmtree(self.debug_dir)
                logger.info(f"🧹 Cleaned up debug directory: {self.debug_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to clean up debug directory: {str(e)}")

def get_audio_processor(speech_services) -> AudioProcessor:
    """Factory function to create AudioProcessor instance"""
    return AudioProcessor(speech_services) 