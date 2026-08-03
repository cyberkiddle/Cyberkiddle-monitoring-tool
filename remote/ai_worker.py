"""
ai_worker.py
------------
Runs under the venvAI interpreter (the one with llama-cpp-python installed).
Loads a GGUF model ONCE, then sits in a loop reading one JSON request per
line from stdin and STREAMING the response back as multiple JSON lines,
so the caller can show tokens as they're generated instead of waiting for
the whole answer.

Protocol:
  stdin  line:  {"prompt": "..."}
  stdout lines (in order):
      {"chunk": "..."}          zero or more, one per generated fragment
      {"done": true, "response": "<full text>"}   on success, ends the turn
      {"ok": false, "error": "..."}                on failure, ends the turn

Status/progress lines are written to stderr for debugging, never stdout.
"""
import sys
import os
import json
import glob

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')

N_CTX = 2048
N_THREADS = 4
N_GPU_LAYERS = 0
MAX_TOKENS = 300
TEMPERATURE = 0.7


def find_model():
    override = os.environ.get("CYBERKIDDLE_MODEL")
    if override and os.path.isfile(override):
        return override
    candidates = sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))
    return candidates[0] if candidates else None


def main():
    print("[ai_worker] starting up...", file=sys.stderr, flush=True)

    model_path = find_model()
    llm = None
    if not model_path:
        print(f"[ai_worker] no .gguf model found in {MODELS_DIR}", file=sys.stderr, flush=True)
    else:
        try:
            from llama_cpp import Llama
            print(f"[ai_worker] loading model: {model_path}", file=sys.stderr, flush=True)
            llm = Llama(
                model_path=model_path,
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                n_gpu_layers=N_GPU_LAYERS,
                verbose=False,
            )
            print("[ai_worker] model loaded, ready.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[ai_worker] failed to load model: {e}", file=sys.stderr, flush=True)
            llm = None

    # Readiness handshake — first line the parent process waits for
    print(json.dumps({"ok": True, "ready": True, "model": model_path}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            prompt = (req.get("prompt") or "").strip()
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"bad request: {e}"}), flush=True)
            continue

        if not prompt:
            print(json.dumps({"ok": False, "error": "empty prompt"}), flush=True)
            continue

        if llm is None:
            print(json.dumps({
                "ok": False,
                "error": "No model loaded on the server (check models/ directory and "
                         "that llama-cpp-python is installed in venvAI)."
            }), flush=True)
            continue

        try:
            full_parts = []
            stream = llm(
                prompt,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                stop=["</s>", "### User", "### Instruction"],
                stream=True,
            )
            for piece in stream:
                delta = piece["choices"][0]["text"]
                if delta:
                    full_parts.append(delta)
                    print(json.dumps({"chunk": delta}), flush=True)
            print(json.dumps({"done": True, "response": "".join(full_parts)}), flush=True)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"inference failed: {e}"}), flush=True)


if __name__ == "__main__":
    main()