#!/bin/bash
# Quick Start Guide for Local LLM Chat

echo "🤖 Local LLM Chat - Quick Start"
echo "=============================="
echo ""

# Check if models exist
if [ ! -d "models" ]; then
    echo "❌ models/ directory not found!"
    echo ""
    echo "Steps:"
    echo "1. Create a models/ directory"
    echo "2. Download a GGUF model (e.g., Orca-mini from huggingface.co)"
    echo "3. Place the .gguf file in the models/ directory"
    echo ""
    exit 1
fi

MODELS=$(find models -name "*.gguf" 2>/dev/null | wc -l)

if [ $MODELS -eq 0 ]; then
    echo "❌ No GGUF models found in models/ directory!"
    echo ""
    echo "Download a model from:"
    echo "  - https://huggingface.co/models?search=gguf"
    echo ""
    echo "Popular options:"
    echo "  - Orca Mini: https://huggingface.co/psmathur/orca_mini_v3_gguf"
    echo "  - Mistral 7B: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF"
    echo "  - Neural Chat: https://huggingface.co/TheBloke/neural-chat-7B-v3-2-GGUF"
    echo ""
    exit 1
fi

echo "✅ Found $MODELS model(s)"
echo ""
echo "Installation:"
echo "1. Install dependencies:"
echo "   bash setup.sh"
echo ""
echo "2. Start chatting:"
echo "   python3 chat.py"
echo ""
echo "   OR with advanced features (tasks, etc):"
echo "   python3 advanced_chat.py"
echo ""
echo "3. For help with commands, type 'help' in the chat"
echo ""
