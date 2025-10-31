"""
Base Agent Factory for Multi-Agent Trading System

Creates Ollama-based agents with configurable prompts and parameters.
"""

from typing import Optional
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable


def create_agent(
    role: str,
    system_prompt: str,
    model: str = "llama3.2:3b",
    temperature: float = 0.7,
    base_url: str = "http://localhost:11434"
) -> Runnable:
    """
    Factory function for creating specialized trading agents.
    
    Args:
        role: Agent role identifier (e.g., "Technical Analyst", "Bull Agent")
        system_prompt: System prompt defining agent behavior and expertise
        model: Ollama model name (default: llama3.2:3b)
        temperature: Sampling temperature (0-1, higher = more creative)
        base_url: Ollama API base URL
        
    Returns:
        Configured LangChain Runnable (prompt | LLM chain)
        
    Example:
        >>> technical_agent = create_agent(
        ...     role="Technical Analyst",
        ...     system_prompt="You are a technical analyst...",
        ...     temperature=0.5
        ... )
        >>> response = await technical_agent.ainvoke({"input": "Analyze BTCUSDT"})
    """
    # Initialize Ollama LLM
    llm = ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url
    )
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"Role: {role}\n\n{system_prompt}"),
        ("human", "{input}")
    ])
    
    # Return LangChain runnable (prompt | LLM)
    return prompt | llm


def create_structured_agent(
    role: str,
    system_prompt: str,
    output_schema: Optional[dict] = None,
    model: str = "llama3.2:3b",
    temperature: float = 0.7
) -> Runnable:
    """
    Create agent with structured output (JSON schema validation).
    
    Args:
        role: Agent role identifier
        system_prompt: System prompt
        output_schema: Pydantic model or dict schema for structured output
        model: Ollama model name
        temperature: Sampling temperature
        
    Returns:
        Configured agent with structured output parsing
        
    Note:
        Structured output requires Ollama >=0.3.0 and model support
    """
    llm = ChatOllama(
        model=model,
        temperature=temperature,
        format="json" if output_schema else None
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"Role: {role}\n\n{system_prompt}\n\nOutput JSON only."),
        ("human", "{input}")
    ])
    
    return prompt | llm
