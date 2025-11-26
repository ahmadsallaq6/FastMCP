"""
Frontend server runner script.

Starts the Streamlit application for the Loan Assistant ChatBot.

Usage:
    python run_frontend.py
    
Or with Streamlit CLI:
    streamlit run frontend/streamlit_app.py
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    # Get the path to the streamlit app
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, "frontend", "streamlit_app.py")
    
    print("Starting Streamlit Frontend...")
    print("Press Ctrl+C to stop")
    
    # Run streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])
