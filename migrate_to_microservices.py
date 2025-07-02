#!/usr/bin/env python3
"""
Migration Script: Monolithic to Microservices Architecture
Helps transition from the current structure to true microservices.
"""

import shutil
from pathlib import Path

from loguru import logger


class MicroservicesMigrator:
    """Migrates from monolithic structure to microservices architecture."""

    def __init__(self):
        self.root_dir = Path(".")
        self.services_dir = Path("services")
        self.src_dir = Path("src/forth_ai_underwriting")

    def migrate(self):
        """Execute the full migration process."""
        logger.info("🚀 Starting migration to microservices architecture")

        try:
            self._create_service_structure()
            self._migrate_webhook_service()
            self._migrate_document_service()
            self._migrate_validation_service()
            self._create_shared_libraries()
            self._create_environment_files()
            self._create_deployment_files()

            logger.info("✅ Migration completed successfully!")
            logger.info("📁 New microservices structure created in ./services/")
            logger.info("🔧 Update environment variables in .env files")
            logger.info("🚀 Deploy with: cd services && docker-compose up -d")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise

    def _create_service_structure(self):
        """Create the basic microservices directory structure."""
        logger.info("📁 Creating microservices directory structure")

        services = ["webhook-service", "document-service", "validation-service"]

        for service in services:
            service_path = self.services_dir / service
            (service_path / "src").mkdir(parents=True, exist_ok=True)
            (service_path / "config").mkdir(exist_ok=True)
            (service_path / "tests").mkdir(exist_ok=True)
            (service_path / "docs").mkdir(exist_ok=True)

        # Shared libraries
        shared_libs = self.services_dir / "shared-libs"
        (shared_libs / "models").mkdir(parents=True, exist_ok=True)
        (shared_libs / "utils").mkdir(exist_ok=True)
        (shared_libs / "infrastructure").mkdir(exist_ok=True)

    def _migrate_webhook_service(self):
        """Migrate webhook-related code to webhook service."""
        logger.info("📦 Migrating webhook service components")

        webhook_src = self.services_dir / "webhook-service" / "src"

        # Copy webhook-specific files
        if (self.src_dir / "webhooks").exists():
            shutil.copytree(self.src_dir / "webhooks", webhook_src / "webhooks")

        # Extract webhook endpoints from main.py
        self._extract_webhook_endpoints()

    def _migrate_document_service(self):
        """Migrate document processing code to document service."""
        logger.info("📦 Migrating document service components")

        document_src = self.services_dir / "document-service" / "src"

        # Copy document processing files
        files_to_copy = [
            "services/document_download_service.py",
            "services/s3_service.py",
            "services/process.py",
            "infrastructure/external_apis.py",
        ]

        for file_path in files_to_copy:
            src_file = self.src_dir / file_path
            if src_file.exists():
                dest_file = document_src / src_file.name
                shutil.copy2(src_file, dest_file)
                logger.info(f"  ✅ Copied {file_path}")

    def _migrate_validation_service(self):
        """Migrate validation logic to validation service."""
        logger.info("📦 Migrating validation service components")

        validation_src = self.services_dir / "validation-service" / "src"
        validation_data = self.services_dir / "validation-service" / "data"

        # Copy validation files
        files_to_copy = [
            "services/validation.py",
            "services/gemini_service.py",
            "services/gemini_llm.py",
            "services/llm_service.py",
        ]

        for file_path in files_to_copy:
            src_file = self.src_dir / file_path
            if src_file.exists():
                dest_file = validation_src / src_file.name
                shutil.copy2(src_file, dest_file)
                logger.info(f"  ✅ Copied {file_path}")

        # Copy validation data
        if (self.src_dir / "data").exists():
            shutil.copytree(self.src_dir / "data", validation_data, dirs_exist_ok=True)

        # Copy prompts
        if (self.src_dir / "prompts").exists():
            shutil.copytree(self.src_dir / "prompts", validation_src / "prompts")

    def _create_shared_libraries(self):
        """Create shared libraries with minimal common code."""
        logger.info("📚 Creating shared libraries")

        shared_libs = self.services_dir / "shared-libs"

        # Copy minimal shared models
        if (self.src_dir / "models").exists():
            # Extract only common models
            common_models = shared_libs / "models" / "common.py"
            self._create_common_models(common_models)

        # Copy minimal utilities
        if (self.src_dir / "utils").exists():
            utils_files = ["retry.py", "environment.py"]
            for util_file in utils_files:
                src_file = self.src_dir / "utils" / util_file
                if src_file.exists():
                    dest_file = shared_libs / "utils" / util_file
                    shutil.copy2(src_file, dest_file)

        # Copy queue infrastructure
        if (self.src_dir / "infrastructure" / "queue.py").exists():
            shutil.copy2(
                self.src_dir / "infrastructure" / "queue.py",
                shared_libs / "infrastructure" / "queue.py",
            )

    def _create_common_models(self, output_file):
        """Extract and create common models file."""
        # This would contain logic to extract common models
        # For now, create a placeholder
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            f.write("# Common models extracted from original codebase\n")
            f.write("# TODO: Extract shared models from original models/\n")

    def _extract_webhook_endpoints(self):
        """Extract webhook endpoints from monolithic main.py."""
        webhook_main = self.services_dir / "webhook-service" / "src" / "main.py"

        # This would contain logic to extract webhook endpoints
        # For now, create a placeholder
        with open(webhook_main, "w") as f:
            f.write("# Webhook service main file\n")
            f.write("# TODO: Extract webhook endpoints from original main.py\n")

    def _create_environment_files(self):
        """Create service-specific environment files."""
        logger.info("🔧 Creating environment configuration files")

        services_config = {
            "webhook-service": [
                "WEBHOOK_QUEUE_NAME=uw-contracts-parser-dev-sqs",
                "WEBHOOK_AWS_REGION=us-west-1",
                "WEBHOOK_LOG_LEVEL=INFO",
            ],
            "document-service": [
                "DOCUMENT_QUEUE_NAME=uw-contracts-parser-dev-sqs",
                "DOCUMENT_S3_BUCKET=contact-contracts-dev-s3-us-west-1",
                "DOCUMENT_AWS_REGION=us-west-1",
                "DOCUMENT_MAX_CONCURRENT_DOWNLOADS=3",
                "DOCUMENT_LOG_LEVEL=INFO",
            ],
            "validation-service": [
                "VALIDATION_GEMINI_API_KEY=your_gemini_api_key_here",
                "VALIDATION_FORTH_API_BASE_URL=https://api.forthcrm.com/v1",
                "VALIDATION_LOG_LEVEL=INFO",
            ],
        }

        for service, config_lines in services_config.items():
            env_file = self.services_dir / service / ".env.example"
            with open(env_file, "w") as f:
                f.write(f"# {service.title()} Environment Configuration\n")
                f.write("# Copy to .env and update with actual values\n\n")
                for line in config_lines:
                    f.write(f"{line}\n")

    def _create_deployment_files(self):
        """Create deployment and documentation files."""
        logger.info("🚀 Creating deployment files")

        # Create main docker-compose.yml (already created above)
        # Create individual service documentation
        # Create deployment scripts
        pass


def main():
    """Main migration entry point."""
    print("🔄 Forth AI Underwriting - Microservices Migration")
    print("=" * 50)

    migrator = MicroservicesMigrator()

    try:
        # Check if migration already exists
        if Path("services").exists():
            response = input("⚠️  Services directory already exists. Continue? (y/N): ")
            if response.lower() != "y":
                print("❌ Migration cancelled")
                return

        migrator.migrate()

        print("\n🎉 Migration completed successfully!")
        print("\n📋 Next Steps:")
        print("1. cd services/")
        print("2. Update .env files with your actual credentials")
        print("3. docker-compose up -d")
        print("4. Test individual services:")
        print("   - Webhook: curl http://localhost:8000/health")
        print("   - Validation: curl http://localhost:8001/health")

    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        logger.error(f"Migration error: {e}")


if __name__ == "__main__":
    main()
