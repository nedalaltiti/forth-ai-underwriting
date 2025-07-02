"""
Document Service - Focused on document downloading, processing, and storage.
Microservice responsible for document lifecycle management.
"""

import asyncio
import signal

from config.settings import DocumentConfig
from document_processor import DocumentProcessor
from loguru import logger


class DocumentService:
    """
    Document service main application.
    Handles document downloading, processing, and S3 storage.
    """

    def __init__(self):
        self.config = DocumentConfig()
        self.processor = DocumentProcessor(self.config)
        self.running = False

    async def startup(self):
        """Initialize document service."""
        logger.info("🚀 Starting Document Service")

        # Initialize processor
        await self.processor.startup()

        # Set up signal handlers
        self._setup_signal_handlers()

        logger.info("✅ Document Service initialized successfully")

    async def run(self):
        """Main service loop."""
        self.running = True
        logger.info(
            f"🎯 Document service started - polling every {self.config.poll_interval_seconds}s"
        )

        try:
            while self.running:
                await self.processor.process_queue_batch()
                await asyncio.sleep(self.config.poll_interval_seconds)

        except asyncio.CancelledError:
            logger.info("📥 Document service gracefully cancelled")
        except Exception as e:
            logger.error(f"❌ Document service error: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("🛑 Shutting down Document Service")
        self.running = False

        if self.processor:
            await self.processor.shutdown()

        logger.info("✅ Document Service shutdown complete")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def health_check(self) -> dict:
        """Get service health status."""
        try:
            processor_health = await self.processor.get_health_status()

            return {
                "service": "document-service",
                "status": "healthy"
                if processor_health.get("status") == "healthy"
                else "degraded",
                "processor": processor_health,
                "running": self.running,
                "config": {
                    "poll_interval": self.config.poll_interval_seconds,
                    "max_concurrent": self.config.max_concurrent_downloads,
                    "queue_name": self.config.queue_name,
                },
            }

        except Exception as e:
            return {
                "service": "document-service",
                "status": "unhealthy",
                "error": str(e),
                "running": self.running,
            }


async def main():
    """Main entry point for document service."""
    service = DocumentService()

    try:
        await service.startup()
        await service.run()
    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted by user")
    except Exception as e:
        logger.error(f"❌ Service failed: {e}")
        raise
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
