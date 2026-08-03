# Local LLM Chat Application

This is a Python application for chatting with locally running LLM models.


https://github.com/user-attachments/assets/b816666e-ba09-4c44-b121-3114b0e266fc



## Features

- **Local Model Support**: Uses GGUF format models (like Orca-mini)
- **Conversation History**: Maintains context across messages
- **Interactive CLI**: Simple command-line interface for chatting
- **Model Management**: Easy switching between models

## Setup


### Debian pkg
Since we have minimum of 2GB upload we need to separate between application deb file and model upload

```
#Downloading the deb pkg and model .gguf
wget https://github.com/cyberkiddle/Cyberkiddle-monitoring-tool/releases/download/cyberkiddle/cyberkiddle_deb-0.1.1-.deb
wget https://github.com/cyberkiddle/Cyberkiddle-monitoring-tool/releases/download/cyberkiddle/orca-mini-3b-gguf2-q4_0.gguf

# Installing the deb pkg
sudo dpkg -i cyberkiddle_deb-0.1.1-.deb

# copying the model to the right place
sudo cp orca-mini-3b-gguf2-q4_0.gguf /usr/share/cyberkiddle/models/orca-mini-3b-gguf2-q4_0.gguf

cyberkiddle #this will start app.
```

### Manually installing
> seting up the app manually
```
git clone https://github.com/cyberkiddle/Cyberkiddle-monitoring-tool.git
cd Cyberkiddle-monitoring-tool/models
wget https://github.com/cyberkiddle/Cyberkiddle-monitoring-tool/releases/download/cyberkiddle/orca-mini-3b-gguf2-q4_0.gguf
cd ..
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> Setting up AI needs manually
```
python3 -m venvAI venvAI
source venv/bin/activate
python3 gui_chat.py #Installing local needs for model environment then Ctrl ^C

```


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
