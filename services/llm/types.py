from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum

class LLMProvider(str, Enum):
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    MOCK = "MOCK"

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class Message(BaseModel):
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ToolDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

class StructuredResponse(BaseModel):
    json_schema: Optional[Dict[str, Any]] = None
    strict: bool = False

class LLMRequest(BaseModel):
    messages: List[Message]
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[ToolDefinition]] = None
    response_format: Optional[StructuredResponse] = None
    correlation_id: str

class LLMUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMResponse(BaseModel):
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]] = None
    provider: LLMProvider
    model: str
    usage: LLMUsage
    correlation_id: str

class LLMError(Exception):
    def __init__(self, message: str, provider: LLMProvider, original_error: Optional[Any] = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)
