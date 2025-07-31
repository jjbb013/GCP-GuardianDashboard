import os
import sys
import subprocess
from dotenv import load_dotenv

# Set environment variable to prefer IPv4, which can resolve gRPC connection issues in some networks.
os.environ['GRPC_DNS_RESOLVER'] = 'native'

# Load .env file from the current directory
load_dotenv()

def main():
    """
    A helper script to run the GCP Guardian application locally for testing.
    
    This script will:
    1. Check for a virtual environment and advise if not found.
    2. Install dependencies from requirements.txt.
    3. Check for the .env file and provide instructions if missing.
    4. Run the main application.
    """
    print("--- GCP Guardian Local Runner ---")

    # 1. Check for virtual environment
    if not (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)):
        print("\n[Warning] You are not in a Python virtual environment.")
        print("It is highly recommended to create one to avoid conflicts:")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate\n")

    # 2. Install dependencies
    print("\n[Step 1] Installing dependencies from requirements.txt...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        sys.exit(1)

    # 3. Check for .env file
    if not os.path.exists('.env'):
        print("\n[Step 2] Configuration")
        print("Error: '.env' file not found.")
        print("Please create it by copying '.env.example' and filling in your details.")
        print("  cp .env.example .env")
        sys.exit(1)
    
    print("\n[Step 2] '.env' file found.")

    # 4. Run the application
    print("\n[Step 3] Starting the FastAPI application with uvicorn...")
    print("The application will be available at http://127.0.0.1:8001")
    print("Press Ctrl+C to stop the service.")

    try:
        subprocess.run([
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8001",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred while running the application: {e}")

if __name__ == "__main__":
    main()
