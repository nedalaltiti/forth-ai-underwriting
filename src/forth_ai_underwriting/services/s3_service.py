"""
S3 service with support for both AWS S3 and local filesystem storage.
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.utils.environment import get_env_var
from loguru import logger


class LocalStorageBackend:
    """Local filesystem storage backend for development."""

    def __init__(self, base_path: str = "./temp_documents"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Initialized local storage backend at: {self.base_path.absolute()}"
        )

    def _get_file_path(self, s3_key: str) -> Path:
        """Convert S3 key to local file path."""
        # Replace S3 key separators with filesystem separators
        relative_path = s3_key.replace("/", os.sep)
        return self.base_path / relative_path

    async def upload_file(
        self, local_path: str, s3_key: str, metadata: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Upload file to local storage."""
        try:
            file_path = self._get_file_path(s3_key)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file to storage location
            shutil.copy2(local_path, file_path)

            # Store metadata in a companion file
            if metadata:
                metadata_path = file_path.with_suffix(file_path.suffix + ".meta")
                import json

                with open(metadata_path, "w") as f:
                    json.dump(metadata, f)

            file_size = file_path.stat().st_size

            logger.info(f"Uploaded file to local storage: {s3_key}")

            return {
                "Location": str(file_path),
                "Bucket": "local-storage",
                "Key": s3_key,
                "ETag": f'"{hash(s3_key)}"',
                "Size": file_size,
            }

        except Exception as e:
            logger.error(f"Failed to upload file to local storage: {e}")
            raise

    async def download_file(self, s3_key: str, local_path: str | None = None) -> str:
        """Download file from local storage."""
        file_path = self._get_file_path(s3_key)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found in local storage: {s3_key}")

        if local_path is None:
            # Create temporary file
            temp_dir = tempfile.mkdtemp(prefix="forth_download_")
            local_path = os.path.join(temp_dir, file_path.name)

        # Copy file to download location
        shutil.copy2(file_path, local_path)

        logger.info(f"Downloaded file from local storage: {s3_key} -> {local_path}")
        return local_path

    async def get_metadata(self, s3_key: str) -> dict[str, Any]:
        """Get file metadata from local storage."""
        file_path = self._get_file_path(s3_key)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found in local storage: {s3_key}")

        stat_info = file_path.stat()
        metadata = {
            "ContentLength": stat_info.st_size,
            "LastModified": stat_info.st_mtime,
            "ContentType": "application/octet-stream",
        }

        # Load custom metadata if available
        metadata_path = file_path.with_suffix(file_path.suffix + ".meta")
        if metadata_path.exists():
            import json

            with open(metadata_path) as f:
                custom_metadata = json.load(f)
                metadata.update(custom_metadata)

        return metadata

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate a file:// URL for local storage."""
        file_path = self._get_file_path(s3_key)
        return f"file://{file_path.absolute()}"

    async def delete_file(self, s3_key: str) -> bool:
        """Delete file from local storage."""
        try:
            file_path = self._get_file_path(s3_key)
            if file_path.exists():
                file_path.unlink()

            # Also delete metadata file if it exists
            metadata_path = file_path.with_suffix(file_path.suffix + ".meta")
            if metadata_path.exists():
                metadata_path.unlink()

            logger.info(f"Deleted file from local storage: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from local storage: {e}")
            return False

    def list_files(self, prefix: str, max_keys: int = 100) -> list:
        """List files in local storage with prefix."""
        try:
            prefix_path = self.base_path / prefix.replace("/", os.sep)
            files = []

            if prefix_path.exists() and prefix_path.is_dir():
                for file_path in prefix_path.rglob("*"):
                    if file_path.is_file() and not file_path.suffix == ".meta":
                        relative_path = file_path.relative_to(self.base_path)
                        s3_key = str(relative_path).replace(os.sep, "/")
                        files.append(
                            {
                                "Key": s3_key,
                                "Size": file_path.stat().st_size,
                                "LastModified": file_path.stat().st_mtime,
                            }
                        )

                        if len(files) >= max_keys:
                            break

            return files
        except Exception as e:
            logger.error(f"Failed to list files in local storage: {e}")
            return []


