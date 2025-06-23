"""
Prompt management system with templating, versioning, and validation.
"""

from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator
import json
from pathlib import Path
from datetime import datetime
from loguru import logger


class PromptCategory(str, Enum):
    """Categories of prompts for organization."""
    CONTRACT_PARSING = "contract_parsing"
    HARDSHIP_ASSESSMENT = "hardship_assessment"
    BUDGET_ANALYSIS = "budget_analysis"
    DEBT_VALIDATION = "debt_validation"
    DOCUMENT_METADATA = "document_metadata"
    GENERAL_VALIDATION = "general_validation"


class PromptVersion(str, Enum):
    """Prompt versions for A/B testing and rollbacks."""
    V1_0 = "v1.0"
    V1_1 = "v1.1"
    V2_0 = "v2.0"
    LATEST = "latest"


class PromptTemplate(BaseModel):
    """
    Pydantic model for prompt templates with validation.
    """
    name: str = Field(..., description="Unique prompt name")
    category: PromptCategory = Field(..., description="Prompt category")
    version: PromptVersion = Field(default=PromptVersion.LATEST, description="Prompt version")
    system_prompt: str = Field(..., min_length=10, description="System/role prompt")
    user_prompt_template: str = Field(..., min_length=10, description="User prompt template with placeholders")
    format_instructions: Optional[str] = Field(None, description="Output format instructions")
    required_variables: List[str] = Field(default_factory=list, description="Required template variables")
    optional_variables: List[str] = Field(default_factory=list, description="Optional template variables")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Expected output schema")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Example inputs/outputs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('user_prompt_template')
    def validate_template_variables(cls, v, values):
        """Validate that template variables are properly formatted."""
        import re
        # Find all template variables in the format {variable_name}
        variables_in_template = set(re.findall(r'\{(\w+)\}', v))
        required_vars = set(values.get('required_variables', []))
        optional_vars = set(values.get('optional_variables', []))
        all_expected_vars = required_vars | optional_vars
        
        # Check for undefined variables
        undefined_vars = variables_in_template - all_expected_vars
        if undefined_vars:
            raise ValueError(f"Template contains undefined variables: {undefined_vars}")
        
        # Check for missing required variables
        missing_required = required_vars - variables_in_template
        if missing_required:
            raise ValueError(f"Template missing required variables: {missing_required}")
        
        return v
    
    def render(self, **kwargs) -> Dict[str, str]:
        """
        Render the prompt template with provided variables.
        
        Returns:
            Dict with 'system_prompt', 'user_prompt', and optionally 'format_instructions'
        """
        # Validate required variables
        missing_required = set(self.required_variables) - set(kwargs.keys())
        if missing_required:
            raise ValueError(f"Missing required variables: {missing_required}")
        
        # Render user prompt
        try:
            user_prompt = self.user_prompt_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Template variable not provided: {e}")
        
        result = {
            "system_prompt": self.system_prompt,
            "user_prompt": user_prompt
        }
        
        if self.format_instructions:
            result["format_instructions"] = self.format_instructions
        
        return result


class PromptManager:
    """
    Centralized prompt management with caching and validation.
    """
    
    def __init__(self):
        self._prompts: Dict[str, PromptTemplate] = {}
        self._category_index: Dict[PromptCategory, List[str]] = {}
        self._version_index: Dict[str, Dict[PromptVersion, str]] = {}
        self._initialize_default_prompts()
        logger.info("PromptManager initialized with default prompts")
    
    def register_prompt(self, prompt: PromptTemplate) -> None:
        """Register a new prompt template."""
        prompt_key = f"{prompt.name}_{prompt.version}"
        self._prompts[prompt_key] = prompt
        
        # Update category index
        if prompt.category not in self._category_index:
            self._category_index[prompt.category] = []
        if prompt_key not in self._category_index[prompt.category]:
            self._category_index[prompt.category].append(prompt_key)
        
        # Update version index
        if prompt.name not in self._version_index:
            self._version_index[prompt.name] = {}
        self._version_index[prompt.name][prompt.version] = prompt_key
        
        logger.debug(f"Registered prompt: {prompt.name} v{prompt.version}")
    
    def get_prompt(
        self, 
        name: str, 
        version: PromptVersion = PromptVersion.LATEST
    ) -> Optional[PromptTemplate]:
        """Get a prompt template by name and version."""
        if version == PromptVersion.LATEST:
            # Get the latest version
            if name in self._version_index:
                versions = list(self._version_index[name].keys())
                # Sort versions and get the latest
                latest_version = max(versions, key=lambda v: v.value)
                prompt_key = self._version_index[name][latest_version]
            else:
                return None
        else:
            prompt_key = f"{name}_{version}"
        
        return self._prompts.get(prompt_key)
    
    def get_prompts_by_category(self, category: PromptCategory) -> List[PromptTemplate]:
        """Get all prompts in a category."""
        if category not in self._category_index:
            return []
        
        return [self._prompts[key] for key in self._category_index[category]]
    
    def render_prompt(
        self, 
        name: str, 
        version: PromptVersion = PromptVersion.LATEST,
        **kwargs
    ) -> Dict[str, str]:
        """Render a prompt with variables."""
        prompt = self.get_prompt(name, version)
        if not prompt:
            raise ValueError(f"Prompt '{name}' version '{version}' not found")
        
        return prompt.render(**kwargs)
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all available prompts with metadata."""
        return [
            {
                "name": prompt.name,
                "category": prompt.category.value,
                "version": prompt.version.value,
                "required_variables": prompt.required_variables,
                "optional_variables": prompt.optional_variables
            }
            for prompt in self._prompts.values()
        ]
    
    def validate_prompt_output(
        self, 
        prompt_name: str, 
        output: Any,
        version: PromptVersion = PromptVersion.LATEST
    ) -> bool:
        """Validate prompt output against expected schema."""
        prompt = self.get_prompt(prompt_name, version)
        if not prompt or not prompt.output_schema:
            return True  # No schema to validate against
        
        try:
            # Create a dynamic Pydantic model from the schema
            from pydantic import create_model
            DynamicModel = create_model('DynamicModel', **prompt.output_schema)
            DynamicModel.parse_obj(output)
            return True
        except Exception as e:
            logger.error(f"Prompt output validation failed for {prompt_name}: {e}")
            return False
    
    def _initialize_default_prompts(self):
        """Initialize default prompt templates."""
        # This will be populated by the specific prompt modules
        pass
    
    def export_prompts(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Export all prompts to JSON format."""
        export_data = {
            "prompts": [prompt.dict() for prompt in self._prompts.values()],
            "metadata": {
                "total_prompts": len(self._prompts),
                "categories": list(self._category_index.keys()),
                "export_timestamp": str(datetime.now())
            }
        }
        
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            logger.info(f"Prompts exported to {file_path}")
        
        return export_data
    
    def import_prompts(self, file_path: str) -> None:
        """Import prompts from JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            for prompt_data in data.get("prompts", []):
                prompt = PromptTemplate.parse_obj(prompt_data)
                self.register_prompt(prompt)
            
            logger.info(f"Imported {len(data.get('prompts', []))} prompts from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import prompts from {file_path}: {e}")
            raise


# Global prompt manager instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


# Convenience functions
def render_prompt(name: str, **kwargs) -> Dict[str, str]:
    """Convenience function to render a prompt."""
    return get_prompt_manager().render_prompt(name, **kwargs)


def get_prompt_template(name: str, version: PromptVersion = PromptVersion.LATEST) -> Optional[PromptTemplate]:
    """Convenience function to get a prompt template."""
    return get_prompt_manager().get_prompt(name, version) 