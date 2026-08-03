#!/bin/bash
# Setup script for Local LLM Chat

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "To start the chat:"
echo "  python3 chat.py              # Use default model"
echo "  python3 chat.py list         # List available models"
echo "  python3 chat.py model.gguf   # Use specific model"
