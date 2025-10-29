"""
Local LLM service for RAG system using CUDA-accelerated models.
Supports Ollama and direct model loading with transformers.
"""

import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import torch
from sentence_transformers import SentenceTransformer


class ModelBackend(Enum):
    """Available model backends"""

    OLLAMA = "ollama"
    TRANSFORMERS = "transformers"
    LLAMACPP = "llamacpp"


class LocalEmbeddings:
    """Generate embeddings using local models with CUDA acceleration"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        """
        Initialize local embeddings service.

        Args:
            model_name: HuggingFace model name for embeddings
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        # Auto-detect CUDA
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.model_name = model_name

        print(f"Loading embedding model '{model_name}' on {device}...")
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()

        print(f"✓ Model loaded (dimension: {self.dimension})")

        # Show GPU info if available
        if device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"  GPU: {gpu_name} ({gpu_memory:.1f} GB)")

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        with torch.no_grad():
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()

    def generate_embeddings_batch(
        self, texts: list[str], batch_size: int = 32, show_progress: bool = False
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            show_progress: Show progress bar

        Returns:
            List of embedding vectors
        """
        # Filter out empty texts
        texts = [text if text and text.strip() else " " for text in texts]

        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_tensor=False,
            )

            return embeddings.tolist()


class LocalLLM:
    """Local LLM for text generation using CUDA"""

    def __init__(
        self,
        model_name: str = "llama3.2:3b",
        backend: ModelBackend = ModelBackend.OLLAMA,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        """
        Initialize local LLM.

        Args:
            model_name: Model identifier
            backend: Backend to use (ollama, transformers, llamacpp)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.model_name = model_name
        self.backend = backend
        self.temperature = temperature
        self.max_tokens = max_tokens

        if backend == ModelBackend.OLLAMA:
            self._init_ollama()
        elif backend == ModelBackend.TRANSFORMERS:
            self._init_transformers()
        elif backend == ModelBackend.LLAMACPP:
            self._init_llamacpp()
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def _init_ollama(self):
        """Initialize Ollama client"""
        try:
            import ollama

            self.client = ollama

            # Test connection
            models = self.client.list()
            print(
                f"✓ Ollama connected ({len(models.get('models', []))} models available)"
            )

            # Check if our model exists
            model_names = [m["name"] for m in models.get("models", [])]
            if self.model_name not in model_names:
                print(f"⚠ Model '{self.model_name}' not found. Available models:")
                for name in model_names:
                    print(f"  - {name}")
                print(f"\nTo pull the model, run: ollama pull {self.model_name}")
            else:
                print(f"✓ Model '{self.model_name}' ready")

        except ImportError:
            raise ImportError("Ollama package not installed. Run: pip install ollama")
        except Exception as e:
            print(f"⚠ Ollama connection error: {e}")
            print("Make sure Ollama is running: ollama serve")

    def _init_transformers(self):
        """Initialize transformers model with GPU support"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading model '{self.model_name}' on {device}...")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                low_cpu_mem_usage=True,
            )

            print(f"✓ Model loaded on {device}")

        except ImportError:
            raise ImportError(
                "Transformers not installed. Run: pip install transformers accelerate"
            )

    def _init_llamacpp(self):
        """Initialize llama.cpp with GPU acceleration"""
        try:
            from llama_cpp import Llama

            # Assumes model is downloaded locally
            model_path = os.getenv(
                "LLAMA_MODEL_PATH", f"./models/{self.model_name}.gguf"
            )

            n_gpu_layers = 35 if torch.cuda.is_available() else 0

            print(f"Loading llama.cpp model from {model_path}...")
            self.model = Llama(
                model_path=model_path,
                n_gpu_layers=n_gpu_layers,
                n_ctx=4096,
                verbose=False,
            )

            print(f"✓ Model loaded (GPU layers: {n_gpu_layers})")

        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Run: pip install llama-cpp-python"
            )
        except Exception as e:
            print(f"Error loading model: {e}")
            raise

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        if self.backend == ModelBackend.OLLAMA:
            return self._generate_ollama(prompt, system_prompt, **kwargs)
        elif self.backend == ModelBackend.TRANSFORMERS:
            return self._generate_transformers(prompt, system_prompt, **kwargs)
        elif self.backend == ModelBackend.LLAMACPP:
            return self._generate_llamacpp(prompt, system_prompt, **kwargs)

    def _generate_ollama(self, prompt: str, system_prompt: Optional[str], **kwargs) -> str:
        """Generate using Ollama"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                },
            )

            return response["message"]["content"]

        except Exception as e:
            return f"Error generating response: {e}"

    def _generate_transformers(
        self, prompt: str, system_prompt: Optional[str], **kwargs
    ) -> str:
        """Generate using transformers"""
        # Format prompt with system message if provided
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:" if system_prompt else prompt

        inputs = self.tokenizer(full_prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove the prompt from response
        if response.startswith(full_prompt):
            response = response[len(full_prompt) :].strip()

        return response

    def _generate_llamacpp(
        self, prompt: str, system_prompt: Optional[str], **kwargs
    ) -> str:
        """Generate using llama.cpp"""
        # Format with system prompt if provided
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:" if system_prompt else prompt

        response = self.model(
            full_prompt,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            stop=["User:", "\n\n"],
        )

        return response["choices"][0]["text"].strip()


# Convenience functions
def create_local_embeddings(model_name: str = "all-MiniLM-L6-v2") -> LocalEmbeddings:
    """
    Create local embeddings service.

    Recommended models:
    - all-MiniLM-L6-v2: Fast, 384 dim (default)
    - all-mpnet-base-v2: Better quality, 768 dim
    - all-MiniLM-L12-v2: Balanced, 384 dim
    """
    return LocalEmbeddings(model_name=model_name)


def create_local_llm(
    model_name: str = "llama3.2:3b", backend: str = "ollama"
) -> LocalLLM:
    """
    Create local LLM service.

    Recommended Ollama models:
    - llama3.2:3b: Small, fast (3B params)
    - llama3.2:1b: Tiny, very fast (1B params)
    - mistral:7b: Good quality (7B params)
    - phi3:mini: Fast, good (3.8B params)

    Args:
        model_name: Model identifier
        backend: 'ollama', 'transformers', or 'llamacpp'
    """
    backend_enum = ModelBackend(backend)
    return LocalLLM(model_name=model_name, backend=backend_enum)


def check_cuda_availability() -> dict[str, Any]:
    """Check CUDA availability and GPU info"""
    info = {
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "devices": [],
    }

    if info["cuda_available"]:
        for i in range(info["device_count"]):
            device_info = {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "total_memory_gb": torch.cuda.get_device_properties(i).total_memory
                / 1e9,
                "compute_capability": torch.cuda.get_device_capability(i),
            }
            info["devices"].append(device_info)

    return info


if __name__ == "__main__":
    # Test script
    print("=" * 60)
    print("Local LLM Service Test")
    print("=" * 60)

    # Check CUDA
    cuda_info = check_cuda_availability()
    print(f"\nCUDA Available: {cuda_info['cuda_available']}")
    if cuda_info["cuda_available"]:
        print(f"CUDA Version: {cuda_info['cuda_version']}")
        print(f"GPUs: {cuda_info['device_count']}")
        for device in cuda_info["devices"]:
            print(
                f"  [{device['index']}] {device['name']} ({device['total_memory_gb']:.1f} GB)"
            )

    # Test embeddings
    print("\n" + "-" * 60)
    print("Testing Local Embeddings...")
    print("-" * 60)

    embeddings = create_local_embeddings()
    test_text = "Bitcoin shows strong support at 42k level"
    embedding = embeddings.generate_embedding(test_text)
    print(f"Text: {test_text}")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    # Test LLM (if Ollama is available)
    print("\n" + "-" * 60)
    print("Testing Local LLM...")
    print("-" * 60)

    try:
        llm = create_local_llm()
        response = llm.generate(
            prompt="What is a good trading strategy for Bitcoin?",
            system_prompt="You are a helpful trading assistant.",
            max_tokens=100,
        )
        print(f"Response: {response}")
    except Exception as e:
        print(f"LLM test skipped: {e}")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
