#!/usr/bin/env python3
"""
Quick test to verify setup
"""
import sys
from pathlib import Path

def check_setup():
    base_path = Path(__file__).parent
    
    print("=" * 60)
    print("Local LLM Chat - Setup Verification")
    print("=" * 60)
    
    # Check files
    files_to_check = [
        "chat.py",
        "advanced_chat.py",
        "web_chat.py",
        "requirements.txt",
        "setup.sh",
        "README.md",
        "GETTING_STARTED.md"
    ]
    
    print("\n📁 Checking files...")
    all_exist = True
    for file in files_to_check:
        path = base_path / file
        exists = "✅" if path.exists() else "❌"
        print(f"  {exists} {file}")
        if not path.exists():
            all_exist = False
    
    # Check models directory
    models_dir = base_path / "models"
    print(f"\n📁 Models directory: {models_dir}")
    
    if models_dir.exists():
        models = list(models_dir.glob("*.gguf"))
        if models:
            print(f"  Found {len(models)} model(s):")
            for model in models:
                size_gb = model.stat().st_size / (1024**3)
                print(f"    • {model.name} ({size_gb:.2f} GB)")
        else:
            print("  ⚠️  No GGUF models found")
            print("  Download from: https://huggingface.co/models?search=gguf")
    else:
        print("  ⚠️  Models directory doesn't exist yet")
        print("  Creating it now...")
        models_dir.mkdir(exist_ok=True)
    
    # Check Python
    print(f"\n🐍 Python version: {sys.version.split()[0]}")
    
    # Check dependencies
    print("\n📦 Checking Python dependencies...")
    deps = {
        "llama_cpp": "llama-cpp-python",
        "flask": "flask"
    }
    
    missing = []
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - NOT INSTALLED")
            missing.append(package)
    
    print("\n" + "=" * 60)
    
    if missing:
        print("⚠️  Missing dependencies!")
        print("\nInstall with:")
        print(f"  pip install {' '.join(missing)}")
        print("\nOr run:")
        print("  bash setup.sh")
    else:
        print("✅ All dependencies installed!")
    
    if all_exist and not missing:
        print("\n🚀 Ready to use!")
        print("\nQuick start:")
        print("  python3 chat.py              # Simple CLI")
        print("  python3 advanced_chat.py     # With tasks")
        print("  python3 web_chat.py          # Web interface")
    
    print("=" * 60)


if __name__ == "__main__":
    check_setup()
