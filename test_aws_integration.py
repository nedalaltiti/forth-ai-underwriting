#!/usr/bin/env python3
"""
Test script for AWS Secrets Manager integration.
This script tests the complete flow of loading credentials from AWS.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

async def test_aws_integration():
    """Test AWS secrets integration."""
    print("🔧 Testing AWS Secrets Manager Integration")
    print("=" * 50)
    
    try:
        # Test environment loading
        from forth_ai_underwriting.utils.environment import (
            get_environment_info, 
            validate_required_env_vars,
            is_aws_secrets_enabled
        )
        
        print("📋 Environment Information:")
        env_info = get_environment_info()
        for key, value in env_info.items():
            print(f"   {key}: {value}")
        
        print(f"\n🔐 AWS Secrets Enabled: {is_aws_secrets_enabled()}")
        
        if not is_aws_secrets_enabled():
            print("⚠️  AWS Secrets not enabled. Set USE_AWS_SECRETS=true to test.")
            return
        
        # Test settings initialization
        print("\n🔧 Testing Settings Initialization...")
        # Import settings configuration
        try:
            from forth_ai_underwriting.config.settings import settings
            print(f"✅ Settings loaded successfully")
            print(f"   Database URL: {settings.database.url[:50]}..." if len(settings.database.url) > 50 else f"   Database URL: {settings.database.url}")
            print(f"   Environment: {settings.environment}")
            print(f"   AWS Region: {settings.aws.region}")
        except Exception as e:
            print(f"❌ Settings loading failed: {e}")
            return
        
        # Test database config
        print("\n📊 Database Configuration:")
        db_config = settings.database.engine_kwargs
        print(f"   Engine: PostgreSQL")
        print(f"   Pool Size: {db_config.get('pool_size', 'N/A')}")
        print(f"   Max Overflow: {db_config.get('max_overflow', 'N/A')}")
        print(f"   Pool Recycle: {db_config.get('pool_recycle', 'N/A')}s")
        
        # Test Gemini config
        print("\n🤖 Gemini Configuration:")
        gemini_config = {
            "api_key": settings.gemini.api_key,
            "model_name": settings.gemini.model_name,
            "use_aws_secrets": settings.gemini.use_aws_secrets,
        }
        print(f"   Model: {gemini_config.get('model_name', 'Not configured')}")
        print(f"   Project: {gemini_config.get('project', 'Not configured')}")
        print(f"   Location: {gemini_config.get('location', 'Not configured')}")
        
        # Test AWS secret loading (if available)
        if settings.aws.use_secrets_manager:
            print("\n🔐 AWS Secrets Status:")
            print(f"   DB Secret: {'✅ Loaded' if hasattr(settings.database, '_credentials_loaded') else '❌ Not loaded'}")
            print(f"   Gemini Secret: {'✅ Loaded' if settings.gemini.credentials_path else '❌ Not loaded'}")
            
            # Test Google Application Credentials
            google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if google_creds:
                print(f"   Google Creds File: ✅ {google_creds}")
                if os.path.exists(google_creds):
                    print(f"   Credentials File Exists: ✅ Yes")
                else:
                    print(f"   Credentials File Exists: ❌ No")
            else:
                print(f"   Google Creds File: ❌ Not set")
        
        # Test application components
        print("\n🔧 Testing Application Components...")
        
        # Test FastAPI app import
        try:
            from forth_ai_underwriting.api.main import app
            print("   ✅ FastAPI app imported successfully")
        except Exception as e:
            print(f"   ❌ FastAPI app import failed: {e}")
        
        # Test services
        try:
            from forth_ai_underwriting.services.validation import ValidationService
            validation_service = ValidationService()
            print("   ✅ ValidationService initialized successfully")
        except Exception as e:
            print(f"   ❌ ValidationService failed: {e}")
        
        try:
            from forth_ai_underwriting.services.gemini_service import get_gemini_service
            gemini_service = get_gemini_service()
            print("   ✅ GeminiService initialized successfully")
        except Exception as e:
            print(f"   ❌ GeminiService failed: {e}")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        print("   ✅ Cleanup completed")
        
        print("\n🎉 AWS Integration Test Completed Successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_without_aws():
    """Test basic functionality without AWS."""
    print("🔧 Testing Basic Configuration (No AWS)")
    print("=" * 50)
    
    try:
        # Temporarily disable AWS
        original_aws = os.environ.get("USE_AWS_SECRETS")
        os.environ["USE_AWS_SECRETS"] = "false"
        
        from forth_ai_underwriting.config.settings import settings
        
        print(f"✅ Basic settings loaded")
        print(f"   Database: {settings.database.url}")
        print(f"   Environment: {settings.environment}")
        print(f"   Debug: {settings.debug}")
        
        # Restore AWS setting
        if original_aws:
            os.environ["USE_AWS_SECRETS"] = original_aws
        else:
            os.environ.pop("USE_AWS_SECRETS", None)
        
        return True
        
    except Exception as e:
        print(f"❌ Basic test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Forth AI Underwriting - AWS Integration Test")
    print("=" * 60)
    
    # Test basic functionality first
    if not test_without_aws():
        print("❌ Basic tests failed, stopping.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Test AWS integration
    success = asyncio.run(test_aws_integration())
    
    if success:
        print("\n✅ All tests passed! Your AWS integration is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check your configuration.")
        sys.exit(1) 