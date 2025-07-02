"""
External API clients with proper async support.
Uses httpx for async HTTP operations.
"""

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger


@dataclass
class APIConfig:
    """Configuration for external API clients."""

    base_url: str
    api_key: str
    api_key_id: str | None = None
    timeout: int = 30
    max_retries: int = 3


class ForthAPIClient:
    """
    Async Forth API client with proper error handling and retries.
    Uses httpx for async HTTP operations.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_id: str | None = None,
        timeout: int = 30,
    ):
        """
        Initialize Forth API client.

        Args:
            base_url: Base URL for Forth API
            api_key: API key for authentication
            api_key_id: API key ID for authentication
            timeout: Request timeout in seconds
        """
        self.config = APIConfig(
            base_url=base_url or "",
            api_key=api_key or "",
            api_key_id=api_key_id,
            timeout=timeout,
        )
        self._client: httpx.AsyncClient | None = None

        if not self.config.base_url or not self.config.api_key:
            logger.warning("Forth API client created without credentials")

    async def __aenter__(self):
        """Async context manager entry."""
        if not self._client:
            headers = {
                "Api-Key": self.config.api_key,
                "Accept": "application/json",
                "User-Agent": "Forth-AI-Underwriting/2.0",
            }

            if self.config.api_key_id:
                headers["Api-Key-Id"] = self.config.api_key_id

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.config.timeout),
                follow_redirects=True,
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def find_document_url(
        self, contact_id: str, doc_id: str, filename: str | None = None
    ) -> str | None:
        """
        Find document URL by doc_id for a contact.

        Args:
            contact_id: Contact identifier
            doc_id: Document ID to search for
            filename: Optional filename for fallback matching

        Returns:
            Document URL if found, None otherwise
        """
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )

        try:
            logger.debug(
                f"Searching for document with doc_id '{doc_id}' for contact {contact_id}"
            )

            # Fetch all documents for the contact
            response = await self._client.get(f"/contacts/{contact_id}/documents")
            response.raise_for_status()

            response_data = response.json()

            # Check if we have response data
            if not response_data or "response" not in response_data:
                logger.warning(
                    f"No response data from documents API for contact {contact_id}"
                )
                return None

            documents = response_data.get("response", {})

            # Search in uploaded documents by doc_id first
            uploaded_docs = documents.get("uploaded", [])
            for doc in uploaded_docs:
                download_path = doc.get("download", "")

                # Extract doc_id from download path: /getfile.php?id=470967734
                if download_path and "id=" in download_path:
                    path_doc_id = download_path.split("id=")[-1]

                    if path_doc_id == doc_id:
                        # Found the document by doc_id
                        file_content_url = doc.get("file_content")

                        if file_content_url:
                            logger.info(
                                f"Found S3 URL for document ID '{doc_id}': {file_content_url[:100]}..."
                            )
                            return file_content_url
                        else:
                            # Construct full URL using download path
                            download_url = (
                                f"{self.config.base_url.rstrip('/')}{download_path}"
                            )
                            logger.info(
                                f"Found download path for document ID '{doc_id}': {download_url}"
                            )
                            return download_url

            # Fallback: Search by filename if provided
            if filename:
                logger.debug(
                    f"Fallback: searching by filename '{filename}' for contact {contact_id}"
                )

                for doc in uploaded_docs:
                    doc_filename = doc.get("file_name", "")

                    # Case-insensitive filename comparison
                    if doc_filename.lower() == filename.lower():
                        # Return S3 URL or download path
                        file_content_url = doc.get("file_content")
                        download_path = doc.get("download")

                        if file_content_url:
                            logger.info(
                                f"Found S3 URL for document '{filename}' (fallback)"
                            )
                            return file_content_url
                        elif download_path:
                            # Construct full URL using download path
                            download_url = (
                                f"{self.config.base_url.rstrip('/')}{download_path}"
                            )
                            logger.info(
                                f"Found download path for document '{filename}' (fallback)"
                            )
                            return download_url

            # Search in esigned documents by doc_id
            esigned = documents.get("esigned", {})
            for doc_type in ["clixsign", "esigns", "docusign"]:
                for doc in esigned.get(doc_type, []):
                    download_path = doc.get("download", "")

                    # Extract doc_id from download path
                    if download_path and "id=" in download_path:
                        path_doc_id = download_path.split("id=")[-1]

                        if path_doc_id == doc_id:
                            download_url = (
                                f"{self.config.base_url.rstrip('/')}{download_path}"
                            )
                            logger.info(
                                f"Found esigned document URL for ID '{doc_id}': {download_url}"
                            )
                            return download_url

            logger.warning(
                f"Document with ID '{doc_id}' not found for contact {contact_id}"
            )
            return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error finding document: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error finding document: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding document: {e}")
            return None

    async def get_contact_data(self, contact_id: str) -> dict[str, Any] | None:
        """
        Fetch contact data from Forth API.

        Args:
            contact_id: Contact identifier

        Returns:
            Contact data if found, None otherwise
        """
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )

        try:
            logger.debug(f"Fetching contact data for: {contact_id}")

            response = await self._client.get(f"/contacts/{contact_id}")
            response.raise_for_status()

            contact_data = response.json()
            logger.debug(f"Successfully fetched contact data for {contact_id}")
            return contact_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching contact: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching contact: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching contact: {e}")
            return None

    async def health_check(self) -> dict[str, Any]:
        """
        Check API health and connectivity.

        Returns:
            Health status information
        """
        if not self.config.base_url or not self.config.api_key:
            return {
                "status": "unconfigured",
                "accessible": False,
                "error": "Missing API credentials",
            }

        try:
            async with self:
                # Try a simple API call to check connectivity
                response = await self._client.get("/health", timeout=5.0)

                return {
                    "status": "healthy",
                    "accessible": True,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                    "base_url": self.config.base_url,
                }

        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "accessible": False,
                "error": f"HTTP {e.response.status_code}",
                "base_url": self.config.base_url,
            }
        except httpx.RequestError as e:
            return {
                "status": "error",
                "accessible": False,
                "error": f"Connection error: {str(e)}",
                "base_url": self.config.base_url,
            }
        except Exception as e:
            return {
                "status": "error",
                "accessible": False,
                "error": f"Unexpected error: {str(e)}",
                "base_url": self.config.base_url,
            }
