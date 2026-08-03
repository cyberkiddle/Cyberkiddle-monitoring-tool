#!/usr/bin/env python3
"""
Local LLM Chat Application
Supports GGUF format models like Orca-mini
"""

import os
import sys
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python not installed")
    print("Install it with: pip install llama-cpp-python")
    sys.exit(1)

# Configuration
MODELS_DIR = Path(__file__).parent / "models"
DEFAULT_MODEL = "orca-mini-3b-gguf2-q4_0.gguf"

class LocalLLMChat:
    def __init__(self, model_name=DEFAULT_MODEL, n_ctx=2048, n_threads=4):
        """Initialize the chat with a local LLM model"""
        self.model_path = MODELS_DIR / model_name
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        print(f"Loading model: {model_name}")
        self.llm = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=0  # Set to 32+ if you have GPU support
        )
        print("Model loaded successfully!\n")
        self.conversation_history = []
    
    def chat(self, user_input, max_tokens=512, temperature=0.7):
        """Send a message and get a response"""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Format conversation for the model
        formatted_prompt = self._format_prompt(user_input)
        
        # Get response from model
        response = self.llm(
            formatted_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["User:", "Assistant:"]
        )
        
        assistant_response = response["choices"][0]["text"].strip()
        
        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": assistant_response})
        
        return assistant_response
    
    def _format_prompt(self, user_input):
        """Format the prompt with conversation history"""
        prompt = ""
        for msg in self.conversation_history[-6:]:  # Keep last 6 messages for context
            if msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            else:
                prompt += f"Assistant: {msg['content']}\n"
        
        # Add current input
        prompt += f"User: {user_input}\nAssistant:"
        return prompt
    
    def reset_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def get_history(self):
        """Get conversation history"""
        return self.conversation_history


def list_available_models():
    """List all available GGUF models"""
    if not MODELS_DIR.exists():
        print(f"Models directory not found: {MODELS_DIR}")
        return []
    
    models = list(MODELS_DIR.glob("*.gguf"))
    if not models:
        print(f"No GGUF models found in {MODELS_DIR}")
        return []
    
    print("Available models:")
    for i, model in enumerate(models, 1):
        size = model.stat().st_size / (1024**3)  # Convert to GB
        print(f"  {i}. {model.name} ({size:.2f} GB)")
    
    return models


def interactive_chat(model_name=DEFAULT_MODEL):
    """Run interactive chat session"""
    try:
        chat = LocalLLMChat(model_name)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        list_available_models()
        return
    
    print("=" * 60)
    print("Local LLM Chat")
    print("=" * 60)
    print("Commands:")
    print("  'clear'  - Clear conversation history")
    print("  'reset'  - Reset the model")
    print("  'quit'   - Exit the chat")
    print("=" * 60 + "\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("Goodbye!")
                break
            
            if user_input.lower() == "clear":
                chat.reset_history()
                print("Conversation history cleared.\n")
                continue
            
            if user_input.lower() == "reset":
                chat = LocalLLMChat(model_name)
                print("Model reset.\n")
                continue
            
            print("\nThinking", end="", flush=True)
            response = chat.chat(user_input)
            print(f"\r\033[K")  # Clear the "Thinking" line
            print(f"Assistant: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_available_models()
        else:
            interactive_chat(sys.argv[1])
    else:
        interactive_chat()
