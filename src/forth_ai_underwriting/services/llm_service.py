"""
Clean LLM service providing unified interface to multiple AI providers.
Handles provider management, fallback logic, and standardized responses.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from loguru import logger

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.utils.retry import retry_ai_api
from forth_ai_underwriting.core.exceptions import AIProviderError, RateLimitError


class LLMProvider(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Standardized LLM response format."""
    content: str
    provider: str
    model: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any]
    confidence: Optional[float] = None


@dataclass
class LLMRequest:
    """Standardized LLM request format."""
    prompt: str
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    format_instructions: Optional[str] = None
    output_format: str = "text"  # "text" or "json"
    stream: bool = False


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.is_available = True
        self.error_count = 0
        self.max_errors = 5
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from the LLM."""
        pass
    
    @abstractmethod
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate streaming response from the LLM."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model."""
        pass
    
    def handle_error(self, error: Exception):
        """Handle errors and update availability status."""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.is_available = False
            logger.warning(f"Provider {self.provider_name} marked as unavailable due to errors")
    
    def reset_errors(self):
        """Reset error count when provider recovers."""
        self.error_count = 0
        self.is_available = True


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementation."""
    
    def __init__(self):
        super().__init__("gemini")
        self.model_name = settings.gemini_model_name
        self.temperature = settings.gemini_temperature
        self.max_tokens = settings.gemini_max_output_tokens
        
        # Initialize Gemini client lazily
        self._client = None
        logger.info(f"GeminiProvider initialized with model: {self.model_name}")
    
    def _get_client(self):
        """Get or initialize Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                self._client = genai.GenerativeModel(self.model_name)
            except ImportError:
                raise AIProviderError("google-generativeai package not installed")
            except Exception as e:
                raise AIProviderError(f"Failed to initialize Gemini client: {str(e)}")
        return self._client
    
    @retry_ai_api
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Gemini."""
        try:
            client = self._get_client()
            
            # Prepare the prompt
            full_prompt = self._prepare_prompt(request)
            
            # Generate content
            response = await asyncio.to_thread(
                client.generate_content,
                full_prompt,
                generation_config={
                    "temperature": request.temperature or self.temperature,
                    "max_output_tokens": request.max_tokens or self.max_tokens,
                }
            )
            
            content = response.text
            
            # Parse JSON if requested
            if request.output_format == "json":
                content = self._parse_json_response(content)
            
            # Reset errors on success
            self.reset_errors()
            
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=self.model_name,
                usage=self._extract_usage(response),
                metadata={"finish_reason": "completed"}
            )
            
        except Exception as e:
            self.handle_error(e)
            if "rate limit" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit exceeded: {str(e)}")
            raise AIProviderError(f"Gemini generation failed: {str(e)}")
    
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream generate response using Gemini."""
        try:
            client = self._get_client()
            full_prompt = self._prepare_prompt(request)
            
            # Note: Gemini streaming implementation would go here
            # For now, simulate streaming with regular generation
            response = await self.generate(request)
            
            # Simulate streaming by yielding chunks
            content = response.content if isinstance(response.content, str) else str(response.content)
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]
                await asyncio.sleep(0.1)  # Simulate network delay
                
        except Exception as e:
            self.handle_error(e)
            raise AIProviderError(f"Gemini streaming failed: {str(e)}")
    
    def _prepare_prompt(self, request: LLMRequest) -> str:
        """Prepare prompt for Gemini."""
        prompt_parts = []
        
        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}")
        
        prompt_parts.append(f"User: {request.prompt}")
        
        if request.format_instructions and request.output_format == "json":
            prompt_parts.append(f"Format: {request.format_instructions}")
        
        return "\n\n".join(prompt_parts)
    
    def _parse_json_response(self, content: str) -> Union[Dict[str, Any], str]:
        """Parse JSON response, return original if parsing fails."""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                if json_end != -1:
                    content = content[json_start:json_end].strip()
            
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response, returning as text")
            return content
    
    def _extract_usage(self, response) -> Dict[str, Any]:
        """Extract usage information from Gemini response."""
        try:
            if hasattr(response, 'usage_metadata'):
                return {
                    "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                    "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                    "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0)
                }
        except:
            pass
        return {"total_tokens": 0}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Gemini model information."""
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "available": self.is_available
        }


class LLMService:
    """
    Unified LLM service managing multiple providers with fallback logic.
    Provides a clean interface for all AI operations.
    """
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.primary_provider = settings.llm_provider
        self.fallback_provider = settings.llm_fallback_provider
        
        self._initialize_providers()
        logger.info(f"LLMService initialized with primary: {self.primary_provider}, fallback: {self.fallback_provider}")
    
    def _initialize_providers(self):
        """Initialize available LLM providers."""
        # Initialize Gemini
        if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
            try:
                self.providers["gemini"] = GeminiProvider()
                logger.info("Gemini provider initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini provider: {e}")
        else:
            logger.info("Gemini provider available but API key not configured")
        
        # Initialize OpenAI (future implementation)
        if settings.openai_api_key and settings.openai_api_key != "your_openai_api_key_here":
            logger.info("OpenAI provider available but not implemented yet")
        
        if not self.providers:
            logger.info("No LLM providers configured - add API keys to enable AI features")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        output_format: str = "text",
        format_instructions: Optional[str] = None,
        provider: Optional[str] = None
    ) -> LLMResponse:
        """
        Generate response using specified or default provider.
        
        Args:
            prompt: User prompt
            system_prompt: System/role prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            output_format: "text" or "json"
            format_instructions: JSON format instructions
            provider: Specific provider to use
            
        Returns:
            LLMResponse with generated content
        """
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            output_format=output_format,
            format_instructions=format_instructions
        )
        
        # Determine provider order
        providers_to_try = []
        if provider and provider in self.providers:
            providers_to_try.append(provider)
        else:
            # Use primary and fallback order
            if self.primary_provider in self.providers:
                providers_to_try.append(self.primary_provider)
            if self.fallback_provider in self.providers and self.fallback_provider != self.primary_provider:
                providers_to_try.append(self.fallback_provider)
        
        # Try providers in order
        last_error = None
        for provider_name in providers_to_try:
            provider_instance = self.providers[provider_name]
            
            if not provider_instance.is_available:
                logger.warning(f"Provider {provider_name} is not available, skipping")
                continue
            
            try:
                logger.debug(f"Attempting generation with provider: {provider_name}")
                response = await provider_instance.generate(request)
                logger.debug(f"Generation successful with provider: {provider_name}")
                return response
                
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                last_error = e
                continue
        
        # All providers failed
        if last_error:
            raise AIProviderError(f"All providers failed. Last error: {str(last_error)}")
        else:
            raise AIProviderError("No available providers")
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return [name for name, provider in self.providers.items() if provider.is_available]
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all providers."""
        health_status = {}
        
        for name, provider in self.providers.items():
            health_status[name] = {
                "available": provider.is_available,
                "error_count": provider.error_count,
                "model_info": provider.get_model_info()
            }
        
        return {
            "status": "healthy" if any(p.is_available for p in self.providers.values()) else "unhealthy",
            "providers": health_status,
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider
        }


# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# Convenience functions for common operations
async def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs
) -> str:
    """Generate text response using the LLM service."""
    llm_service = get_llm_service()
    response = await llm_service.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        output_format="text",
        **kwargs
    )
    return response.content


async def generate_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    format_instructions: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate JSON response using the LLM service."""
    llm_service = get_llm_service()
    response = await llm_service.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        output_format="json",
        format_instructions=format_instructions,
        **kwargs
    )
    
    # Ensure response is a dictionary
    if isinstance(response.content, dict):
        return response.content
    elif isinstance(response.content, str):
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            raise AIProviderError(f"Expected JSON response but got: {response.content}")
    else:
        raise AIProviderError(f"Unexpected response type: {type(response.content)}") 