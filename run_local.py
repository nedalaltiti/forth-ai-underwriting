#!/usr/bin/env python3
"""
Simple script to run the Forth AI Underwriting system locally for testing.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import uvicorn
        import fastapi
        import forth_ai_underwriting
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: uv sync")
        return False

def check_env_file():
    """Check if .env file exists and has required variables."""
    env_path = Path("configs/.env")
    if not env_path.exists():
        print("❌ .env file not found at configs/.env")
        print("Create it from configs/.env.example and add your API keys")
        return False
    
    required_vars = [
        "FORTH_API_BASE_URL",
        "FORTH_API_KEY", 
        "GOOGLE_API_KEY"
    ]
    
    env_content = env_path.read_text()
    missing_vars = []
    
    for var in required_vars:
        if f"{var}=" not in env_content or f"{var}=your_" in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or incomplete environment variables: {', '.join(missing_vars)}")
        print("Please update your configs/.env file")
        return False
    
    print("✅ Environment configuration looks good")
    return True

def run_server():
    """Run the FastAPI server."""
    print("🚀 Starting Forth AI Underwriting system...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API docs will be available at: http://localhost:8000/docs")
    print("🔧 To test webhook, run: python test_webhook_integration.py")
    print("-" * 60)
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "forth_ai_underwriting.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n\n❌ Server failed to start: {e}")
        return False
    
    return True

def main():
    """Main function."""
    print("Forth AI Underwriting - Local Development Server")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        sys.exit(1)
    
    # Check if we're in the right directory
    if not Path("src/forth_ai_underwriting").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment configuration
    if not check_env_file():
        sys.exit(1)
    
    # Set PYTHONPATH
    os.environ["PYTHONPATH"] = str(Path.cwd() / "src")
    
    # Run the server
    if not run_server():
        sys.exit(1)

if __name__ == "__main__":
    main() 