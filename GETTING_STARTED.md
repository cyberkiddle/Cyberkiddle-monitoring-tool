# 🤖 Local LLM Chat - Complete Setup Guide

## What You Have

Three chat applications with increasing features:

1. **chat.py** - Simple CLI chat
2. **advanced_chat.py** - CLI with task management
3. **web_chat.py** - Web-based interface (browser)

## Installation

### Step 1: Install Dependencies

```bash
cd /home/cyberkid/bin/Ai
bash setup.sh
```

Or manually:
```bash
pip install llama-cpp-python flask
```

### Step 2: Download Models

You need GGUF format models. Download from Hugging Face:

**Option A: Orca Mini (Recommended - Fast & Good Quality)**
- Download from: https://huggingface.co/psmathur/orca_mini_v3_gguf
- File: `orca-mini-3b.gguf` (~3.3 GB)

**Option B: Mistral 7B (Better but Slower)**
- Download from: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF
- File: `mistral-7b-instruct-v0.1.Q4_K_M.gguf` (~5 GB)

**Option C: Neural Chat**
- Download from: https://huggingface.co/TheBloke/neural-chat-7B-v3-2-GGUF
- File: `neural-chat-7b-v3-2.Q4_K_M.gguf` (~5 GB)

Place downloaded files in: `/home/cyberkid/bin/Ai/models/`

### Step 3: Verify Setup

```bash
bash quickstart.sh
```

## Usage

### Simple CLI Chat
```bash
python3 chat.py
```

**Commands:**
- `clear` - Clear conversation history
- `reset` - Reset the model
- `quit` - Exit

**Example:**
```
You: What is machine learning?
Assistant: Machine learning is a subset of artificial intelligence...

You: Can you explain neural networks?
Assistant: Neural networks are computational models inspired by...
```

### Advanced CLI with Tasks
```bash
python3 advanced_chat.py
```

**Commands:**
- `ask: <question>` - Ask a question
- `task: <description>` - Add a task
- `task: list` - View all tasks
- `task: done <id>` - Mark task complete
- `clear` - Clear conversation
- `models` - List available models
- `switch <model>` - Switch to different model
- `help` - Show help

**Example:**
```
You: task: Build a web scraper for weather data
Assistant: ✅ Task #1 added: Build a web scraper for weather data

You: task: list
Assistant: 📋 Tasks:
  ⏳ [1] Build a web scraper for weather data

You: How do I build a web scraper?
Assistant: To build a web scraper, you'll need...

You: task: done 1
Assistant: ✅ Task 1 marked as completed!
```

### Web Interface (Browser)
```bash
python3 web_chat.py
```

Then open: http://localhost:5000

**Features:**
- Beautiful web UI
- Switch models from dropdown
- Chat history displayed nicely
- Clear conversation button
- Works on mobile

## Performance Tips

### For CPU Only:
- Use 3B models (Orca Mini) for speed
- Edit `chat.py` or `advanced_chat.py`:
  - Reduce `n_ctx` from 2048 to 1024
  - Set `n_threads` to your CPU core count
  - Reduce `max_tokens` from 512 to 256

### For GPU (CUDA):
In `chat.py`, change:
```python
n_gpu_layers=0  # Change to 32 or higher
```

Also update requirements:
```bash
pip install llama-cpp-python --no-binary llama-cpp-python
# Then rebuild with CUDA support
```

### Faster Response Times:
- Use smaller quantization (Q4 instead of Q5 or Q6)
- Reduce temperature to 0.5 for more focused responses
- Use shorter max_tokens (256 instead of 512)

## Example Workflows

### 1. Learning & Q&A
```
You: Explain quantum computing in simple terms
You: What are qubits?
You: How does quantum entanglement work?
```

### 2. Code Help
```
You: Write a Python function to sort a list
You: Can you add error handling?
You: How do I test this function?
```

### 3. Project Planning
```
You: task: Design database schema
You: task: Build API endpoints
You: task: Create frontend
You: task: Add authentication
You: task: list
You: task: done 1
```

### 4. Writing & Content
```
You: Write a short story about a robot
You: Make it more creative
You: Add more dialogue
```

## Troubleshooting

### "Model not found" error
- Check models are in `/home/cyberkid/bin/Ai/models/`
- Run `python3 chat.py list` to see available models

### Very slow responses
- Use a smaller model (Orca Mini instead of Mistral)
- Reduce `n_ctx` in the code
- Reduce `max_tokens` in the code

### Out of memory
- Use CPU-only (don't enable GPU)
- Use 3B model instead of 7B
- Close other applications

### ModuleNotFoundError
- Run: `pip install -r requirements.txt`
- Or: `bash setup.sh`

## Advanced Configuration

### Edit `chat.py` (around line 24):
```python
self.llm = Llama(
    model_path=str(self.model_path),
    n_ctx=2048,        # Increase for longer context
    n_threads=4,       # Set to your CPU cores
    n_gpu_layers=0     # Set to 32+ for GPU
)
```

### Edit chat parameters (around line 35):
```python
response = self.llm(
    formatted_prompt,
    max_tokens=512,      # Shorter = faster responses
    temperature=0.7,     # Lower = more focused, higher = more creative
    stop=["User:", "Assistant:"]
)
```

## File Structure

```
/home/cyberkid/bin/Ai/
├── chat.py                 # Simple CLI chat
├── advanced_chat.py        # CLI with tasks
├── web_chat.py             # Web interface
├── requirements.txt        # Python dependencies
├── setup.sh               # Setup script
├── quickstart.sh          # Quick start guide
├── README.md              # Detailed docs
├── GETTING_STARTED.md     # This file
├── models/                # Your GGUF models go here
│   ├── orca-mini-3b.gguf
│   └── mistral-7b.gguf
└── tasks.json             # Task storage (auto-created)
```

## Next Steps

1. ✅ Install dependencies: `bash setup.sh`
2. ✅ Download a model to `models/` directory
3. ✅ Run: `bash quickstart.sh`
4. ✅ Choose your app:
   - CLI: `python3 chat.py`
   - Advanced: `python3 advanced_chat.py`
   - Web: `python3 web_chat.py`

## Model Recommendations

| Use Case | Model | Size | Speed |
|----------|-------|------|-------|
| Quick testing | Orca Mini 3B | 3 GB | ⚡⚡⚡ Fast |
| Good balance | Mistral 7B Q4 | 5 GB | ⚡⚡ Moderate |
| Best quality | Mistral 7B Q5 | 7 GB | ⚡ Slower |
| Mobile/Limited RAM | TinyLlama | 1 GB | ⚡⚡⚡⚡ Very Fast |

## Support

For issues:
1. Check this guide
2. Run: `python3 chat.py list` to verify models
3. Check terminal output for error messages
4. Try a different model to isolate issues

---

**Happy chatting! 🚀**
