#!/usr/bin/env python3
"""
Web-based Chat Interface for Local LLM
Flask web app for chatting with local models
"""

import json
from pathlib import Path
from datetime import datetime
from threading import Thread
import sys

try:
    from flask import Flask, render_template_string, request, jsonify
    from llama_cpp import Llama
except ImportError:
    print("Error: Missing dependencies")
    print("Run: pip install flask")
    sys.exit(1)

MODELS_DIR = Path(__file__).parent / "models"

class WebLLMChat:
    def __init__(self):
        self.app = Flask(__name__)
        self.models = list(MODELS_DIR.glob("*.gguf"))
        self.llm = None
        self.current_model = None
        self.conversation = []
        
        if self.models:
            self._load_model(self.models[0])
        
        self._setup_routes()
    
    def _load_model(self, model_path):
        """Load a model"""
        self.current_model = model_path.name
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0
        )
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route("/")
        def index():
            return render_template_string(self.get_html_template())
        
        @self.app.route("/api/models", methods=["GET"])
        def get_models():
            return jsonify({
                "models": [m.name for m in self.models],
                "current": self.current_model
            })
        
        @self.app.route("/api/switch-model", methods=["POST"])
        def switch_model():
            model_name = request.json.get("model")
            try:
                self._load_model(MODELS_DIR / model_name)
                self.conversation = []
                return jsonify({"status": "success", "model": model_name})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 400
        
        @self.app.route("/api/chat", methods=["POST"])
        def chat():
            user_message = request.json.get("message", "").strip()
            
            if not user_message or not self.llm:
                return jsonify({"status": "error", "message": "No model loaded"}), 400
            
            try:
                # Add to history
                self.conversation.append({"role": "user", "content": user_message})
                
                # Build prompt
                prompt = ""
                for msg in self.conversation[-4:]:
                    role = msg["role"].capitalize()
                    prompt += f"{role}: {msg['content']}\n"
                prompt += "Assistant:"
                
                # Get response
                response = self.llm(
                    prompt,
                    max_tokens=512,
                    temperature=0.7,
                    stop=["User:"]
                )
                
                assistant_message = response["choices"][0]["text"].strip()
                self.conversation.append({"role": "assistant", "content": assistant_message})
                
                return jsonify({
                    "status": "success",
                    "response": assistant_message,
                    "timestamp": datetime.now().isoformat()
                })
            
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route("/api/clear", methods=["POST"])
        def clear_history():
            self.conversation = []
            return jsonify({"status": "success"})
        
        @self.app.route("/api/history", methods=["GET"])
        def get_history():
            return jsonify({"conversation": self.conversation})
    
    def get_html_template(self):
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Local LLM Chat</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            padding: 20px;
        }
        
        .container {
            width: 100%;
            max-width: 1200px;
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 20px;
            margin: auto;
        }
        
        .sidebar {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            height: fit-content;
        }
        
        .sidebar h2 {
            font-size: 14px;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 15px;
            letter-spacing: 1px;
        }
        
        .sidebar select {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 13px;
            cursor: pointer;
        }
        
        .sidebar button {
            width: 100%;
            padding: 10px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            margin-bottom: 10px;
            transition: background 0.2s;
        }
        
        .sidebar button:hover {
            background: #764ba2;
        }
        
        .chat-container {
            background: white;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .chat-header {
            background: #667eea;
            color: white;
            padding: 20px;
            text-align: center;
        }
        
        .chat-header h1 {
            font-size: 20px;
            margin-bottom: 5px;
        }
        
        .chat-header p {
            font-size: 12px;
            opacity: 0.9;
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: 500px;
        }
        
        .message {
            display: flex;
            gap: 10px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            flex-direction: row-reverse;
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 15px;
            border-radius: 10px;
            word-wrap: break-word;
            font-size: 14px;
            line-height: 1.4;
        }
        
        .message.assistant .message-content {
            background: #f0f0f0;
            color: #333;
        }
        
        .message.user .message-content {
            background: #667eea;
            color: white;
        }
        
        .input-area {
            padding: 20px;
            border-top: 1px solid #eee;
            display: flex;
            gap: 10px;
        }
        
        .input-area input {
            flex: 1;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            font-family: inherit;
        }
        
        .input-area button {
            padding: 12px 25px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .input-area button:hover {
            background: #764ba2;
        }
        
        .input-area button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .loading {
            text-align: center;
            color: #999;
            font-size: 13px;
            padding: 20px;
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 5px;
            margin: 10px;
            border-left: 4px solid #c33;
        }
        
        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
            
            .sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h2>Models</h2>
            <select id="modelSelect">
                <option>Loading...</option>
            </select>
            <button onclick="clearHistory()">Clear Chat</button>
            
            <h2 style="margin-top: 30px;">Info</h2>
            <p style="font-size: 12px; color: #666; line-height: 1.6;">
                Local LLM Chat powered by Orca Mini or your custom GGUF model.
            </p>
        </div>
        
        <div class="chat-container">
            <div class="chat-header">
                <h1>🤖 Local LLM Chat</h1>
                <p id="modelName">Loading model...</p>
            </div>
            
            <div id="messages" class="messages">
                <div class="message assistant">
                    <div class="message-content">
                        Hello! I'm ready to chat. Ask me anything or give me a task to help with.
                    </div>
                </div>
            </div>
            
            <div class="input-area">
                <input 
                    type="text" 
                    id="messageInput" 
                    placeholder="Type your message..." 
                    onkeypress="handleKeypress(event)"
                >
                <button id="sendBtn" onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        let isLoading = false;
        
        // Load models on page load
        document.addEventListener('DOMContentLoaded', async () => {
            await loadModels();
            document.getElementById('messageInput').focus();
        });
        
        async function loadModels() {
            try {
                const response = await fetch('/api/models');
                const data = await response.json();
                
                const select = document.getElementById('modelSelect');
                select.innerHTML = data.models
                    .map(m => `<option value="${m}" ${m === data.current ? 'selected' : ''}>${m}</option>`)
                    .join('');
                
                document.getElementById('modelName').textContent = `Model: ${data.current}`;
                
                select.addEventListener('change', switchModel);
            } catch (e) {
                showError('Failed to load models');
            }
        }
        
        async function switchModel() {
            const model = document.getElementById('modelSelect').value;
            try {
                const response = await fetch('/api/switch-model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model })
                });
                
                if (response.ok) {
                    document.getElementById('modelName').textContent = `Model: ${model}`;
                    clearHistory();
                } else {
                    showError('Failed to switch model');
                }
            } catch (e) {
                showError('Error switching model');
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || isLoading) return;
            
            // Add user message to UI
            addMessage(message, 'user');
            input.value = '';
            isLoading = true;
            document.getElementById('sendBtn').disabled = true;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    addMessage(data.response, 'assistant');
                } else {
                    showError(data.message || 'Error generating response');
                }
            } catch (e) {
                showError('Network error');
            } finally {
                isLoading = false;
                document.getElementById('sendBtn').disabled = false;
                input.focus();
            }
        }
        
        function addMessage(content, role) {
            const messagesDiv = document.getElementById('messages');
            const messageEl = document.createElement('div');
            messageEl.className = `message ${role}`;
            messageEl.innerHTML = `<div class="message-content">${escapeHtml(content)}</div>`;
            messagesDiv.appendChild(messageEl);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function showError(message) {
            const messagesDiv = document.getElementById('messages');
            const errorEl = document.createElement('div');
            errorEl.className = 'error';
            errorEl.textContent = message;
            messagesDiv.appendChild(errorEl);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        async function clearHistory() {
            await fetch('/api/clear', { method: 'POST' });
            document.getElementById('messages').innerHTML = 
                '<div class="message assistant"><div class="message-content">History cleared. Ready for new conversation!</div></div>';
        }
        
        function handleKeypress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
        """
    
    def run(self, host="127.0.0.1", port=5000, debug=False):
        """Run the Flask server"""
        if not self.models:
            print("Error: No GGUF models found in models/ directory")
            return
        
        print(f"🚀 Starting web server at http://{host}:{port}")
        print(f"Using model: {self.current_model}")
        print("Press Ctrl+C to stop")
        
        self.app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    chat = WebLLMChat()
    chat.run()
