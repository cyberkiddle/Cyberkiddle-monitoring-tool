#!/usr/bin/env python3
"""
Real LLM Chat - Uses actual GGUF models
Works with orca-mini and other quantized models
"""

import sys
from pathlib import Path

# Try to import llama_cpp, install if needed
try:
    from llama_cpp import Llama
except ImportError:
    print("Installing llama-cpp-python... (first time only, may take a minute)")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
    from llama_cpp import Llama

MODELS_DIR = Path(__file__).parent / "models"

class RealLLMChat:
    def __init__(self):
        """Initialize with real model"""
        # Find available models

        models = list(MODELS_DIR.glob("*.gguf"))
        
        if not models:
            print("❌ No GGUF models found in models/ directory")
            print(f"   Looking in: {MODELS_DIR}")
            sys.exit(1)
        
        # Use first model found
        model_path = models[0]
        print(f"📦 Loading model: {model_path.name}")
        print("   (First time may take 10-30 seconds...)\n")
        
        # Load model
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0,
            verbose=False
        )
        
        print("✅ Model loaded!\n")
        self.conversation = []
    
    def chat(self, user_input):
        """Get response from real model"""
        self.conversation.append({"role": "user", "content": user_input})
        
        # Build a better prompt for Orca Mini
        system = "You are a helpful assistant."
        
        # Format as simple Q&A
        prompt = system + "\n\n"
        
        # Add last few exchanges
        for msg in self.conversation[-6:]:
            if msg["role"] == "user":
                prompt += f"Q: {msg['content']}\n"
            else:
                prompt += f"A: {msg['content']}\n"
        
        prompt += "A:"
        
        # Get response
        response = self.llm(
            prompt,
            max_tokens=256,
            temperature=0.8,
            top_p=0.95,
            stop=["Q:", "\n\nQ"]
        )
        
        text = response["choices"][0]["text"].strip()
        self.conversation.append({"role": "assistant", "content": text})
        
        return text


def main():
    chat = RealLLMChat()
    
    print("=" * 70)
    print("🤖 REAL LLM CHAT - ACTUAL AI RESPONSES")
    print("=" * 70)
    print("Type 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("Goodbye!")
                break
            
            print("\nAssistant: ", end="", flush=True)
            response = chat.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
