"""
Infrastructure package for external integrations.
Handles AWS services, external APIs, and async adapters.
"""

from .external_apis import ForthAPIClient
from .queue import QueueAdapter, create_queue_adapter

__all__ = ["QueueAdapter", "create_queue_adapter", "ForthAPIClient"]
