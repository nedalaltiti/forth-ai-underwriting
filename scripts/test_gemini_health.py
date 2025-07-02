#!/usr/bin/env python3
"""
Demonstration script for testing GeminiProvider health check functionality.
This script shows how to use the health check method in practice.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from forth_ai_underwriting.services.gemini_llm import get_gemini_provider
from loguru import logger


async def test_gemini_health():
    """Test the GeminiProvider health check method."""
    logger.info("🏥 Testing GeminiProvider Health Check")
    logger.info("=" * 50)

    try:
        # Get the Gemini provider instance
        gemini_provider = get_gemini_provider()
        logger.info(
            f"✅ GeminiProvider instance created: {type(gemini_provider).__name__}"
        )

        # Run the health check
        logger.info("🔍 Running comprehensive health check...")
        health_result = await gemini_provider.health_check()

        # Display results
        logger.info("📊 Health Check Results:")
        logger.info("-" * 30)

        # Overall status
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌",
            "unknown": "❓",
        }

        overall_status = health_result.get("status", "unknown")
        logger.info(
            f"Overall Status: {status_emoji.get(overall_status, '❓')} {overall_status.upper()}"
        )
        logger.info(f"Service: {health_result.get('service', 'N/A')}")
        logger.info(f"Model: {health_result.get('model', 'N/A')}")
        logger.info(f"Timestamp: {health_result.get('timestamp', 'N/A')}")

        # Individual checks
        logger.info("\n🔬 Individual Check Results:")
        checks = health_result.get("checks", {})

        for check_name, check_data in checks.items():
            check_status = check_data.get("status", "unknown")
            check_emoji = status_emoji.get(check_status, "❓")

            logger.info(
                f"  {check_emoji} {check_name.replace('_', ' ').title()}: {check_status}"
            )

            # Show timing if available
            if "time_ms" in check_data:
                logger.info(f"    ⏱️  Response time: {check_data['time_ms']}ms")

            # Show message or error
            if "message" in check_data:
                logger.info(f"    💬 {check_data['message']}")
            elif "error" in check_data:
                logger.info(f"    ⚠️  Error: {check_data['error']}")

            # Show specific details
            if check_name == "configuration" and "issues" in check_data:
                issues = check_data["issues"]
                if issues:
                    logger.info(f"    🔧 Configuration issues: {len(issues)}")
                    for issue in issues:
                        logger.info(f"      - {issue}")

            if check_name == "dependencies" and "dependencies" in check_data:
                deps = check_data["dependencies"]
                logger.info("    📦 Dependencies:")
                for dep_name, dep_info in deps.items():
                    dep_status = dep_info.get("status", "unknown")
                    dep_emoji = (
                        "✅" if dep_status in ["available", "configured"] else "❌"
                    )
                    logger.info(f"      {dep_emoji} {dep_name}: {dep_status}")
                    if "version" in dep_info:
                        logger.info(f"        Version: {dep_info['version']}")
                    if "project_id" in dep_info:
                        logger.info(f"        Project: {dep_info['project_id']}")
                    if "location" in dep_info:
                        logger.info(f"        Location: {dep_info['location']}")

        # Performance metrics
        logger.info("\n⚡ Performance Metrics:")
        metadata = health_result.get("metadata", {})
        if "total_check_time_ms" in metadata:
            logger.info(f"  Total check time: {metadata['total_check_time_ms']}ms")
        if "average_response_time_ms" in metadata:
            logger.info(
                f"  Average response time: {metadata['average_response_time_ms']}ms"
            )
        if "initialization_status" in metadata:
            init_status = metadata["initialization_status"]
            init_emoji = "✅" if init_status else "❌"
            logger.info(f"  Initialization status: {init_emoji} {init_status}")

        # Configuration details
        logger.info("\n⚙️  Configuration:")
        if "temperature" in metadata:
            logger.info(f"  Temperature: {metadata['temperature']}")
        if "max_output_tokens" in metadata:
            logger.info(f"  Max output tokens: {metadata['max_output_tokens']}")

        # JSON output option
        if "--json" in sys.argv:
            logger.info("\n📄 Raw JSON Output:")
            print(json.dumps(health_result, indent=2))

        # Return success/failure based on overall status
        if overall_status == "healthy":
            logger.info("\n🎉 All systems operational!")
            return 0
        elif overall_status == "degraded":
            logger.warning("\n⚠️  System operational with warnings")
            return 1
        else:
            logger.error("\n💥 System unhealthy - issues detected")
            return 2

    except Exception as e:
        logger.error(f"❌ Health check failed with error: {e}")
        logger.exception("Full error details:")
        return 3


async def test_basic_connection():
    """Test basic connection to Gemini service."""
    logger.info("\n🔌 Testing Basic Connection")
    logger.info("-" * 30)

    try:
        gemini_provider = get_gemini_provider()
        is_connected = await gemini_provider.test_connection()

        if is_connected:
            logger.info("✅ Basic connection test: PASSED")
            return True
        else:
            logger.error("❌ Basic connection test: FAILED")
            return False

    except Exception as e:
        logger.error(f"❌ Connection test error: {e}")
        return False


def print_usage():
    """Print usage information."""
    print("Usage: python scripts/test_gemini_health.py [options]")
    print("\nOptions:")
    print("  --json    Output raw JSON health check results")
    print("  --help    Show this help message")
    print("\nThis script tests the GeminiProvider health check functionality.")


async def main():
    """Main function."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return 0

    logger.info("🚀 Starting GeminiProvider Health Check Test")
    logger.info("=" * 60)

    # Test basic connection first
    connection_ok = await test_basic_connection()

    # Run comprehensive health check
    health_exit_code = await test_gemini_health()

    # Summary
    logger.info("\n" + "=" * 60)
    if connection_ok and health_exit_code == 0:
        logger.info("🏆 All tests completed successfully!")
    else:
        logger.warning("⚠️  Some tests failed or have warnings")

    return health_exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
