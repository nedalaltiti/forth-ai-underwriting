"""
Document processing service that orchestrates PDF parsing, text extraction,
and AI-powered analysis using Gemini and other services.
"""

import asyncio
import tempfile
import aiofiles
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, BinaryIO
from dataclasses import dataclass, asdict
from loguru import logger
import hashlib
import mimetypes
from datetime import datetime

# PDF processing
import PyPDF2
import fitz  # PyMuPDF for better text extraction
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# HTTP client for downloading documents
import httpx

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.services.gemini_service import get_gemini_service, ContractData
from forth_ai_underwriting.core.exceptions import (
    DocumentProcessingError,
    create_document_processing_error,
    create_ai_parsing_error
)


@dataclass
class DocumentInfo:
    """Document metadata and processing information."""
    url: str
    filename: str
    file_size: int
    mime_type: str
    page_count: int
    processing_status: str = "pending"
    extracted_text: Optional[str] = None
    text_quality: str = "unknown"
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None


@dataclass
class ProcessingResult:
    """Complete document processing result."""
    document_info: DocumentInfo
    contract_data: Optional[ContractData] = None
    extracted_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    validation_ready: bool = False
    processing_errors: List[str] = None
    
    def __post_init__(self):
        if self.processing_errors is None:
            self.processing_errors = []


