#!/usr/bin/env python3
"""
Interactive Demo Chat - Works without external dependencies
Shows how the chat interface would work
"""

import json
from datetime import datetime

class DemoChat:
    def __init__(self):
        self.conversation = []
        self.tasks = []
        self.responses = self._load_sample_responses()
    
    def _load_sample_responses(self):
        """Load sample AI responses"""
        return {
            "python": "Python is a high-level programming language known for its simple syntax and readability. It's widely used in web development, data science, AI, and automation.",
            "machine learning": "Machine learning is a subset of artificial intelligence where systems learn patterns from data without being explicitly programmed. It powers recommendations, predictions, and automation.",
            "hello": "Hello! I'm your local AI assistant. Ask me anything about programming, learning, or any topic you're interested in!",
            "hello world": "The classic 'Hello World' program is traditionally the first program people write when learning a new language. It's a simple way to test if your development environment is set up correctly.",
            "task": "I can help you create and manage tasks! Use the task system to track your learning goals.",
            "help": "You can ask me questions about any topic. I'll provide helpful answers and explanations. Try asking about Python, programming, or any subject!",
            "default": "That's an interesting question! I'm a local AI assistant running on your computer. Feel free to ask me anything about programming, concepts, or ideas you'd like to explore.",
        }
    
    def get_response(self, user_input):
        """Generate a response based on user input"""
        query = user_input.lower()
        
        # Check for keywords
        for key, response in self.responses.items():
            if key in query:
                return response
        
        # Default response
        return self.responses["default"]
    
    def chat(self, user_input):
        """Process user input and return response"""
        # Add to history
        self.conversation.append({
            "timestamp": datetime.now().isoformat(),
            "role": "user",
            "content": user_input
        })
        
        # Get response
        response = self.get_response(user_input)
        
        # Add response to history
        self.conversation.append({
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "content": response
        })
        
        return response
    
    def add_task(self, task_description):
        """Add a task"""
        task = {
            "id": len(self.tasks) + 1,
            "description": task_description,
            "completed": False,
            "created": datetime.now().isoformat()
        }
        self.tasks.append(task)
        return task
    
    def complete_task(self, task_id):
        """Mark task as completed"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = True
                return task
        return None
    
    def list_tasks(self):
        """List all tasks"""
        if not self.tasks:
            return "No tasks yet"
        
        output = "\n📋 Tasks:\n"
        for task in self.tasks:
            status = "✅" if task["completed"] else "⏳"
            output += f"  {status} [{task['id']}] {task['description']}\n"
        return output
    
    def save_conversation(self):
        """Save conversation to file"""
        with open("/home/cyberkid/bin/Ai/last_conversation.json", "w") as f:
            json.dump(self.conversation, f, indent=2)


def main():
    """Main chat loop"""
    chat = DemoChat()
    
    print("=" * 70)
    print("🤖 LOCAL LLM CHAT - DEMO MODE")
    print("=" * 70)
    print("\nThis is a demo showing what the chat interface does!")
    print("In production, this connects to your local AI models.\n")
    print("Commands:")
    print("  ask: <question>    - Ask a question")
    print("  task: <task>       - Add a task")
    print("  task: list         - List tasks")
    print("  task: done <id>    - Complete task")
    print("  save               - Save conversation")
    print("  clear              - Clear screen")
    print("  quit               - Exit\n")
    print("=" * 70 + "\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("\nGoodbye! 👋")
                break
            
            if user_input.lower() == "clear":
                print("\n" * 100)
                print("=" * 70)
                print("🤖 LOCAL LLM CHAT - DEMO MODE")
                print("=" * 70 + "\n")
                continue
            
            if user_input.lower() == "save":
                chat.save_conversation()
                print("✅ Conversation saved to: last_conversation.json\n")
                continue
            
            if user_input.lower().startswith("task:"):
                command = user_input[5:].strip()
                
                if command.lower() == "list":
                    print(chat.list_tasks() + "")
                    continue
                
                if command.lower().startswith("done "):
                    task_id = int(command.split()[1])
                    task = chat.complete_task(task_id)
                    if task:
                        print(f"✅ Task {task_id} marked as completed!\n")
                    else:
                        print("❌ Task not found\n")
                    continue
                
                # Add new task
                task = chat.add_task(command)
                print(f"✅ Task #{task['id']} added: {command}\n")
                continue
            
            if user_input.lower().startswith("ask:"):
                user_input = user_input[4:].strip()
            
            # Regular chat
            print("\nAssistant: ", end="", flush=True)
            response = chat.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except ValueError:
            print("❌ Invalid input. Try again.\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
