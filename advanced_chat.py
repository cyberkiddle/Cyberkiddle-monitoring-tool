#!/usr/bin/env python3
"""
Advanced Chat Application with Multiple Features
- Task execution
- Context management
- Model switching
- File operations
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python not installed")
    print("Run: bash setup.sh")
    sys.exit(1)

MODELS_DIR = Path(__file__).parent / "models"

class TaskManager:
    """Manage tasks and execute them with LLM assistance"""
    
    def __init__(self):
        self.tasks = []
        self.task_file = Path(__file__).parent / "tasks.json"
        self.load_tasks()
    
    def add_task(self, task_description):
        """Add a new task"""
        task = {
            "id": len(self.tasks) + 1,
            "description": task_description,
            "status": "pending",
            "created": datetime.now().isoformat(),
            "completed": None
        }
        self.tasks.append(task)
        self.save_tasks()
        return task
    
    def complete_task(self, task_id):
        """Mark task as completed"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed"] = datetime.now().isoformat()
                self.save_tasks()
                return task
        return None
    
    def list_tasks(self):
        """List all tasks"""
        if not self.tasks:
            return "No tasks yet"
        
        output = "\n📋 Tasks:\n"
        for task in self.tasks:
            status_icon = "✅" if task["status"] == "completed" else "⏳"
            output += f"  {status_icon} [{task['id']}] {task['description']}\n"
        return output
    
    def save_tasks(self):
        """Save tasks to file"""
        with open(self.task_file, "w") as f:
            json.dump(self.tasks, f, indent=2)
    
    def load_tasks(self):
        """Load tasks from file"""
        if self.task_file.exists():
            with open(self.task_file, "r") as f:
                self.tasks = json.load(f)
        else:
            self.tasks = []


class AdvancedLLMChat:
    """Advanced chat with tasks, context, and model management"""
    
    def __init__(self, model_name=None):
        self.models_available = self._find_models()
        
        if not self.models_available:
            raise FileNotFoundError("No GGUF models found in models/ directory")
        
        if model_name is None:
            model_name = self.models_available[0].name
        
        self.model_path = MODELS_DIR / model_name
        if not self.model_path.exists():
            self.model_path = self.models_available[0]
        
        self._load_model(str(self.model_path))
        self.conversation_history = []
        self.task_manager = TaskManager()
        self.context = {}
    
    def _find_models(self):
        """Find all GGUF models"""
        if not MODELS_DIR.exists():
            return []
        return list(MODELS_DIR.glob("*.gguf"))
    
    def _load_model(self, model_path):
        """Load a model"""
        print(f"Loading model: {Path(model_path).name}")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0
        )
        print("✅ Model loaded!\n")
    
    def chat(self, user_input, max_tokens=512, temperature=0.7):
        """Process user input and generate response"""
        
        # Handle special commands
        if user_input.lower().startswith("task:"):
            return self._handle_task_command(user_input)
        
        if user_input.lower().startswith("ask:"):
            user_input = user_input[5:].strip()
        
        # Regular chat
        self.conversation_history.append({"role": "user", "content": user_input})
        
        prompt = self._build_prompt(user_input)
        
        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["User:", "Assistant:"]
        )
        
        assistant_response = response["choices"][0]["text"].strip()
        self.conversation_history.append({"role": "assistant", "content": assistant_response})
        
        return assistant_response
    
    def _build_prompt(self, user_input):
        """Build prompt with context"""
        prompt = ""
        
        # Add recent history
        for msg in self.conversation_history[-4:]:
            role = msg["role"].capitalize()
            prompt += f"{role}: {msg['content']}\n"
        
        prompt += f"User: {user_input}\nAssistant:"
        return prompt
    
    def _handle_task_command(self, user_input):
        """Handle task-related commands"""
        command = user_input[5:].strip()
        
        if command.lower() == "list":
            return self.task_manager.list_tasks()
        
        if command.lower().startswith("done "):
            task_id = int(command.split()[1])
            task = self.task_manager.complete_task(task_id)
            return f"✅ Task {task_id} marked as completed!" if task else "Task not found"
        
        # Add new task
        task = self.task_manager.add_task(command)
        return f"✅ Task #{task['id']} added: {command}"
    
    def help(self):
        """Show help message"""
        return """
🤖 Local LLM Chat - Commands:

Chat:
  ask: <question>     - Ask a question
  <message>           - Regular chat (default)

Tasks:
  task: list          - List all tasks
  task: <description> - Add new task
  task: done <id>     - Mark task as completed

System:
  clear               - Clear conversation
  models              - List available models
  switch <model>      - Switch to different model
  help                - Show this help
  quit                - Exit

Example:
  task: Write a Python script for data analysis
  task: done 1
  ask: What is machine learning?
"""


def main():
    """Main function"""
    try:
        chat = AdvancedLLMChat()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please download a GGUF model and place it in the models/ directory")
        sys.exit(1)
    
    print("=" * 60)
    print("🤖 Local LLM Chat with Task Manager")
    print("=" * 60)
    print(chat.help())
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("Goodbye! 👋")
                break
            
            if user_input.lower() == "help":
                print(chat.help())
                continue
            
            if user_input.lower() == "clear":
                chat.conversation_history = []
                print("Conversation cleared.\n")
                continue
            
            if user_input.lower() == "models":
                print("\nAvailable models:")
                for i, model in enumerate(chat.models_available, 1):
                    size = model.stat().st_size / (1024**3)
                    print(f"  {i}. {model.name} ({size:.2f} GB)")
                print()
                continue
            
            if user_input.lower().startswith("switch "):
                model_name = user_input[7:].strip()
                try:
                    chat._load_model(str(MODELS_DIR / model_name))
                    chat.conversation_history = []
                    print()
                except Exception as e:
                    print(f"Error loading model: {e}\n")
                continue
            
            print("Assistant: ", end="", flush=True)
            response = chat.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
