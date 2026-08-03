#!/usr/bin/env python3
"""
Beautiful GUI Chat with Streaming Responses
Real AI responses that appear word-by-word like typing
"""

import sys
from pathlib import Path
from threading import Thread
import tkinter as tk
from tkinter import scrolledtext, filedialog
import queue
import time

try:
    from llama_cpp import Llama
except ImportError:
    print("Installing llama-cpp-python...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
    from llama_cpp import Llama

MODELS_DIR = Path(__file__).parent / "models"

class RealLLMChat:
    def __init__(self):
        """Initialize with real model"""
        models = list(MODELS_DIR.glob("*.gguf"))
        
        if not models:
            print("Oops Please contact +255688115216 For assistance.")
            sys.exit(1)
        
        model_path = models[0]
        print(f"Loading model: {model_path.name}")
        
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0,
            verbose=False
        )
        
        print("Model loaded!")
        self.conversation = []

    # --- New helper methods for summarization and chunked Q&A ---
    def summarize_text(self, text: str, max_tokens: int = 180) -> str:
        """Return a concise summary (bullet points) of `text` using the model."""
        prompt = (
            "Summarize the following text in clear concise bullet points."
            f" Keep it brief and focused.\n\n{text}\n\nSummary:\n"
        )
        try:
            resp = self.llm(prompt, max_tokens=max_tokens, temperature=0.2, top_p=0.9)
            # robust parsing for different llama-cpp return formats
            try:
                choice = resp.get("choices", [])[0]
                text_out = choice.get("text") or (choice.get("message") or {}).get("content")
            except Exception:
                text_out = None
            if not text_out:
                # try alternative fields
                text_out = resp.get("output") if isinstance(resp, dict) else None
            if text_out:
                return str(text_out).strip()
            return text[:500].strip()
        except Exception:
            return text[:500].strip()

    def answer_on_text(self, text: str, question: str, max_tokens: int = 256) -> str:
        """Ask the model a question about `text` and return the answer."""
        prompt = f"Text:\n{text}\n\nQuestion: {question}\nAnswer:"
        resp = self.llm(prompt, max_tokens=max_tokens, temperature=0.7, top_p=0.95)
        try:
            choice = resp.get("choices", [])[0]
            text_out = choice.get("text") or (choice.get("message") or {}).get("content")
        except Exception:
            text_out = None
        if not text_out:
            text_out = resp.get("output") if isinstance(resp, dict) else None
        if not text_out:
            return "(no answer from model)"
        return str(text_out).strip()

    def answer_on_chunks(self, question: str, chunks: list[str], max_tokens: int = 256):
        """Answer `question` for each chunk; return list of answers."""
        answers = []
        for i, chunk in enumerate(chunks):
            try:
                ans = self.answer_on_text(chunk, question, max_tokens=max_tokens)
            except Exception:
                ans = "(error while answering this chunk)"
            answers.append(ans)
        return answers
    
    def stream_chat(self, user_input):
        """Stream response word by word"""
        # Sanitize user input before storing (truncate file contexts if present)
        def sanitize_user_input(text: str, chars_budget: int = 2000) -> str:
            if "[File Context]" in text:
                try:
                    return truncate_file_context(text, chars_budget)
                except Exception:
                    # fallback to a safe tail slice
                    return text[-chars_budget:]
            return text

        sanitized_input = sanitize_user_input(user_input, chars_budget=2000)
        # Append sanitized content to conversation history
        self.conversation.append({"role": "user", "content": sanitized_input})

        system = "You are a helpful assistant."

        # Helper: estimate tokens (roughly 4 chars per token)
        def estimate_tokens(s: str) -> int:
            return max(1, int(len(s) / 4))

        # Helper: truncate long file contexts in a message payload
        def truncate_file_context(text: str, max_chars: int) -> str:
            # If no file context marker present, just trim to max_chars
            if "[File Context]" not in text:
                return text[-max_chars:]

            parts = text.split("[File Context]")
            before = parts[0]
            rest = "[File Context]" + parts[1]

            # Split files from user question
            if "[User Question]" in rest:
                files_part, user_q = rest.split("[User Question]", 1)
            else:
                files_part, user_q = rest, ""

            # Find each File: header and its content
            file_sections = []
            current = None
            for line in files_part.splitlines(True):
                if line.startswith("File:"):
                    if current:
                        file_sections.append(current)
                    current = line
                else:
                    if current is None:
                        current = line
                    else:
                        current += line
            if current:
                file_sections.append(current)

            # Allocate characters per file (evenly)
            n_files = max(1, len(file_sections))
            per_file = max(200, int(max_chars / n_files))

            trimmed = []
            for sec in file_sections:
                # Keep header (File: name) and first/last slice of content
                header, _, body = sec.partition("\n")
                body = body or ""
                if len(body) > per_file:
                    # Keep start + ellipsis + end
                    keep = int(per_file / 2)
                    body = body[:keep] + "\n\n...\n\n" + body[-keep:]
                trimmed.append(header + "\n" + body)

            new_files_part = "\n".join(trimmed)
            return before + "[File Context]" + new_files_part + "[User Question]" + user_q

        # Build prompt using last few messages but be token-aware
        # Safely obtain model context size (some Llama wrappers expose n_ctx as method)
        raw_ctx = getattr(self.llm, "n_ctx", None)
        try:
            if callable(raw_ctx):
                max_ctx = int(raw_ctx())
            else:
                max_ctx = int(raw_ctx) if raw_ctx is not None else 2048
        except Exception:
            max_ctx = 2048
        max_response_tokens = 256
        reserved_tokens = max_response_tokens + 100  # safety margin

        # First assemble a simple prompt from recent history
        prompt = system + "\n\n"
        # Use only the last few messages to keep prompt small
        recent = self.conversation[-8:]
        for msg in recent:
            if msg["role"] == "user":
                prompt += f"Q: {msg['content']}\n"
            else:
                prompt += f"A: {msg['content']}\n"

        prompt += "A:"

        # If estimated tokens exceed context window, try to trim file contexts
        est = estimate_tokens(prompt)
        if est + reserved_tokens > max_ctx:
            # Attempt to trim file-containing user messages
            trimmed_recent = []
            for msg in recent:
                content = msg["content"]
                if "[File Context]" in content:
                    # Allow total of ~ (max_ctx - reserved_tokens) chars for all files
                    chars_budget = max(1000, int((max_ctx - reserved_tokens) * 4 / 3))
                    content = truncate_file_context(content, chars_budget)
                trimmed_recent.append({"role": msg["role"], "content": content})

            # Rebuild prompt from trimmed_recent
            prompt = system + "\n\n"
            for msg in trimmed_recent:
                if msg["role"] == "user":
                    prompt += f"Q: {msg['content']}\n"
                else:
                    prompt += f"A: {msg['content']}\n"
            prompt += "A:"

            est = estimate_tokens(prompt)

        # As a last resort, if still too large, truncate prompt tail
        if est + reserved_tokens > max_ctx:
            # Convert to chars and trim from the front
            allowed_chars = max(500, int((max_ctx - reserved_tokens) * 4))
            prompt = prompt[-allowed_chars:]

        response = self.llm(
            prompt,
            max_tokens=max_response_tokens,
            temperature=0.8,
            top_p=0.95,
            stop=["Q:", "\n\nQ"]
        )

        text = response["choices"][0]["text"].strip()
        self.conversation.append({"role": "assistant", "content": text})

        return text


class BeautifulChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cyberkiddle AI")
        self.root.geometry("900x700")
        # Fixed-size window
        self.root.resizable(False, False)
        
        # Dark theme colors
        self.bg_primary = "#0f0f17"
        self.bg_secondary = "#36374B"
        self.accent_blue = "#FEFEFE"
        self.accent_green = "#F9D73D"
        self.accent_red = "#000000"
        self.text_primary = "#e5e5e5"
        self.text_secondary = "#ffffff"
        
        self.root.configure(bg=self.bg_primary)
        
        print("Initializing AI...")
        self.ai = RealLLMChat()
        print("Ready!")
        
        self.response_queue = queue.Queue()
        self.is_responding = False
        self.partial_active = False
        self.uploaded_files = []  # Store uploaded file contents
        # Top-right header status animation state
        self._status_anim_active = False
        self._status_anim_state = False
        
        self.create_widgets()
        self.check_responses()
        self.input_field.focus()
    
    def create_widgets(self):
        """Create beautiful UI"""
        # Header with gradient effect
        header = tk.Frame(self.root, bg=self.bg_secondary, height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        # Logo (left) if available
        logo_path = Path(__file__).parent / "robot.png"
        self.logo_img = None
        if logo_path.exists():
            try:
                tmp_img = tk.PhotoImage(file=str(logo_path))
                # downscale large images to keep the header tidy
                try:
                    w = tmp_img.width()
                    h = tmp_img.height()
                    max_dim = 64
                    if max(w, h) > max_dim:
                        factor = max(1, int(max(w, h) / max_dim))
                        self.logo_img = tmp_img.subsample(factor, factor)
                    else:
                        self.logo_img = tmp_img
                except Exception:
                    self.logo_img = tmp_img

                logo_label = tk.Label(header, image=self.logo_img, bg=self.bg_secondary)
                logo_label.pack(side=tk.LEFT, padx=8, pady=8)
            except Exception:
                # ignore image errors and continue
                self.logo_img = None

        # Title (left) and status (right)
        title_frame = tk.Frame(header, bg=self.bg_secondary)
        title_frame.pack(side=tk.LEFT, anchor="w", padx=12)

        title = tk.Label(
            title_frame,
            text="AI Assistant",
            font=("Segoe UI", 22, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_green
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            title_frame,
            text="Created by: Rodgers Omben.",
            font=("Segoe UI", 10),
            bg=self.bg_secondary,
            fg=self.text_secondary
        )
        subtitle.pack(anchor="w")

        # Top-right status indicator
        status_frame = tk.Frame(header, bg=self.bg_secondary)
        status_frame.pack(side=tk.RIGHT, anchor="e", padx=12, pady=10)

        # small circular dot to the left of the text
        self.status_dot = tk.Canvas(status_frame, width=12, height=12, bg=self.bg_secondary, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self._dot_oval = self.status_dot.create_oval(2, 2, 11, 11, fill=self.accent_green)

        self.header_status = tk.Label(
            status_frame,
            text="Ready",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_green
        )
        self.header_status.pack(side=tk.LEFT)

        # (theme button removed)
        
        # Separator
        sep1 = tk.Frame(self.root, bg=self.accent_blue, height=2)
        sep1.pack(fill=tk.X)
        
        # Chat display with dark theme
        chat_frame = tk.Frame(self.root, bg=self.bg_primary)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg=self.bg_primary,
            fg=self.text_primary,
            state=tk.DISABLED,
            height=20,
            relief=tk.FLAT,
            borderwidth=0,
            spacing3=8
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Center icon in chat area (laptop.png or fallback robot.png)
        icon_path = Path(__file__).parent / "laptop.png"
        if not icon_path.exists():
            icon_path = Path(__file__).parent / "robot.png"
        self.chat_icon_label = None
        self.chat_icon_img = None
        if icon_path.exists():
            try:
                tmp = tk.PhotoImage(file=str(icon_path))
                # scale down to max 128px
                try:
                    w = tmp.width()
                    h = tmp.height()
                    max_dim = 128
                    if max(w, h) > max_dim:
                        factor = max(1, int(max(w, h) / max_dim))
                        self.chat_icon_img = tmp.subsample(factor, factor)
                    else:
                        self.chat_icon_img = tmp
                except Exception:
                    self.chat_icon_img = tmp
                self.chat_icon_label = tk.Label(chat_frame, image=self.chat_icon_img, bg=self.bg_primary)
                # place at center of chat frame
                self.chat_icon_label.place(relx=0.5, rely=0.45, anchor="center")
            except Exception:
                self.chat_icon_label = None

        # Configure tags for beautiful styling
        self.chat_display.tag_config(
            "user_label",
            foreground=self.accent_blue,
            font=("Consolas", 11, "bold"),
            spacing1=10
        )
        self.chat_display.tag_config(
            "user_text",
            foreground=self.accent_blue,
            font=("Consolas", 11),
            lmargin2=20
        )
        self.chat_display.tag_config(
            "ai_label",
            foreground=self.accent_green,
            font=("Consolas", 11, "bold"),
            spacing1=10
        )
        self.chat_display.tag_config(
            "ai_text",
            foreground=self.text_primary,
            font=("Consolas", 11),
            lmargin2=20
        )
        self.chat_display.tag_config(
            "system",
            foreground=self.text_secondary,
            font=("Consolas", 10, "italic")
        )
        
        # Separator
        sep3 = tk.Frame(self.root, bg=self.accent_blue, height=1)
        sep3.pack(fill=tk.X)
        
        # Combined input frame with file button, input field, and send button
        input_frame = tk.Frame(self.root, bg=self.bg_secondary)
        input_frame.pack(fill=tk.X, padx=0, pady=0)
        
        input_container = tk.Frame(input_frame, bg=self.bg_secondary)
        input_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)
        
        # File upload button (left)
        upload_btn = tk.Button(
            input_container,
            text="Upload",
            command=self.upload_file,
            bg=self.accent_blue,
            fg=self.bg_primary,
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=5,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.accent_green,
        )
        upload_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Input field (middle, expanding)
        self.input_field = tk.Entry(
            input_container,
            font=("Segoe UI", 12),
            bg=self.bg_primary,
            fg=self.text_primary,
            relief=tk.FLAT,
            borderwidth=8,
            insertbackground=self.accent_blue
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.input_field.bind("<Return>", lambda e: self.send_message())
        
        # Send button (right)
        self.send_btn = tk.Button(
            input_container,
            text="Send",
            command=self.send_message,
            bg=self.accent_green,
            fg=self.bg_primary,
            font=("Segoe UI", 11, "bold"),
            padx=25,
            pady=8,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.accent_blue,
            activeforeground=self.bg_primary
        )
        self.send_btn.pack(side=tk.LEFT)

        # Clear conversation button (right of send)
        self.clear_btn = tk.Button(
            input_container,
            text="Clear",
            command=self.clear_conversation,
            bg=self.bg_secondary,
            fg=self.text_primary,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.accent_red,
            activeforeground=self.bg_primary
        )
        self.clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Copy last AI response
        self.copy_btn = tk.Button(
            input_container,
            text="Copy",
            command=self.copy_last_ai,
            bg=self.bg_secondary,
            fg=self.text_primary,
            font=("Segoe UI", 10),
            padx=8,
            pady=6,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.accent_blue,
        )
        self.copy_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Export conversation
        self.export_btn = tk.Button(
            input_container,
            text="Export",
            command=self.export_chat,
            bg=self.bg_secondary,
            fg=self.text_primary,
            font=("Segoe UI", 10),
            padx=8,
            pady=6,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.accent_blue,
        )
        self.export_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Upload stop button (hidden until analyzing)
        self.upload_stop_btn = tk.Button(
            input_container,
            text="Stop",
            command=self._request_upload_stop,
            bg=self.accent_red,
            fg=self.bg_primary,
            font=("Segoe UI", 10),
            padx=8,
            pady=6,
            relief=tk.FLAT,
            cursor="hand2",
        )
        self.upload_stop_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.upload_stop_btn.pack_forget()

        # internal stop/response control
        self._response_thread = None
        self._stop_requested = False
        
        # Separator (pack AFTER input_frame for correct ordering)
        sep2 = tk.Frame(self.root, bg=self.accent_blue, height=1)
        sep2.pack(fill=tk.X)
        
        # File status label (hidden, for feedback)
        self.file_status = tk.Label(
            self.root,
            text="",
            bg=self.bg_secondary,
            fg=self.text_secondary,
            font=("Segoe UI", 8)
        )
        self.file_status.pack(fill=tk.X, padx=15)
        
        # Status bar
        self.status = tk.Label(
            self.root,
            text="Ready to chat!",
            bg=self.bg_secondary,
            fg=self.accent_green,
            font=("Segoe UI", 9),
            pady=5
        )
        self.status.pack(fill=tk.X)
        
        # Welcome message
        self.add_message("Welcome to AI Chat!", "system")
        self.add_message("Ask me anything and I'll respond with real AI intelligence.", "system")
        self.add_message("Responses will appear naturally as they're generated.", "system")
    
    def add_message(self, text, sender="user"):
        """Add message to chat display"""
        # hide center icon when conversational messages appear
        if sender in ("user", "assistant") and getattr(self, 'chat_icon_label', None):
            try:
                self.chat_icon_label.place_forget()
            except Exception:
                pass

        self.chat_display.config(state=tk.NORMAL)

        if sender == "user":
            self.chat_display.insert(tk.END, "You: ", "user_label")
            self.chat_display.insert(tk.END, text + "\n\n", "user_text")
        elif sender == "assistant":
            self.chat_display.insert(tk.END, "AI: ", "ai_label")
            self.chat_display.insert(tk.END, text, "ai_text")
        else:
            self.chat_display.insert(tk.END, "Info: " + text + "\n", "system")

        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def stream_response(self, text):
        """Stream response word by word"""
        words = text.split()
        
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "AI: ", "ai_label")
        
        for word in words:
            self.chat_display.insert(tk.END, word + " ", "ai_text")
            self.chat_display.see(tk.END)
            self.root.update()
            time.sleep(0.05)  # Typing speed
        
        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.config(state=tk.DISABLED)

    def stream_partial(self, text):
        """Stream a partial chunk of assistant text without repeating the AI label."""
        words = text.split()
        self.chat_display.config(state=tk.NORMAL)
        for word in words:
            self.chat_display.insert(tk.END, word + " ", "ai_text")
            self.chat_display.see(tk.END)
            self.root.update()
            time.sleep(0.005)
        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.config(state=tk.DISABLED)

    def _start_response_ui(self):
        """Switch UI to responding state: change Send -> Stop, disable input."""
        self.is_responding = True
        self._stop_requested = False
        try:
            self.input_field.config(state=tk.DISABLED)
            self.send_btn.config(text="Stop", bg=self.accent_red, command=self._request_stop)
            self.update_header_status("Thinking...", fg=self.accent_blue, thinking=True)
        except Exception:
            pass

    def _finalize_response_ui(self):
        """Reset UI after response finished or stopped."""
        self.is_responding = False
        self._stop_requested = False
        try:
            self.input_field.config(state=tk.NORMAL)
            self.send_btn.config(text="Send", bg=self.accent_green, command=self.send_message)
            self.update_header_status("Ready", fg=self.accent_green, thinking=False)
        except Exception:
            pass

    def _request_stop(self):
        """User requested to stop current response."""
        self._stop_requested = True
        # give immediate feedback
        self.update_header_status("Stopping...", fg=self.accent_red, thinking=False)

    def _request_upload_stop(self):
        """User requested to stop ongoing upload analysis."""
        self._upload_stop_requested = True
        # update UI immediately
        try:
            self.upload_stop_btn.config(text="Stopping...", state=tk.DISABLED)
        except Exception:
            pass
        self.update_header_status("Stopping analysis...", fg=self.accent_red, thinking=False)

    def clear_conversation(self):
        """Clear the current conversation/context so the AI starts fresh."""
        try:
            # Reset model conversation history
            if hasattr(self, 'ai') and getattr(self.ai, 'conversation', None) is not None:
                self.ai.conversation = []

            # Reset flags
            self.partial_active = False
            self.is_responding = False

            # Clear chat display and show a system note
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)

            self.add_message("Conversation cleared. AI context reset.", "system")
            # show center icon again if present
            if getattr(self, 'chat_icon_label', None):
                try:
                    self.chat_icon_label.place(relx=0.5, rely=0.45, anchor="center")
                except Exception:
                    pass
            self.update_header_status("Ready", fg=self.accent_green, thinking=False)
        except Exception as e:
            self.add_message(f"Error clearing conversation: {e}", "system")

    def update_header_status(self, text: str, fg: str = None, thinking: bool = False):
        """Update the top-right header status and optionally start/stop the thinking animation."""
        fg = fg or self.accent_green
        try:
            self.header_status.config(text=text, fg=fg)
            # update dot color
            if thinking:
                self.status_dot.itemconfig(self._dot_oval, fill=self.accent_blue)
                if not self._status_anim_active:
                    self._status_anim_active = True
                    self._animate_status_dot()
            else:
                self._status_anim_active = False
                self.status_dot.itemconfig(self._dot_oval, fill=fg)
        except Exception:
            pass

    def toggle_theme(self):
        """Toggle between dark and light themes and apply to main widgets."""
        try:
            self.dark_mode = not getattr(self, 'dark_mode', True)
            if self.dark_mode:
                # dark
                self.bg_primary = "#1e1e2e"
                self.bg_secondary = "#313244"
                self.accent_blue = "#89b4fa"
                self.accent_green = "#94e2d5"
                self.text_primary = "#cdd6f4"
                self.text_secondary = "#a6adc8"
                self.accent_red = "#f38ba8"
            else:
                # light
                self.bg_primary = "#ffffff"
                self.bg_secondary = "#f3f4f6"
                self.accent_blue = "#2b6cb0"
                self.accent_green = "#2f855a"
                self.text_primary = "#0f172a"
                self.text_secondary = "#475569"
                self.accent_red = "#e53e3e"

            # apply to main areas
            try:
                self.root.configure(bg=self.bg_primary)
            except Exception:
                pass
            try:
                self.chat_display.config(bg=self.bg_primary, fg=self.text_primary)
            except Exception:
                pass
            try:
                self.input_field.config(bg=self.bg_primary, fg=self.text_primary, insertbackground=self.accent_blue)
            except Exception:
                pass
            try:
                self.send_btn.config(bg=self.accent_green if self.dark_mode else self.accent_blue)
                self.clear_btn.config(bg=self.bg_secondary)
                self.copy_btn.config(bg=self.bg_secondary)
                self.export_btn.config(bg=self.bg_secondary)
            except Exception:
                pass
            try:
                self.file_status.config(bg=self.bg_secondary, fg=self.text_secondary)
                self.status.config(bg=self.bg_secondary, fg=self.accent_green if self.dark_mode else self.text_secondary)
                self.header_status.config(bg=self.bg_secondary, fg=self.accent_green if self.dark_mode else self.text_secondary)
            except Exception:
                pass
        except Exception:
            pass


    def copy_last_ai(self):
        """Copy the last AI response to clipboard."""
        try:
            full = self.chat_display.get("1.0", tk.END).strip()
            idx = full.rfind("AI:")
            if idx == -1:
                # nothing to copy
                self.add_message("No AI response found to copy.", "system")
                return
            last = full[idx+3:].strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(last)
            self.add_message("Last AI response copied to clipboard.", "system")
        except Exception as e:
            self.add_message(f"Copy failed: {e}", "system")

    def export_chat(self):
        """Export full conversation to a text file."""
        try:
            fname = filedialog.asksaveasfilename(title="Export conversation", defaultextension=".txt", filetypes=[("Text files","*.txt")])
            if not fname:
                return
            content = self.chat_display.get("1.0", tk.END)
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(content)
            self.add_message(f"Conversation exported to: {Path(fname).name}", "system")
        except Exception as e:
            self.add_message(f"Export failed: {e}", "system")

    def _animate_status_dot(self):
        """Simple blink/pulse animation for status dot while thinking."""
        if not getattr(self, '_status_anim_active', False):
            return
        # toggle slightly between two opacities (simulate pulse)
        try:
            self._status_anim_state = not self._status_anim_state
            color = self.accent_blue if self._status_anim_state else self.accent_green
            self.status_dot.itemconfig(self._dot_oval, fill=color)
            # schedule next frame
            self.root.after(500, self._animate_status_dot)
        except Exception:
            self._status_anim_active = False
    
    def upload_file(self):
        """Upload and analyze a file"""
        file_path = filedialog.askopenfilename(
            title="Upload file for analysis",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        # show uploading status and read file
        try:
            self.update_header_status("Uploading...", fg=self.accent_blue, thinking=True)
            self.file_status.config(text="Uploading...", fg=self.text_secondary)
            self.root.update()

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            file_name = Path(file_path).name
            file_size = len(content)

            # Truncate large files for prompt context (keep head + tail)
            def make_truncated(s: str, max_chars: int = 3000) -> str:
                if len(s) <= max_chars:
                    return s
                keep = max_chars // 2
                return s[:keep] + "\n\n...TRUNCATED...\n\n" + s[-keep:]

            truncated = make_truncated(content, max_chars=3000)

            # Build smaller chunks for detailed per-chunk QA
            chunk_size = 1500
            chunks = []
            i = 0
            while i < len(content):
                chunks.append(content[i:i+chunk_size])
                i += chunk_size

            # Start background analysis so user can cancel
            self._upload_stop_requested = False
            self.upload_stop_btn.pack(side=tk.LEFT, padx=(8,0))
            self.update_header_status("Analyzing file...", fg=self.accent_blue, thinking=True)
            self.file_status.config(text=f"Analyzing: {file_name}", fg=self.text_secondary)
            self.root.update()

            def _analyze():
                try:
                    summary = None
                    try:
                        summary = self.ai.summarize_text(truncated, max_tokens=180)
                    except Exception:
                        summary = truncated[:600]

                    # if user requested stop, abort storing
                    if getattr(self, '_upload_stop_requested', False):
                        def _cancel_ui():
                            self.file_status.config(text=f"Analysis canceled: {file_name}", fg=self.accent_red)
                            self.update_header_status("Ready", fg=self.accent_green, thinking=False)
                            try:
                                self.upload_stop_btn.pack_forget()
                            except Exception:
                                pass
                            self.add_message(f"Analysis canceled for: {file_name}", "system")
                        self.root.after(0, _cancel_ui)
                        return

                    # store file info on the main thread
                    def _store_ui():
                        self.uploaded_files.append({
                            "name": file_name,
                            "content": content,
                            "truncated": truncated,
                            "chunks": chunks,
                            "summary": summary,
                            "size": file_size
                        })
                        self.file_status.config(text=f"Uploaded: {file_name} ({file_size} chars)", fg=self.accent_green)
                        self.update_header_status("Ready", fg=self.accent_green, thinking=False)
                        try:
                            self.upload_stop_btn.pack_forget()
                        except Exception:
                            pass
                        self.add_message(f"Uploaded file: {file_name}\n\nYou can now ask questions about this file! (content trimmed for context)", "system")
                    self.root.after(0, _store_ui)
                except Exception as e:
                    def _err_ui():
                        self.file_status.config(text=f"Analysis failed", fg=self.accent_red)
                        self.update_header_status("Upload failed", fg=self.accent_red, thinking=False)
                        try:
                            self.upload_stop_btn.pack_forget()
                        except Exception:
                            pass
                        self.add_message(f"Error analyzing file: {e}", "system")
                    self.root.after(0, _err_ui)

            t = Thread(target=_analyze)
            t.daemon = True
            t.start()
            
        except Exception as e:
            self.add_message(f"Error reading file: {str(e)}", "system")
            self.file_status.config(text="Upload failed", fg=self.accent_red)
            self.update_header_status("Upload failed", fg=self.accent_red, thinking=False)
    
    def send_message(self):
        """Send message and get streaming response"""
        message = self.input_field.get().strip()
        
        if not message or self.is_responding:
            return
        
        # If files are uploaded, decide strategy:
        # - For generic 'explain' or 'detail' requests: run chunked Q&A across chunks
        # - Otherwise include the concise summaries in the prompt
        if self.uploaded_files:
            lower = message.lower()
            keywords = ("explain", "detail", "detailed", "full", "analyze", "describe", "what is")
            if any(k in lower for k in keywords) and len(message) < 120:
                # Start chunked Q&A flow in background
                self.add_message(self.input_field.get().strip(), "user")
                self.input_field.delete(0, tk.END)
                # update UI and spawn worker
                self._start_response_ui()
                thread = Thread(target=self.get_ai_response_chunked, args=(message,))
                thread.daemon = True
                self._response_thread = thread
                thread.start()
                return
            else:
                # Use summaries for quick context
                file_context = "\n\n".join([f"File: {f['name']}\nSummary: {f.get('summary', f.get('truncated',''))}" for f in self.uploaded_files])
                message = f"[File Context]\n{file_context}\n\n[User Question]\n{message}"
        
        self.add_message(self.input_field.get().strip(), "user")
        self.input_field.delete(0, tk.END)
        
        # update UI and spawn worker
        self._start_response_ui()
        self.root.update()
        thread = Thread(target=self.get_ai_response, args=(message,))
        thread.daemon = True
        self._response_thread = thread
        thread.start()

    def get_ai_response_chunked(self, user_message):
        """Process a question against each chunk and stream partial answers back."""
        try:
            # For each uploaded file, run per-chunk QA
            for f in self.uploaded_files:
                chunks = f.get("chunks", [])
                if not chunks:
                    continue
                # Announce file
                self.response_queue.put(("partial", f"--- Answers for {f['name']} ---\n"))
                # Process and enqueue each chunk answer immediately so UI can stream them
                for i, chunk in enumerate(chunks):
                    # allow user to stop between chunks
                    if getattr(self, '_stop_requested', False):
                        self.response_queue.put(("error", "Stopped by user."))
                        return
                    try:
                        ans = self.ai.answer_on_text(chunk, user_message, max_tokens=220)
                    except Exception:
                        ans = "(error while answering this chunk)"
                    if not isinstance(ans, str) or not ans.strip():
                        ans = "(no answer for this chunk)"
                    header = f"[Part {i+1}/{len(chunks)}]\n"
                    # push a short info snippet first for visibility
                    info = f"[len={len(ans)}] " + (ans[:120].replace('\n',' ') + ('...' if len(ans)>120 else ''))
                    self.response_queue.put(("partial", header + info + "\n"))
                    # then push the actual answer
                    self.response_queue.put(("partial", ans + "\n\n"))
            # Signal completion
            self.response_queue.put(("success", "Chunked answers complete."))
        except Exception as e:
            self.response_queue.put(("error", str(e)))
    
    def get_ai_response(self, user_message):
        """Get AI response in background"""
        try:
            response = self.ai.stream_chat(user_message)
            if getattr(self, '_stop_requested', False):
                self.response_queue.put(("error", "Stopped by user."))
            else:
                self.response_queue.put(("success", response))
        except Exception as e:
            if getattr(self, '_stop_requested', False):
                self.response_queue.put(("error", "Stopped by user."))
            else:
                self.response_queue.put(("error", str(e)))
    
    def check_responses(self):
        """Check for AI responses"""
        try:
            status, response = self.response_queue.get_nowait()

            if status == "success":
                # Final successful response (could be chunked-complete message)
                if isinstance(response, str) and response.strip().endswith("complete."):
                    # final notification only
                    self.add_message(response, "system")
                else:
                    self.stream_response(response)
                # If we were streaming partials, close that flow
                if getattr(self, 'partial_active', False):
                    self.partial_active = False
                # finalize UI after success
                self._finalize_response_ui()

            elif status == "partial":
                # Partial chunk from chunked QA — stream inline as part of the same AI message
                if not getattr(self, 'partial_active', False):
                    # Start a continuous AI message in the ScrolledText
                    self.chat_display.config(state=tk.NORMAL)
                    self.chat_display.insert(tk.END, "AI: ", "ai_label")
                    self.chat_display.config(state=tk.DISABLED)
                    self.partial_active = True
                # Stream the partial content inline
                self.stream_partial(response)
                self.update_header_status("Receiving chunked answers...", fg=self.accent_blue, thinking=True)

            else:
                # Treat other statuses as errors/stops
                self.add_message(str(response), "system")
                # finalize UI on error/stop
                self._finalize_response_ui()
        
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_responses)


class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Chat - Real LLM")
        self.root.geometry("800x600")
        self.root.configure(bg="#f0f0f0")
        
        # Initialize AI
        print("Initializing AI...")
        self.ai = RealLLMChat()
        print("Ready!")
        
        # Response queue for thread safety
        self.response_queue = queue.Queue()
        
        # Create UI
        self.create_widgets()
        
        # Check for responses
        self.check_responses()
    
    def create_widgets(self):
        """Create GUI elements"""
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        
        title = tk.Label(
            header,
            text="AI Chat - Real LLM Responses",
            font=("Arial", 16, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=10)
        
        # Chat display
        chat_frame = tk.Frame(self.root, bg="white")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg="white",
            fg="#2c3e50",
            state=tk.DISABLED,
            height=20
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Configure tags for styling
        self.chat_display.tag_config("user", foreground="#3498db", font=("Courier", 10, "bold"))
        self.chat_display.tag_config("assistant", foreground="#27ae60", font=("Courier", 10, "bold"))
        self.chat_display.tag_config("system", foreground="#7f8c8d", font=("Courier", 9, "italic"))
        
        # Input frame
        input_frame = tk.Frame(self.root, bg="#ecf0f1")
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.input_field = tk.Entry(
            input_frame,
            font=("Arial", 12),
            bg="white",
            fg="#2c3e50"
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.input_field.bind("<Return>", lambda e: self.send_message())
        
        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg="#3498db",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            cursor="hand2"
        )
        send_btn.pack(side=tk.LEFT)
        
        # Status bar
        self.status = tk.Label(
            self.root,
            text="Ready to chat!",
            bg="#ecf0f1",
            fg="#7f8c8d",
            font=("Arial", 9)
        )
        self.status.pack(fill=tk.X, padx=10, pady=5)
        
        # Add welcome message
        self.add_message("Welcome to AI Chat!", "system")
        self.add_message("Ask me anything and I'll give you real AI responses!", "system")
    
    def add_message(self, text, sender="user"):
        """Add message to chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        if sender == "user":
            self.chat_display.insert(tk.END, "You: ", "user")
        elif sender == "assistant":
            self.chat_display.insert(tk.END, "AI: ", "assistant")
        else:
            self.chat_display.insert(tk.END, "Info: " + text + "\n", "system")
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    gui = BeautifulChatGUI(root)
    root.mainloop()