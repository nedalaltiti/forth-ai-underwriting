#!/usr/bin/env python3
"""
Test script for webhook integration testing.
Tests the complete flow from webhook trigger to validation results.
"""

import asyncio
import httpx
import json
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Test configuration
LOCAL_API_URL = "http://localhost:8000"
WEBHOOK_ENDPOINT = "/webhook/forth-docs"
TEAMS_ENDPOINT = "/teams/validate"
HEALTH_ENDPOINT = "/health"

# Sample webhook payload (simulating Forth CRM)
SAMPLE_WEBHOOK_PAYLOAD = {
    "contact_id": "test_contact_12345",
    "document_type": "agreement",
    "document_url": "https://example.com/sample_contract.pdf", 
    "document_name": "sample_contract.pdf",
    "created_by": "test_user",
    "timestamp": datetime.now().isoformat(),
    "additional_data": {
        "file_size": 1024000,
        "upload_source": "agent_portal"
    }
}

# Sample Teams validation request
SAMPLE_TEAMS_REQUEST = {
    "contact_id": "test_contact_12345",
    "user_id": "test_teams_user",
    "conversation_id": "test_conversation_123"
}


class WebhookTester:
    """Comprehensive webhook integration tester."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.server_process: Optional[subprocess.Popen] = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
    
    def start_local_server(self) -> bool:
        """Start the local FastAPI server."""
        print("🚀 Starting local FastAPI server...")
        
        try:
            # Start the server using uvicorn
            self.server_process = subprocess.Popen([
                sys.executable, "-m", "uvicorn",
                "forth_ai_underwriting.api.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--reload"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to start
            print("⏳ Waiting for server to start...")
            time.sleep(5)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    async def wait_for_server(self, max_attempts: int = 10) -> bool:
        """Wait for the server to be ready."""
        for attempt in range(max_attempts):
            try:
                response = await self.client.get(f"{LOCAL_API_URL}/")
                if response.status_code == 200:
                    print("✅ Server is ready!")
                    return True
            except:
                pass
            
            print(f"⏳ Waiting for server... (attempt {attempt + 1}/{max_attempts})")
            await asyncio.sleep(2)
        
        print("❌ Server failed to start")
        return False
    
    async def test_health_check(self) -> bool:
        """Test the health check endpoint."""
        print("\n🔍 Testing health check endpoint...")
        
        try:
            response = await self.client.get(f"{LOCAL_API_URL}{HEALTH_ENDPOINT}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Health check passed")
                print(f"   Status: {data.get('data', {}).get('status', 'unknown')}")
                print(f"   Services: {data.get('data', {}).get('services', {})}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    async def test_webhook_trigger(self) -> bool:
        """Test the webhook endpoint with a sample payload."""
        print("\n📤 Testing webhook trigger...")
        
        try:
            response = await self.client.post(
                f"{LOCAL_API_URL}{WEBHOOK_ENDPOINT}",
                json=SAMPLE_WEBHOOK_PAYLOAD,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Webhook trigger successful")
                print(f"   Message: {data.get('message')}")
                print(f"   Contact ID: {data.get('data', {}).get('contact_id')}")
                print(f"   Status: {data.get('data', {}).get('status')}")
                return True
            else:
                print(f"❌ Webhook trigger failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Webhook trigger error: {e}")
            return False
    
    async def test_teams_validation(self) -> bool:
        """Test the Teams validation endpoint."""
        print("\n👥 Testing Teams validation endpoint...")
        
        # Wait a bit for background processing
        print("⏳ Waiting for background processing...")
        await asyncio.sleep(3)
        
        try:
            response = await self.client.post(
                f"{LOCAL_API_URL}{TEAMS_ENDPOINT}",
                json=SAMPLE_TEAMS_REQUEST,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Teams validation successful")
                print(f"   Message: {data.get('message')}")
                print(f"   Validation Count: {data.get('data', {}).get('validation_count', 0)}")
                
                # Display validation results
                results = data.get('data', {}).get('results', '')
                if results:
                    print("\n📋 Validation Results:")
                    print(results)
                
                return True
            else:
                print(f"❌ Teams validation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Teams validation error: {e}")
            return False
    
    async def test_feedback_endpoint(self) -> bool:
        """Test the feedback endpoint."""
        print("\n💬 Testing feedback endpoint...")
        
        feedback_payload = {
            "contact_id": "test_contact_12345",
            "rating": 5,
            "feedback": "Test feedback - system working well!",
            "user_id": "test_teams_user"
        }
        
        try:
            response = await self.client.post(
                f"{LOCAL_API_URL}/teams/feedback",
                json=feedback_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Feedback submission successful")
                print(f"   Message: {data.get('message')}")
                return True
            else:
                print(f"❌ Feedback submission failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Feedback submission error: {e}")
            return False
    
    async def run_comprehensive_test(self) -> bool:
        """Run the complete test suite."""
        print("🧪 Starting Comprehensive Webhook Integration Test")
        print("=" * 60)
        
        # Start server
        if not self.start_local_server():
            return False
        
        # Wait for server to be ready
        if not await self.wait_for_server():
            return False
        
        # Run all tests
        tests = [
            ("Health Check", self.test_health_check),
            ("Webhook Trigger", self.test_webhook_trigger),
            ("Teams Validation", self.test_teams_validation),
            ("Feedback Submission", self.test_feedback_endpoint)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Results Summary:")
        print("=" * 60)
        
        passed = 0
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
        
        if passed == len(results):
            print("🎉 All tests passed! Your webhook integration is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Please check the output above for details.")
            return False


def simulate_forth_webhook():
    """Simulate a webhook call from Forth CRM (for manual testing)."""
    print("🔧 Simulating Forth CRM Webhook Call")
    print("=" * 50)
    
    print("Webhook Configuration for Forth CRM:")
    print(f"  Name: UW-docs")
    print(f"  URL: {LOCAL_API_URL}{WEBHOOK_ENDPOINT}")
    print(f"  Method: POST")
    print(f"  Content-Type: application/json")
    print(f"  Trigger: document_type == 'agreement'")
    print()
    
    print("Sample Payload:")
    print(json.dumps(SAMPLE_WEBHOOK_PAYLOAD, indent=2))
    print()
    
    print("To test manually with curl:")
    curl_command = f"""curl -X POST {LOCAL_API_URL}{WEBHOOK_ENDPOINT} \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(SAMPLE_WEBHOOK_PAYLOAD)}'"""
    print(curl_command)


async def main():
    """Main test runner."""
    if len(sys.argv) > 1 and sys.argv[1] == "--simulate":
        simulate_forth_webhook()
        return
    
    async with WebhookTester() as tester:
        success = await tester.run_comprehensive_test()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    print("Forth AI Underwriting - Webhook Integration Tester")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python test_webhook_integration.py          # Run full test suite")
        print("  python test_webhook_integration.py --simulate # Show webhook config")
        print("  python test_webhook_integration.py --help     # Show this help")
        sys.exit(0)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        sys.exit(1) 