class S3Service:
    """Service for managing document storage with AWS S3 or local filesystem."""

    def __init__(self):
        self.use_local_mode = False
        self.local_backend = None
        self.s3_client = None

        # Get S3 configuration from environment variables
        self.bucket_name = get_env_var(
            "AWS_S3_BUCKET_NAME", "forth-underwriting-documents"
        )
        self.aws_access_key_id = get_env_var("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = get_env_var("AWS_SECRET_ACCESS_KEY")

        try:
            # Try to initialize AWS S3
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError

            # Build S3 client configuration
            s3_config = {
                "region_name": settings.aws.region,
            }

            # Only add credentials if they're available
            if self.aws_access_key_id and self.aws_secret_access_key:
                s3_config.update(
                    {
                        "aws_access_key_id": self.aws_access_key_id,
                        "aws_secret_access_key": self.aws_secret_access_key,
                    }
                )

            self.s3_client = boto3.client("s3", **s3_config)

            # Test AWS credentials
            try:
                self.s3_client.list_buckets()
                logger.info("AWS S3 client initialized successfully")
                self._ensure_bucket_exists()
            except (NoCredentialsError, ClientError) as e:
                logger.warning(f"AWS S3 not available: {e}")
                self._initialize_local_mode()

        except ImportError:
            logger.warning("boto3 not available, using local storage backend")
            self._initialize_local_mode()
        except Exception as e:
            logger.warning(f"Failed to initialize AWS S3: {e}")
            self._initialize_local_mode()

    def _initialize_local_mode(self):
        """Initialize local development mode."""
        self.use_local_mode = True
        self.local_backend = LocalStorageBackend()
        logger.info("✅ S3 service initialized in LOCAL DEVELOPMENT MODE")

    def _ensure_bucket_exists(self):
        """Ensure S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket exists: {self.bucket_name}")
        except self.s3_client.exceptions.NoSuchBucket:
            try:
                if settings.aws.region == "us-east-1":
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            "LocationConstraint": settings.aws.region
                        },
                    )

                # Enable server-side encryption
                self.s3_client.put_bucket_encryption(
                    Bucket=self.bucket_name,
                    ServerSideEncryptionConfiguration={
                        "Rules": [
                            {
                                "ApplyServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256"
                                }
                            }
                        ]
                    },
                )

                logger.info(f"Created S3 bucket with encryption: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to create S3 bucket: {e}")
                self._initialize_local_mode()
        except Exception as e:
            logger.error(f"Error checking S3 bucket: {e}")
            self._initialize_local_mode()

    def generate_s3_key(self, contact_id: str, doc_id: str, filename: str) -> str:
        """Generate S3 key for a document."""
        # Create hierarchical structure: contact_id/doc_id/filename
        safe_filename = filename.replace(" ", "_").replace("/", "_")
        return f"contacts/{contact_id}/documents/{doc_id}/{safe_filename}"

    async def upload_document(
        self,
        file_path: str,
        contact_id: str,
        doc_id: str,
        filename: str,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload document to storage (S3 or local)."""
        s3_key = self.generate_s3_key(contact_id, doc_id, filename)

        if self.use_local_mode:
            return await self.local_backend.upload_file(file_path, s3_key, metadata)

        # AWS S3
        try:
            extra_args = {"ServerSideEncryption": "AES256"}

            # Ensure metadata is properly formatted for S3
            if metadata:
                # S3 metadata values must be strings
                string_metadata = {}
                for key, value in metadata.items():
                    if value is not None:
                        string_metadata[key] = str(value)
                if string_metadata:
                    extra_args["Metadata"] = string_metadata

            # Upload file
            self.s3_client.upload_file(
                file_path, self.bucket_name, s3_key, ExtraArgs=extra_args
            )

            # Get file size
            file_size = os.path.getsize(file_path)

            logger.info(f"Uploaded document to S3: s3://{self.bucket_name}/{s3_key}")

            return {
                "Location": f"s3://{self.bucket_name}/{s3_key}",
                "Bucket": self.bucket_name,
                "Key": s3_key,
                "Size": file_size,
                "Metadata": metadata or {},
            }

        except Exception as e:
            logger.error(f"Failed to upload document to S3: {e}")
            raise

    async def download_document(
        self, s3_key: str, local_path: str | None = None
    ) -> str:
        """Download document from storage (S3 or local)."""
        if self.use_local_mode:
            return await self.local_backend.download_file(s3_key, local_path)

        # AWS S3
        if local_path is None:
            # Create temporary file
            temp_dir = tempfile.mkdtemp(prefix="forth_download_")
            filename = os.path.basename(s3_key)
            local_path = os.path.join(temp_dir, filename)

        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded document from S3: {s3_key} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download document from S3: {e}")
            raise

    async def get_document_metadata(self, s3_key: str) -> dict[str, Any]:
        """Get document metadata from storage (S3 or local)."""
        if self.use_local_mode:
            return await self.local_backend.get_metadata(s3_key)

        # AWS S3
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            return {
                "ContentLength": response.get("ContentLength"),
                "ContentType": response.get("ContentType"),
                "LastModified": response.get("LastModified"),
                "ETag": response.get("ETag"),
                "Metadata": response.get("Metadata", {}),
            }
        except Exception as e:
            logger.error(f"Failed to get document metadata from S3: {e}")
            raise

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate presigned URL for document access."""
        if self.use_local_mode:
            return self.local_backend.generate_presigned_url(s3_key, expiration)

        # AWS S3
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def delete_document(self, s3_key: str) -> bool:
        """Delete document from storage (S3 or local)."""
        if self.use_local_mode:
            return await self.local_backend.delete_file(s3_key)

        # AWS S3
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted document from S3: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from S3: {e}")
            return False

    def list_documents(self, prefix: str, max_keys: int = 100) -> list:
        """List documents in storage with prefix."""
        if self.use_local_mode:
            return self.local_backend.list_files(prefix, max_keys)

        # AWS S3
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix, MaxKeys=max_keys
            )

            objects = []
            for obj in response.get("Contents", []):
                objects.append(
                    {
                        "Key": obj["Key"],
                        "Size": obj["Size"],
                        "LastModified": obj["LastModified"],
                    }
                )

            return objects
        except Exception as e:
            logger.error(f"Failed to list documents from S3: {e}")
            return []

    def generate_presigned_upload_url(
        self,
        contact_id: str,
        doc_id: str,
        filename: str,
        expiration: int = 3600,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
    ) -> dict[str, Any]:
        """
        Generate a pre-signed URL for direct upload to S3.
        This allows clients to upload files directly to S3 without going through our servers.

        Args:
            contact_id: Contact identifier
            doc_id: Document identifier
            filename: Document filename
            expiration: URL expiration time in seconds (default 1 hour)
            max_file_size: Maximum file size allowed in bytes

        Returns:
            Dictionary containing the pre-signed URL and upload fields
        """
        try:
            s3_key = self.generate_s3_key(contact_id, doc_id, filename)

            # Conditions for the upload
            conditions = [
                {"bucket": self.bucket_name},
                {"key": s3_key},
                ["starts-with", "$Content-Type", "application/"],
                ["content-length-range", 1, max_file_size],
            ]

            # Fields to include in the form
            fields = {
                "key": s3_key,
                "Content-Type": "application/pdf",
                "x-amz-meta-contact-id": contact_id,
                "x-amz-meta-doc-id": doc_id,
                "x-amz-meta-upload-source": "direct_upload",
                "x-amz-meta-uploaded-at": datetime.utcnow().isoformat(),
            }

            if self.use_local_mode:
                # For local development, return a mock URL
                logger.info(f"🏠 Local mode: Mock pre-signed URL for {s3_key}")
                return {
                    "url": f"http://localhost:8000/mock-upload/{s3_key}",
                    "fields": fields,
                    "s3_key": s3_key,
                    "expiration": expiration,
                    "max_file_size": max_file_size,
                }

            # Generate the pre-signed POST
            response = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=s3_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration,
            )

            logger.info(f"✅ Generated pre-signed upload URL for: {s3_key}")

            return {
                **response,
                "s3_key": s3_key,
                "expiration": expiration,
                "max_file_size": max_file_size,
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate pre-signed upload URL: {e}")
            raise


# Global S3 service instance
_s3_service: S3Service | None = None


def get_s3_service() -> S3Service:
    """Get the global S3 service instance."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
