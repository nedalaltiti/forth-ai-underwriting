"""
LLM Service interface for AI-powered text generation.
Clean, simple interface following SOLID principles.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass
from loguru import logger


@dataclass
class LLMResult:
    """Result from LLM analysis."""
    success: bool
    content: Optional[str] = None
    data: Optional[Dict] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class LLMService(ABC):
    """Abstract base class for LLM services."""
    
    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResult:
        """
        Generate text based on a prompt.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system/role prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            LLMResult with generated text or error
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict] = None
    ) -> LLMResult:
        """
        Generate structured JSON output.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system/role prompt
            schema: Optional JSON schema to validate against
            
        Returns:
            LLMResult with parsed JSON data or error
        """
        pass
    
    @abstractmethod
    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate text with streaming output.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system/role prompt
            
        Yields:
            Chunks of generated text
        """
        yield "Streaming not implemented"
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the LLM service is accessible."""
        pass


# Singleton instance holder
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the configured LLM service instance."""
    global _llm_service
    
    if _llm_service is None:
        # Import here to avoid circular imports
        from forth_ai_underwriting.config.settings import settings
        
        # Choose implementation based on configuration
        if settings.llm.provider == "gemini":
            from forth_ai_underwriting.services.gemini_llm import GeminiProvider
            _llm_service = GeminiProvider()
        else:
            logger.warning(f"Unknown LLM provider: {settings.llm.provider}, using Gemini as default")
            from forth_ai_underwriting.services.gemini_llm import GeminiProvider
            _llm_service = GeminiProvider()
    
    return _llm_service 