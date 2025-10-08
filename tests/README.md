# Tests Directory

This directory contains development and testing tools for the voice agent system.

## Files

### `streamlit_test_journey_booking.py`
- **Purpose**: Interactive web-based testing interface for the journey booking system
- **Usage**: `streamlit run tests/streamlit_test_journey_booking.py`
- **Features**:
  - Voice input testing with microphone
  - Text input fallback
  - Audio processing validation
  - Step-by-step journey booking flow simulation
  - Real-time session state monitoring
  - Azure Speech Services integration testing

### ⚠️ Important Notes

- These are **DEVELOPMENT TOOLS ONLY** - not for production use
- The Streamlit interface requires additional dependencies (`streamlit`)
- Audio testing works best on macOS with system volume configured
- These files should not be deployed to production environments

### Usage Instructions

1. Install Streamlit (development dependency):
   ```bash
   pip install streamlit
   ```

2. Run the test interface:
   ```bash
   cd /path/to/voice-agent
   streamlit run tests/streamlit_test_journey_booking.py
   ```

3. Open your browser to `http://localhost:8501` to access the testing interface

### Production vs Development

- **Production Code**: `src/voice_agent/` - clean, no UI dependencies
- **Development Tools**: `tests/` - includes Streamlit testing interfaces
- **Separation**: This ensures production code remains lean and dependency-free