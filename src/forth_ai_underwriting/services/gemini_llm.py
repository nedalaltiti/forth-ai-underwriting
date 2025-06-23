"""
Gemini LLM Service implementation.
Clean implementation of the LLMService interface for Google Gemini.
"""

import json
import asyncio
from typing import Dict, Optional, AsyncGenerator
import google.generativeai as genai
from loguru import logger

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.services.llm_service import LLMService, LLMResult
from forth_ai_underwriting.utils.retry import retry_ai_api


class GeminiProvider(LLMService):
    """Gemini implementation of the LLM service."""
    
    def __init__(self):
        """Initialize Gemini service with configuration."""
        self.model_name = settings.gemini.model_name
        self.temperature = settings.gemini.temperature
        self.max_tokens = settings.gemini.max_output_tokens
        
        # Configure Gemini
        if settings.gemini.use_aws_secrets and settings.gemini.credentials_path:
            # Use service account from AWS Secrets Manager
            import os
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.gemini.credentials_path
            logger.info("Using Gemini credentials from AWS Secrets Manager")
        else:
            # Use API key
            genai.configure(api_key=settings.gemini.api_key)
            logger.info("Using Gemini with API key")
        
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"GeminiProvider initialized with model: {self.model_name}")
    
    @retry_ai_api
    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResult:
        """Generate text using Gemini."""
        try:
            # Prepare the prompt
            full_prompt = self._prepare_prompt(prompt, system_prompt)
            
            # Generate content
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": temperature or self.temperature,
                    "max_output_tokens": max_tokens or self.max_tokens,
                }
            )
            
            return LLMResult(
                success=True,
                content=response.text,
                metadata={
                    "model": self.model_name,
                    "usage": self._extract_usage(response)
                }
            )
            
        except Exception as e:
            logger.error(f"Gemini text generation failed: {e}")
            return LLMResult(
                success=False,
                error=str(e)
            )
    
    @retry_ai_api
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict] = None
    ) -> LLMResult:
        """Generate JSON using Gemini."""
        try:
            # Add JSON formatting instructions
            json_prompt = prompt + "\n\nProvide your response as valid JSON."
            if schema:
                json_prompt += f"\n\nExpected schema: {json.dumps(schema, indent=2)}"
            
            full_prompt = self._prepare_prompt(json_prompt, system_prompt)
            
            # Generate content
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": 0.0,  # Use low temperature for structured output
                    "max_output_tokens": self.max_tokens,
                }
            )
            
            # Parse JSON from response
            content = response.text
            parsed_data = self._parse_json_response(content)
            
            if isinstance(parsed_data, dict):
                return LLMResult(
                    success=True,
                    data=parsed_data,
                    content=content,
                    metadata={
                        "model": self.model_name,
                        "usage": self._extract_usage(response)
                    }
                )
            else:
                return LLMResult(
                    success=False,
                    content=content,
                    error="Failed to parse JSON from response"
                )
                
        except Exception as e:
            logger.error(f"Gemini JSON generation failed: {e}")
            return LLMResult(
                success=False,
                error=str(e)
            )
    
    async def generate_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate text with streaming (simulated for Gemini)."""
        # Gemini doesn't have true streaming in the Python SDK yet
        # Simulate streaming by generating full response and yielding chunks
        result = await self.generate_text(prompt, system_prompt)
        
        if result.success and result.content:
            chunk_size = 50
            for i in range(0, len(result.content), chunk_size):
                yield result.content[i:i + chunk_size]
                await asyncio.sleep(0.05)  # Small delay to simulate streaming
        elif not result.success:
            yield f"Error: {result.error}"
    
    async def test_connection(self) -> bool:
        """Test Gemini connection."""
        try:
            response = await self.generate_text(
                "Hello, please respond with 'OK' if you can read this.",
                temperature=0.0
            )
            return response.success
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
    
    def _prepare_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Prepare the full prompt with system instructions."""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from response, handling markdown code blocks."""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                if json_end != -1:
                    content = content[json_start:json_end].strip()
            elif "```" in content:
                # Generic code block
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                if json_end != -1:
                    content = content[json_start:json_end].strip()
            
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return {"error": "JSON parsing failed", "raw_content": content}
    
    def _extract_usage(self, response) -> Dict:
        """Extract token usage information from response."""
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