class DocumentProcessor:
    """
    Main document processing service that handles the complete workflow
    from document URL to structured data extraction.
    """
    
    def __init__(self):
        self.gemini_service = get_gemini_service()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.document_processing.max_chunk_size * 100,  # Convert to reasonable chunk size
            chunk_overlap=200,
            length_function=len
        )
        self.http_client = httpx.AsyncClient(timeout=settings.document_processing.processing_timeout)
        
        logger.info("DocumentProcessor initialized")
    
    async def process_document(
        self, 
        document_url: str, 
        document_name: Optional[str] = None,
        skip_ai_parsing: bool = False
    ) -> ProcessingResult:
        """
        Complete document processing workflow.
        
        Args:
            document_url: URL to download the document from
            document_name: Optional name for the document
            skip_ai_parsing: Skip AI parsing and only extract text
            
        Returns:
            ProcessingResult with all extracted information
        """
        start_time = datetime.now()
        processing_errors = []
        
        try:
            logger.info(f"Starting document processing for: {document_url}")
            
            # Step 1: Download and validate document
            document_info = await self._download_and_validate(document_url, document_name)
            
            # Step 2: Extract text from PDF
            extracted_text = await self._extract_text_from_pdf(document_info)
            document_info.extracted_text = extracted_text
            document_info.text_quality = self._assess_text_quality(extracted_text)
            
            # Step 3: AI-powered parsing (if enabled)
            contract_data = None
            metadata = None
            
            if not skip_ai_parsing and settings.document_processing.enable_ai_parsing:
                try:
                    # Extract structured data using Gemini
                    contract_data = await self.gemini_service.parse_contract_document(
                        extracted_text, 
                        document_url
                    )
                    
                    # Extract document metadata
                    metadata = await self.gemini_service.extract_document_metadata(extracted_text)
                    
                    logger.info("AI parsing completed successfully")
                    
                except Exception as e:
                    error_msg = f"AI parsing failed: {str(e)}"
                    processing_errors.append(error_msg)
                    logger.error(error_msg)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            document_info.processing_time_ms = int(processing_time)
            document_info.processing_status = "completed" if not processing_errors else "completed_with_errors"
            
            # Determine if document is ready for validation
            validation_ready = (
                extracted_text and 
                len(extracted_text.strip()) > 100 and
                document_info.text_quality in ["good", "fair"]
            )
            
            result = ProcessingResult(
                document_info=document_info,
                contract_data=contract_data,
                extracted_text=extracted_text,
                metadata=metadata,
                validation_ready=validation_ready,
                processing_errors=processing_errors
            )
            
            logger.info(
                f"Document processing completed in {processing_time:.0f}ms. "
                f"Validation ready: {validation_ready}"
            )
            
            return result
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"Document processing failed: {str(e)}"
            logger.error(error_msg)
            
            # Return error result
            return ProcessingResult(
                document_info=DocumentInfo(
                    url=document_url,
                    filename=document_name or "unknown",
                    file_size=0,
                    mime_type="unknown",
                    page_count=0,
                    processing_status="failed",
                    processing_time_ms=int(processing_time),
                    error_message=error_msg
                ),
                processing_errors=[error_msg],
                validation_ready=False
            )
    
    async def _download_and_validate(self, document_url: str, document_name: Optional[str]) -> DocumentInfo:
        """Download document and create DocumentInfo."""
        try:
            logger.info(f"Downloading document from: {document_url}")
            
            # Download the document
            response = await self.http_client.get(document_url)
            response.raise_for_status()
            
            # Extract filename
            if not document_name:
                document_name = Path(document_url).name or "document.pdf"
            
            # Determine mime type
            mime_type = response.headers.get("content-type", "application/octet-stream")
            if not mime_type or mime_type == "application/octet-stream":
                mime_type = mimetypes.guess_type(document_name)[0] or "application/pdf"
            
            # Validate file type
            if not self._is_supported_file_type(mime_type, document_name):
                raise DocumentProcessingError(
                    f"Unsupported file type: {mime_type}",
                    error_code="UNSUPPORTED_FILE_TYPE",
                    details={"mime_type": mime_type, "filename": document_name}
                )
            
            # Validate file size
            file_size = len(response.content)
            max_size = settings.document_processing.max_file_size_mb * 1024 * 1024
            if file_size > max_size:
                raise DocumentProcessingError(
                    f"File too large: {file_size} bytes (max: {max_size})",
                    error_code="FILE_TOO_LARGE",
                    details={"file_size": file_size, "max_size": max_size}
                )
            
            # Save to temporary file for processing
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            async with aiofiles.open(temp_file.name, "wb") as f:
                await f.write(response.content)
            
            # Get page count
            page_count = await self._get_pdf_page_count(temp_file.name)
            
            document_info = DocumentInfo(
                url=document_url,
                filename=document_name,
                file_size=file_size,
                mime_type=mime_type,
                page_count=page_count,
                processing_status="downloaded"
            )
            
            # Store temp file path for later processing
            document_info._temp_file_path = temp_file.name
            
            logger.info(f"Document downloaded: {file_size} bytes, {page_count} pages")
            return document_info
            
        except httpx.RequestError as e:
            raise create_document_processing_error(
                document_id=document_url,
                reason=f"Failed to download document: {str(e)}"
            )
        except Exception as e:
            raise create_document_processing_error(
                document_id=document_url,
                reason=f"Document validation failed: {str(e)}"
            )
    
    async def _extract_text_from_pdf(self, document_info: DocumentInfo) -> str:
        """Extract text from PDF using multiple methods for best quality."""
        temp_file_path = getattr(document_info, '_temp_file_path', None)
        if not temp_file_path:
            raise DocumentProcessingError("No temporary file available for text extraction")
        
        try:
            logger.info(f"Extracting text from PDF: {document_info.filename}")
            
            # Method 1: Try PyMuPDF first (usually better for complex PDFs)
            text_pymupdf = await self._extract_with_pymupdf(temp_file_path)
            
            # Method 2: Try PyPDF2 as fallback
            text_pypdf2 = await self._extract_with_pypdf2(temp_file_path)
            
            # Method 3: Try LangChain PyPDFLoader
            text_langchain = await self._extract_with_langchain(temp_file_path)
            
            # Choose the best extraction result
            extracted_text = self._choose_best_extraction([
                ("pymupdf", text_pymupdf),
                ("pypdf2", text_pypdf2), 
                ("langchain", text_langchain)
            ])
            
            # Clean up temporary file
            try:
                Path(temp_file_path).unlink()
            except Exception:
                pass  # Ignore cleanup errors
            
            if not extracted_text or len(extracted_text.strip()) < 50:
                raise DocumentProcessingError("Insufficient text extracted from PDF")
            
            logger.info(f"Text extraction completed: {len(extracted_text)} characters")
            return extracted_text
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise create_document_processing_error(
                document_id=document_info.url,
                reason=f"Text extraction failed: {str(e)}"
            )
    
    async def _extract_with_pymupdf(self, file_path: str) -> str:
        """Extract text using PyMuPDF."""
        try:
            doc = fitz.open(file_path)
            text_parts = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text_parts.append(page.get_text())
            
            doc.close()
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")
            return ""
    
    async def _extract_with_pypdf2(self, file_path: str) -> str:
        """Extract text using PyPDF2."""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []
                
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                
                return "\n".join(text_parts)
                
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}")
            return ""
    
    async def _extract_with_langchain(self, file_path: str) -> str:
        """Extract text using LangChain PyPDFLoader."""
        try:
            loader = PyPDFLoader(file_path)
            pages = await asyncio.get_event_loop().run_in_executor(None, loader.load)
            
            text_parts = [page.page_content for page in pages]
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.warning(f"LangChain extraction failed: {e}")
            return ""
    
    def _choose_best_extraction(self, extractions: List[tuple]) -> str:
        """Choose the best text extraction result."""
        # Score each extraction method
        scored_extractions = []
        
        for method, text in extractions:
            if not text:
                continue
                
            # Simple scoring based on length and quality indicators
            score = len(text)
            
            # Bonus for containing common contract keywords
            contract_keywords = ["agreement", "contract", "signature", "payment", "terms"]
            keyword_count = sum(1 for keyword in contract_keywords if keyword.lower() in text.lower())
            score += keyword_count * 100
            
            # Penalty for too many special characters (indicates poor extraction)
            special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
            if special_char_ratio > 0.3:
                score *= 0.5
            
            scored_extractions.append((score, method, text))
        
        if not scored_extractions:
            return ""
        
        # Return the highest scoring extraction
        best_score, best_method, best_text = max(scored_extractions, key=lambda x: x[0])
        logger.info(f"Best extraction method: {best_method} (score: {best_score:.0f})")
        
        return best_text
    
    async def _get_pdf_page_count(self, file_path: str) -> int:
        """Get the number of pages in a PDF."""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages)
        except Exception:
            return 0
    
    def _is_supported_file_type(self, mime_type: str, filename: str) -> bool:
        """Check if the file type is supported."""
        supported_types = [
            "application/pdf",
            "application/x-pdf",
        ]
        
        supported_extensions = [".pdf"]
        
        return (
            mime_type in supported_types or
            any(filename.lower().endswith(ext) for ext in supported_extensions)
        )
    
    def _assess_text_quality(self, text: str) -> str:
        """Assess the quality of extracted text."""
        if not text:
            return "poor"
        
        # Calculate various quality metrics
        total_chars = len(text)
        alpha_chars = sum(1 for c in text if c.isalpha())
        digit_chars = sum(1 for c in text if c.isdigit())
        space_chars = sum(1 for c in text if c.isspace())
        
        if total_chars < 100:
            return "poor"
        
        # Calculate ratios
        alpha_ratio = alpha_chars / total_chars
        readable_ratio = (alpha_chars + digit_chars + space_chars) / total_chars
        
        # Quality assessment
        if readable_ratio > 0.8 and alpha_ratio > 0.3:
            return "good"
        elif readable_ratio > 0.6 and alpha_ratio > 0.2:
            return "fair"
        else:
            return "poor"
    
    async def process_multiple_documents(
        self, 
        document_urls: List[str],
        max_concurrent: int = 3
    ) -> List[ProcessingResult]:
        """Process multiple documents concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(url: str) -> ProcessingResult:
            async with semaphore:
                return await self.process_document(url)
        
        tasks = [process_with_semaphore(url) for url in document_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ProcessingResult(
                    document_info=DocumentInfo(
                        url=document_urls[i],
                        filename="unknown",
                        file_size=0,
                        mime_type="unknown",
                        page_count=0,
                        processing_status="failed",
                        error_message=str(result)
                    ),
                    validation_ready=False,
                    processing_errors=[str(result)]
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the document processor."""
        try:
            # Test basic functionality
            test_result = {
                "status": "healthy",
                "services": {
                    "gemini": await self.gemini_service.health_check(),
                    "http_client": "healthy" if self.http_client else "unhealthy"
                },
                "settings": {
                    "max_file_size_mb": settings.document_processing.max_file_size_mb,
                    "ai_parsing_enabled": settings.document_processing.enable_ai_parsing,
                    "processing_timeout": settings.document_processing.processing_timeout
                }
            }
            
            return test_result
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.http_client.aclose()


# Global document processor instance
_document_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Get the global document processor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


# Convenience function
async def process_document_from_url(
    document_url: str,
    document_name: Optional[str] = None
) -> ProcessingResult:
    """Process a single document from URL."""
    processor = get_document_processor()
    return await processor.process_document(document_url, document_name) 