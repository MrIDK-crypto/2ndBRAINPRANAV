"""
OpenAI Client Wrapper
Supports both Azure OpenAI and regular OpenAI APIs
"""
import os
from typing import Optional
from openai import OpenAI, AzureOpenAI


class OpenAIClientWrapper:
    """Wrapper that works with both Azure OpenAI and regular OpenAI"""

    def __init__(self, timeout: float = None):
        """
        Initialize OpenAI client wrapper.

        Args:
            timeout: Optional timeout in seconds for API calls. If None, uses SDK default.
        """
        self.use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"

        if self.use_azure:
            # Azure OpenAI configuration
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_kwargs = {
                "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                "api_version": os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
            }
            if timeout:
                azure_kwargs["timeout"] = timeout

            # Handle Azure AI Services project endpoints
            if "/api/projects/" in endpoint:
                # Remove trailing path for SDK compatibility
                base_endpoint = endpoint.split("/api/projects/")[0]
                azure_kwargs["azure_endpoint"] = base_endpoint
                azure_kwargs["default_headers"] = {"api-project": endpoint.split("/api/projects/")[1]}
            else:
                azure_kwargs["azure_endpoint"] = endpoint

            self.client = AzureOpenAI(**azure_kwargs)
            self.chat_model = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4")
            self.embedding_model = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        else:
            # Regular OpenAI configuration
            openai_kwargs = {
                "api_key": os.getenv("OPENAI_API_KEY")
            }
            if timeout:
                openai_kwargs["timeout"] = timeout

            self.client = OpenAI(**openai_kwargs)
            self.chat_model = "gpt-4o-mini"  # More cost-effective for development
            self.embedding_model = "text-embedding-3-large"

    def chat_completion(self, messages, temperature=0.7, max_tokens=None, **kwargs):
        """Create a chat completion"""
        params = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        return self.client.chat.completions.create(**params)

    def chat_completion_stream(self, messages, temperature=0.7, max_tokens=None, **kwargs):
        """Create a streaming chat completion - yields chunks as they arrive"""
        params = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        return self.client.chat.completions.create(**params)

    def create_embedding(self, text, dimensions=1536):
        """Create embeddings"""
        params = {
            "model": self.embedding_model,
            "input": text,
            "dimensions": dimensions  # text-embedding-3-large supports dimensions on both OpenAI and Azure
        }

        return self.client.embeddings.create(**params)

    def get_chat_model(self):
        """Get the chat model name"""
        return self.chat_model

    def get_embedding_model(self):
        """Get the embedding model name"""
        return self.embedding_model

    @property
    def embeddings(self):
        """Expose the underlying client's embeddings API for direct access"""
        return self.client.embeddings

    @property
    def audio(self):
        """Expose the underlying client's audio API for Whisper transcription"""
        return self.client.audio


# Singleton instance
_client = None
_client_with_timeout = None

def get_openai_client() -> OpenAIClientWrapper:
    """Get or create the OpenAI client singleton"""
    global _client
    if _client is None:
        _client = OpenAIClientWrapper()
    return _client


def get_openai_client_with_timeout(timeout: float = 120.0) -> OpenAIClientWrapper:
    """
    Get OpenAI client with extended timeout for long-running operations.
    Use this for services like Protocol Optimizer that make multiple sequential API calls.
    """
    global _client_with_timeout
    if _client_with_timeout is None:
        _client_with_timeout = OpenAIClientWrapper(timeout=timeout)
    return _client_with_timeout
