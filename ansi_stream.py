"""
ansi_stream.py
--------------
Incrementally converts a stream of raw process output containing ANSI SGR
escape codes into HTML, without needing the full output buffered in memory.

Two things matter for a tool like LinPEAS piped into a Qt text widget:

1. SGR colour codes (16-colour, 256-colour, and truecolor 38;2;r;g;b /
   48;2;r;g;b) must render as real colour, not leak through as literal
   escape text.
2. '\\r' is used heavily by progress bars / spinners to redraw the same
   line in place. Without handling it, a scan floods the widget with
   thousands of near-duplicate lines — which is exactly the wall of
   garbage seen in the "before" screenshots.
"""
import re
import html as html_lib


class AnsiToHtmlStreamer:
    ANSI_RE = re.compile(r'\x1b\[([0-9;]*)([a-zA-Z])')

    BASIC_COLORS = {
        30: '#3b3b3b', 31: '#e06c75', 32: '#98c379', 33: '#e5c07b',
        34: '#61afef', 35: '#c678dd', 36: '#56b6c2', 37: '#d0d0d0',
        90: '#5c6370', 91: '#ff7b86', 92: '#b5e890', 93: '#ffd479',
        94: '#79c0ff', 95: '#e0a3ff', 96: '#7ee7e0', 97: '#ffffff',
    }

    def __init__(self):
        self.fg = None
        self.bg = None
        self.bold = False
        self._pending = ""        # possibly-incomplete escape sequence held over between feed() calls
        self._current_line = []   # list of pre-rendered span HTML strings for the still-open line

    # ---------------- style handling ----------------

    def _span(self, text):
        if not text:
            return ""
        styles = []
        if self.fg:
            styles.append(f"color:{self.fg}")
        if self.bg:
            styles.append(f"background-color:{self.bg}")
        if self.bold:
            styles.append("font-weight:600")
        escaped = html_lib.escape(text)
        if not styles:
            return escaped
        return f'<span style="{";".join(styles)}">{escaped}</span>'

    def _apply_sgr(self, params):
        codes = [int(p) if p else 0 for p in params.split(";")] if params else [0]
        i = 0
        while i < len(codes):
            code = codes[i]
            if code == 0:
                self.fg, self.bg, self.bold = None, None, False
            elif code == 1:
                self.bold = True
            elif code == 22:
                self.bold = False
            elif code == 39:
                self.fg = None
            elif code == 49:
                self.bg = None
            elif code in self.BASIC_COLORS:
                self.fg = self.BASIC_COLORS[code]
            elif 40 <= code <= 47:
                self.bg = self.BASIC_COLORS.get(code - 10, '#444444')
            elif 100 <= code <= 107:
                self.bg = self.BASIC_COLORS.get(code - 10, '#444444')
            elif code == 38 and i + 1 < len(codes):
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    self.fg = self._xterm256(codes[i + 2]); i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    self.fg = f'rgb({codes[i+2]},{codes[i+3]},{codes[i+4]})'; i += 4
            elif code == 48 and i + 1 < len(codes):
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    self.bg = self._xterm256(codes[i + 2]); i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    self.bg = f'rgb({codes[i+2]},{codes[i+3]},{codes[i+4]})'; i += 4
            i += 1

    @staticmethod
    def _xterm256(n):
        basic16 = ['#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0',
                   '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff']
        if n < 16:
            return basic16[n]
        if n <= 231:
            n -= 16
            r, g, b = (n // 36) % 6, (n // 6) % 6, n % 6
            scale = lambda v: 55 + v * 40 if v else 0
            return f'rgb({scale(r)},{scale(g)},{scale(b)})'
        grey = 8 + (n - 232) * 10
        return f'rgb({grey},{grey},{grey})'

    # ---------------- streaming feed ----------------

    def feed(self, raw):
        """
        Feed one chunk of raw process output.

        Returns (new_committed_lines, current_line_html):
          - new_committed_lines: list of finished lines (HTML), oldest first,
            that the caller should APPEND.
          - current_line_html: latest state of the still-open (not yet
            newline-terminated) line. The caller should REPLACE whatever it
            last displayed for the in-progress line with this.
        """
        text = self._pending + raw
        self._pending = ""

        m = re.search(r'\x1b(\[[0-9;]*)?$', text)
        if m:
            self._pending = text[m.start():]
            text = text[:m.start()]

        new_committed = []
        pos = 0
        for match in self.ANSI_RE.finditer(text):
            self._consume_literal(text[pos:match.start()], new_committed)
            if match.group(2) == 'm':
                self._apply_sgr(match.group(1))
            pos = match.end()
        self._consume_literal(text[pos:], new_committed)

        current_html = "".join(self._current_line)
        return new_committed, current_html

    def _consume_literal(self, literal, new_committed):
        if not literal:
            return
        idx = 0
        n = len(literal)
        while idx < n:
            nxt_r = literal.find('\r', idx)
            nxt_n = literal.find('\n', idx)
            candidates = [x for x in (nxt_r, nxt_n) if x != -1]
            if not candidates:
                chunk = literal[idx:]
                if chunk:
                    self._current_line.append(self._span(chunk))
                break
            nxt = min(candidates)
            chunk = literal[idx:nxt]
            if chunk:
                self._current_line.append(self._span(chunk))
            if literal[nxt] == '\r':
                self._current_line = []  # progress-bar style redraw: discard, don't commit
            else:
                new_committed.append("".join(self._current_line))
                self._current_line = []
            idx = nxt + 1

    def flush_remaining(self):
        """Call once the process exits, to commit any still-open final line."""
        if self._current_line:
            line = "".join(self._current_line)
            self._current_line = []
            return line
        return None