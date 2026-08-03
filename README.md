# Local LLM Chat Application

This is a Python application for chatting with locally running LLM models.


https://github.com/user-attachments/assets/b816666e-ba09-4c44-b121-3114b0e266fc



## Features

- **Local Model Support**: Uses GGUF format models (like Orca-mini)
- **Conversation History**: Maintains context across messages
- **Interactive CLI**: Simple command-line interface for chatting
- **Model Management**: Easy switching between models

## Setup

1. **Install dependencies:**
   ```bash
   bash setup.sh
   # or manually: pip install -r requirements.txt
   ```

2. **Place your models** in the `models/` directory (GGUF format)

## Usage

### Start Interactive Chat
```bash
python3 chat.py                    # Use default model
python3 chat.py orca-mini.gguf     # Use specific model
```

### List Available Models
```bash
python3 chat.py list
```

### Commands (inside chat)
- `clear` - Clear conversation history
- `reset` - Reset the model
- `quit` - Exit the chat

## Supported Models

Any GGUF format model works, including:
- Orca Mini (3B, 7B, 13B)
- Mistral 7B
- Neural Chat
- Other GGUF quantized models

## Requirements

- Python 3.8+
- 4GB+ RAM (for 3B models), 8GB+ for larger models
- CUDA/GPU support optional (speeds up inference)

## Advanced Configuration

Edit `chat.py` to customize:
- `n_ctx`: Context window size (default: 2048)
- `n_threads`: CPU threads (default: 4)
- `n_gpu_layers`: GPU acceleration (default: 0 for CPU only)
- Model parameters like temperature and max tokens
