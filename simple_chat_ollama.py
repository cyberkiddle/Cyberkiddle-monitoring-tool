#!/usr/bin/env python3
"""
Simple Chat Application using Ollama (Docker-based LLM)
This is a lightweight alternative that doesn't require compilation
"""

import requests
import json
import sys
from pathlib import Path

# Configuration
OLLAMA_API = "http://localhost:11434/api/generate"
MODELS_DIR = Path(__file__).parent / "models"

class SimpleLLMChat:
    def __init__(self, model_name="orca-mini"):
        """Initialize the chat"""
        self.model_name = model_name
        self.conversation_history = []
        
        print(f"Using model: {model_name}")
        print("Type 'quit' to exit, 'clear' to reset conversation\n")
    
    def chat(self, user_input):
        """Send a message and get a response"""
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Build prompt from history
        prompt = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in self.conversation_history
        ]) + "\nAssistant:"
        
        try:
            response = requests.post(
                OLLAMA_API,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                assistant_response = result.get("response", "").strip()
                self.conversation_history.append({"role": "assistant", "content": assistant_response})
                return assistant_response
            else:
                return f"Error: {response.status_code} - Is Ollama running?"
        
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Is it running? (ollama serve)"
        except requests.exceptions.Timeout:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def reset_history(self):
        """Clear conversation history"""
        self.conversation_history = []


def main():
    print("=" * 60)
    print("Simple LLM Chat (Ollama)")
    print("=" * 60)
    print("\nNote: This requires Ollama to be running!")
    print("Download Ollama from: https://ollama.ai")
    print("Then run: ollama pull orca-mini")
    print("         ollama serve")
    print("\n" + "=" * 60 + "\n")
    
    chat = SimpleLLMChat()
    
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
                print("Conversation cleared.\n")
                continue
            
            print("Assistant: ", end="", flush=True)
            response = chat.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


if __name__ == "__main__":
    main()
