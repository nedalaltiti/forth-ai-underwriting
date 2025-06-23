#!/usr/bin/env python3
"""
Configuration validation script for Forth AI Underwriting System.
This script validates your configuration for different environments and provides security recommendations.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Main validation function."""
    print("🔧 Forth AI Underwriting - Configuration Validator")
    print("=" * 60)
    
    try:
        # Import after path setup
        from forth_ai_underwriting.config.settings import settings
        from forth_ai_underwriting.utils.environment import get_environment_info
        
        # Show environment info
        print("📋 Environment Information:")
        env_info = get_environment_info()
        for key, value in env_info.items():
            print(f"   {key}: {value}")
        
        print("\n🔍 Configuration Validation:")
        print("-" * 40)
        
        # Validate settings
        try:
            status = settings.validate_configuration()
            
            # Display results
            print(f"Environment: {status['environment']}")
            print(f"Valid: {'✅ Yes' if status['valid'] else '❌ No'}")
            print(f"Security Score: {status['security_score']}/100")
            
            # Show errors
            if status['errors']:
                print(f"\n❌ Errors ({len(status['errors'])}):")
                for error in status['errors']:
                    print(f"   • {error}")
            
            # Show warnings
            if status['warnings']:
                print(f"\n⚠️  Warnings ({len(status['warnings'])}):")
                for warning in status['warnings']:
                    print(f"   • {warning}")
            
            # Environment-specific validations
            print(f"\n📊 Configuration Details:")
            print(f"   Database: {'PostgreSQL' if settings.database.url.startswith('postgresql') else 'Unsupported (PostgreSQL required)'}")
            print(f"   AWS Secrets: {'✅ Enabled' if settings.aws.use_secrets_manager else '❌ Disabled'}")
            print(f"   Debug Mode: {'✅ On' if settings.debug else '❌ Off'}")
            print(f"   CORS Origins: {len(settings.security.cors_origins)} configured")
            
            # Production-specific validation
            if settings.environment == "production":
                print(f"\n🏭 Production Validation:")
                if status['valid']:
                    print("   ✅ Production configuration is valid")
                else:
                    print("   ❌ Production validation failed - check errors above")
            
            # Generate security report
            print(f"\n🛡️  Security Assessment:")
            if status['security_score'] >= 90:
                print("   ✅ Excellent security configuration")
            elif status['security_score'] >= 75:
                print("   ⚠️  Good security configuration with minor issues")
            elif status['security_score'] >= 50:
                print("   ⚠️  Moderate security concerns - review warnings")
            else:
                print("   ❌ Significant security issues - address immediately")
            
            # Configuration checklist for production
            if settings.environment in ["staging", "production"]:
                print(f"\n📋 Production Readiness Checklist:")
                checklist = [
                    ("Strong secret key (64+ chars)", len(settings.security.secret_key) >= 64),
                    ("AWS Secrets Manager enabled", settings.aws.use_secrets_manager),
                    ("PostgreSQL database", settings.database.url.startswith("postgresql")),
                    ("Debug mode disabled", not settings.debug),
                    ("Restricted CORS origins", "*" not in settings.security.cors_origins),
                    ("Production log level", settings.log_level in ["INFO", "WARNING", "ERROR"]),
                ]
                
                for check, passed in checklist:
                    status_icon = "✅" if passed else "❌"
                    print(f"   {status_icon} {check}")
            
            print(f"\n{'✅ Configuration validation completed successfully!' if status['valid'] else '❌ Configuration validation failed!'}")
            return status['valid']
            
        except Exception as e:
            print(f"❌ Configuration loading failed: {e}")
            print("\nCommon issues:")
            print("   • Missing required environment variables")
            print("   • Invalid configuration values")
            print("   • AWS credentials or secrets not accessible")
            print("   • Network connectivity issues")
            return False
    
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you've installed all dependencies with: uv sync")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 