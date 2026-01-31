#!/usr/bin/env python3
"""
LLM Wrapper for SportSQL

Provides a unified interface to switch between different LLM providers:
- Gemini (default)
- OpenAI GPT

Usage:
    from src.llm.wrapper import LLMWrapper
    
    llm = LLMWrapper(provider='gemini')  # or 'openai'
    response = llm.generate_content(prompt)
"""

import os
import sys
import argparse
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class LLMWrapper:
    """Unified interface for different LLM providers."""
    
    SUPPORTED_PROVIDERS = ['gemini', 'openai', 'gpt']
    
    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize LLM wrapper.
        
        Args:
            provider: 'gemini' or 'openai'/'gpt' (auto-detected from CLI if None)
            model: Specific model name (uses defaults if None)
        """
        self.provider = provider or self._detect_provider()
        self.model_name = model or self._get_default_model()
        self.client = None
        
        # Validate provider
        if self.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {self.provider}. Use: {self.SUPPORTED_PROVIDERS}")
        
        # Normalize provider name
        if self.provider in ['openai', 'gpt']:
            self.provider = 'openai'
        
        # Initialize the appropriate client
        self._initialize_client()
        
        print(f"🤖 LLM Provider: {self.provider.upper()}")
        print(f"📋 Model: {self.model_name}")
    
    def _detect_provider(self) -> str:
        """Auto-detect LLM provider from command line arguments or environment."""
        # Check for explicit command line argument
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--llm', '--llm-provider', 
                           choices=['gemini', 'openai', 'gpt'], 
                           default='openai',
                           help='LLM provider to use')
        args, _ = parser.parse_known_args()
        
        # Check environment variable override
        env_provider = os.getenv('LLM_PROVIDER', '').lower()
        if env_provider in self.SUPPORTED_PROVIDERS:
            return env_provider
        
        return args.llm
    
    def _get_default_model(self) -> str:
        """Get default model for the provider."""
        defaults = {
            'gemini': os.getenv('GEMINI_MODEL', 'gemini-2.0-flash'),
            'openai': os.getenv('GPT_MODEL', 'gpt-4o')
        }
        return defaults.get(self.provider, 'gemini-2.0-flash')
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == 'gemini':
            self._initialize_gemini()
        elif self.provider == 'openai':
            self._initialize_openai()
    
    def _initialize_gemini(self):
        """Initialize Gemini client."""
        try:
            import google.generativeai as genai
            
            api_key = os.getenv("API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API key not found. Set API_KEY or GEMINI_API_KEY environment variable.")
            
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model_name)
            self._client_type = 'gemini'
            
        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini: {e}")
    
    def _initialize_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            
            self.client = OpenAI(api_key=api_key)
            self._client_type = 'openai'
            
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI: {e}")
    
    def generate_content(self, prompt: str, timeout: int = 30, **kwargs) -> str:
        """
        Generate content using the configured LLM.
        
        Args:
            prompt: Input prompt
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Generated text content
        """
        try:
            if self.provider == 'gemini':
                return self._generate_gemini(prompt, timeout, **kwargs)
            elif self.provider == 'openai':
                return self._generate_openai(prompt, timeout, **kwargs)
        except Exception as e:
            print(f"❌ LLM generation error ({self.provider}): {e}")
            raise
    
    def _generate_gemini(self, prompt: str, timeout: int, **kwargs) -> str:
        """Generate content using Gemini."""
        response = self.client.generate_content(
            prompt,
            request_options={"timeout": timeout},
            **kwargs
        )
        return response.text
    
    def _generate_openai(self, prompt: str, timeout: int, **kwargs) -> str:
        """Generate content using OpenAI."""
        # Extract OpenAI-specific parameters
        temperature = kwargs.get('temperature', 0.1)
        max_tokens = kwargs.get('max_tokens', 2000)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
        return response.choices[0].message.content
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        return {
            'provider': self.provider,
            'model': self.model_name,
            'client_type': self._client_type,
            'available': self.client is not None
        }


# Convenience functions for backward compatibility
def get_llm_client(provider: str = None, model: str = None) -> LLMWrapper:
    """Get an LLM client instance."""
    return LLMWrapper(provider=provider, model=model)

def generate_with_llm(prompt: str, provider: str = None, timeout: int = 30, **kwargs) -> str:
    """Generate content with the specified LLM provider."""
    llm = LLMWrapper(provider=provider)
    return llm.generate_content(prompt, timeout=timeout, **kwargs)


# Global instance for easy access
_global_llm = None

def get_global_llm() -> LLMWrapper:
    """Get or create global LLM instance."""
    global _global_llm
    if _global_llm is None:
        _global_llm = LLMWrapper()
    return _global_llm

def set_global_llm_provider(provider: str, model: str = None):
    """Set the global LLM provider."""
    global _global_llm
    _global_llm = LLMWrapper(provider=provider, model=model)


# CLI for testing
def main():
    """Test the LLM wrapper."""
    parser = argparse.ArgumentParser(description='Test LLM Wrapper')
    parser.add_argument('--llm', choices=['gemini', 'openai', 'gpt'], default='gpt',
                       help='LLM provider to test')
    parser.add_argument('--model', help='Specific model to use')
    parser.add_argument('--prompt', default='Write a simple SQL query to count all players.',
                       help='Test prompt')
    
    args = parser.parse_args()
    
    print("🧪 Testing LLM Wrapper")
    print("=" * 50)
    
    try:
        llm = LLMWrapper(provider=args.llm, model=args.model)
        
        print(f"📝 Test prompt: {args.prompt}")
        print("🔄 Generating response...")
        
        response = llm.generate_content(args.prompt, timeout=30)
        
        print("✅ Response:")
        print(response)
        print("\n" + "=" * 50)
        print(f"Provider info: {llm.get_provider_info()}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
