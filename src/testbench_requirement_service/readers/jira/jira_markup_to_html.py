import html
import re
from typing import ClassVar


class _JiraMarkupToHtmlConverter:
    """Converts Jira wiki markup to HTML."""

    _HEADING_RE = re.compile(r"^h([1-6])\.\s+(.*)$")
    _LIST_RE = re.compile(r"^([*#]+)\s+(.*)$")
    _TABLE_RE = re.compile(r"^\|.*\|$")
    _CODE_OPEN_RE = re.compile(r"^\{code(?::([^}]+))?\}$")
    _PANEL_OPEN_RE = re.compile(r"^\{panel(?::([^}]*))?\}$")
    _COLOR_RE = re.compile(r"\{color:([^}]+)\}(.*?)\{color\}", re.DOTALL)
    _IMAGE_RE = re.compile(r"!(?P<src>[^!|]+?)(?:\|(?P<props>[^!]+))?!")
    _LINK_WITH_TEXT_RE = re.compile(r"\[(?P<label>[^\]|]+)\|(?P<href>[^\]]+)\]")
    _LINK_SIMPLE_RE = re.compile(r"\[(?P<href>https?://[^\]]+)\]")

    _PANEL_STYLE_MAP: ClassVar = {
        "borderStyle": "border-style",
        "borderColor": "border-color",
        "borderWidth": "border-width",
        "bgColor": "background-color",
    }

    _INLINE_FORMAT_PATTERNS: ClassVar = [
        (re.compile(r"\{\{(.+?)\}\}", re.DOTALL), "code"),
        (re.compile(r"\?\?(?=\S)(.+?)(?<=\S)\?\?", re.DOTALL), "cite"),
        (re.compile(r"(?<!\w)\*(?=\S)(.+?)(?<=\S)\*(?!\w)", re.DOTALL), "strong"),
        (re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)", re.DOTALL), "em"),
        (re.compile(r"(?<!\w)\+(?=\S)(.+?)(?<=\S)\+(?!\w)", re.DOTALL), "u"),
        (re.compile(r"(?<!\w)-(?=\S)(.+?)(?<=\S)-(?!\w)", re.DOTALL), "del"),
        (re.compile(r"(?<!\w)~(?=\S)(.+?)(?<=\S)~(?!\w)", re.DOTALL), "sub"),
        (re.compile(r"(?<!\w)\^(?=\S)(.+?)(?<=\S)\^(?!\w)", re.DOTALL), "sup"),
    ]

    _EMOTICON_CLASS_MAP: ClassVar = {
        "(*y)": "star-yellow",
        "(*r)": "star-red",
        "(*g)": "star-green",
        "(*b)": "star-blue",
        "(flag)": "flag",
        "(on)": "lightbulb-on",
        "(off)": "lightbulb-off",
        "(/)": "check",
        "(!)": "warning",
        "(-)": "forbidden",
        "(+)": "add",
        "(?)": "help",
        "(y)": "thumbs-up",
        "(n)": "thumbs-down",
        "(i)": "information",
        "(x)": "error",
        ":)": "smile",
        ":(": "sad",
        ":P": "tongue",
        ":D": "biggrin",
        ";)": "wink",
    }

    def __init__(self) -> None:
        emoticons = sorted(self._EMOTICON_CLASS_MAP, key=len, reverse=True)
        self._emoticon_re = re.compile("|".join(re.escape(token) for token in emoticons))

    def convert(self, jira_text: str) -> str:
        if not jira_text or not jira_text.strip():
            return ""

        normalized = jira_text.replace("\r\n", "\n").replace("\r", "\n")
        converted = self._convert_blocks(normalized)
        return re.sub(r"\n{3,}", "\n\n", converted).strip()

    def _convert_blocks(self, text: str) -> str:  # noqa: C901
        lines = text.split("\n")
        parts = []
        i = 0

        while i < len(lines):
            raw_line = lines[i]
            stripped = raw_line.strip()

            if not stripped:
                i += 1
                continue

            code_open = self._CODE_OPEN_RE.match(stripped)
            if code_open:
                body, i = self._consume_until(lines, i + 1, "{code}")
                language = self._extract_code_language(code_open.group(1))
                parts.append(self._render_code_block(body, language))
                continue

            if stripped == "{noformat}":
                body, i = self._consume_until(lines, i + 1, "{noformat}")
                parts.append(f"<pre>{html.escape(body)}</pre>")
                continue

            if stripped == "{quote}":
                body, i = self._consume_until(lines, i + 1, "{quote}")
                quote_inner = self._convert_blocks(body)
                parts.append(f"<blockquote>{quote_inner}</blockquote>")
                continue

            panel_open = self._PANEL_OPEN_RE.match(stripped)
            if panel_open:
                body, i = self._consume_until(lines, i + 1, "{panel}")
                panel_inner = self._convert_blocks(body)
                parts.append(self._render_panel(panel_open.group(1), panel_inner))
                continue

            heading_match = self._HEADING_RE.match(stripped)
            if heading_match:
                level, heading_text = heading_match.groups()
                parts.append(f"<h{level}>{self._convert_inline(heading_text)}</h{level}>")
                i += 1
                continue

            if stripped == "----":
                parts.append("<hr />")
                i += 1
                continue

            if self._LIST_RE.match(stripped):
                list_lines, i = self._consume_list_lines(lines, i)
                parts.append(self._render_list_block(list_lines))
                continue

            if self._TABLE_RE.match(stripped):
                table_lines, i = self._consume_table_lines(lines, i)
                parts.append(self._render_table_block(table_lines))
                continue

            paragraph_lines = []
            while i < len(lines) and not self._is_block_boundary(lines[i]):
                paragraph_lines.append(lines[i].strip())
                i += 1

            paragraph_text = " ".join(line for line in paragraph_lines if line)
            if paragraph_text:
                parts.append(f"<p>{self._convert_inline(paragraph_text)}</p>")

        return "\n".join(parts)

    def _is_block_boundary(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if stripped in {"----", "{noformat}", "{quote}"}:
            return True
        if self._CODE_OPEN_RE.match(stripped) or self._PANEL_OPEN_RE.match(stripped):
            return True
        if self._HEADING_RE.match(stripped) or self._LIST_RE.match(stripped):
            return True
        return bool(self._TABLE_RE.match(stripped))

    def _consume_until(self, lines: list[str], start: int, end_marker: str) -> tuple[str, int]:
        collected = []
        i = start
        while i < len(lines):
            if lines[i].strip() == end_marker:
                return "\n".join(collected), i + 1
            collected.append(lines[i])
            i += 1
        return "\n".join(collected), i

    def _consume_list_lines(self, lines: list[str], start: int) -> tuple[list[str], int]:
        collected = []
        i = start
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped or not self._LIST_RE.match(stripped):
                break
            collected.append(stripped)
            i += 1
        return collected, i

    def _consume_table_lines(self, lines: list[str], start: int) -> tuple[list[str], int]:
        collected = []
        i = start
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped or not self._TABLE_RE.match(stripped):
                break
            collected.append(stripped)
            i += 1
        return collected, i

    def _extract_code_language(self, metadata: str | None) -> str:
        if not metadata:
            return ""
        first_piece = metadata.split("|", maxsplit=1)[0].strip()
        if not first_piece or "=" in first_piece:
            return ""
        return first_piece

    def _render_code_block(self, code_text: str, language: str) -> str:
        escaped = html.escape(code_text)
        if language:
            safe_language = re.sub(r"[^a-zA-Z0-9_-]", "", language)
            if safe_language:
                return f'<pre><code class="language-{safe_language}">{escaped}</code></pre>'
        return f"<pre><code>{escaped}</code></pre>"

    def _render_panel(self, panel_params: str | None, panel_content_html: str) -> str:
        params = self._parse_panel_params(panel_params)

        panel_styles = []
        for key, css_property in self._PANEL_STYLE_MAP.items():
            value = params.get(key)
            if value:
                panel_styles.append(f"{css_property}:{html.escape(value, quote=True)}")

        panel_style_attr = f' style="{";".join(panel_styles)}"' if panel_styles else ""

        title = params.get("title", "").strip()
        title_bg = params.get("titleBGColor", "").strip()
        title_style_attr = ""
        if title_bg:
            title_style_attr = f' style="background-color:{html.escape(title_bg, quote=True)}"'

        parts = [f'<div class="panel"{panel_style_attr}>']
        if title:
            parts.append(
                f'<div class="panelHeader"{title_style_attr}>{self._convert_inline(title)}</div>'
            )
        parts.append(f'<div class="panelContent">{panel_content_html}</div>')
        parts.append("</div>")
        return "".join(parts)

    def _parse_panel_params(self, panel_params: str | None) -> dict[str, str]:
        if not panel_params:
            return {}
        params = {}
        for piece in panel_params.split("|"):
            if "=" not in piece:
                continue
            key, value = piece.split("=", maxsplit=1)
            params[key.strip()] = value.strip()
        return params

    def _render_list_block(self, list_lines: list[str]) -> str:
        roots = []
        stack = []

        for line in list_lines:
            match = self._LIST_RE.match(line)
            if not match:
                continue

            markers, text = match.groups()
            desired_types = ["ul" if marker == "*" else "ol" for marker in markers]

            common_depth = 0
            while (
                common_depth < len(stack)
                and common_depth < len(desired_types)
                and stack[common_depth]["type"] == desired_types[common_depth]
            ):
                common_depth += 1

            stack = stack[:common_depth]

            for depth in range(common_depth, len(desired_types)):
                list_node = {"type": desired_types[depth], "items": []}
                if depth == 0:
                    roots.append(list_node)
                else:
                    parent_items = stack[depth - 1]["items"]
                    if not parent_items:
                        parent_items.append({"text": "", "children": []})
                    parent_items[-1]["children"].append(list_node)
                stack.append(list_node)

            stack[-1]["items"].append({"text": text.strip(), "children": []})

        return "".join(self._render_list_node(node) for node in roots)

    def _render_list_node(self, node: dict) -> str:
        tag = node["type"]
        parts = [f"<{tag}>"]
        for item in node["items"]:
            parts.append("<li>")
            parts.append(self._convert_inline(item["text"]))
            for child_list in item["children"]:
                parts.append(self._render_list_node(child_list))
            parts.append("</li>")
        parts.append(f"</{tag}>")
        return "".join(parts)

    def _render_table_block(self, table_lines: list[str]) -> str:
        rows = []
        for line in table_lines:
            if line.startswith("||") and line.endswith("||"):
                content = line[2:-2]
                cells = [cell.strip() for cell in content.split("||")]
                rows.append(("th", cells))
                continue

            if line.startswith("|") and line.endswith("|"):
                content = line[1:-1]
                cells = [cell.strip() for cell in content.split("|")]
                rows.append(("td", cells))

        if not rows:
            return ""

        parts = ["<table>"]
        for cell_tag, cells in rows:
            parts.append("<tr>")
            for cell in cells:
                parts.append(f"<{cell_tag}>{self._convert_inline(cell)}</{cell_tag}>")
            parts.append("</tr>")
        parts.append("</table>")
        return "".join(parts)

    def _convert_inline(self, text: str) -> str:  # noqa: C901
        placeholders = []

        def protect(value: str) -> str:
            placeholders.append(value)
            return f"\x00{len(placeholders) - 1}\x00"

        def image_repl(match: re.Match) -> str:
            src = html.escape(match.group("src").strip(), quote=True)
            attrs = [f'src="{src}"']

            props = (match.group("props") or "").strip()
            if props:
                for prop_piece in props.split(","):
                    if "=" not in prop_piece:
                        continue
                    key, value = prop_piece.split("=", maxsplit=1)
                    key = key.strip().lower()
                    value = html.escape(value.strip(), quote=True)
                    if key in {"width", "height", "alt"}:
                        attrs.append(f'{key}="{value}"')

            return protect(f"<img {' '.join(attrs)} />")

        def link_with_text_repl(match: re.Match) -> str:
            label = self._convert_inline(match.group("label").strip())
            href = html.escape(match.group("href").strip(), quote=True)
            return protect(f'<a href="{href}">{label}</a>')

        def link_simple_repl(match: re.Match) -> str:
            href = html.escape(match.group("href").strip(), quote=True)
            return protect(f'<a href="{href}">{href}</a>')

        protected = self._IMAGE_RE.sub(image_repl, text)
        protected = self._LINK_WITH_TEXT_RE.sub(link_with_text_repl, protected)
        protected = self._LINK_SIMPLE_RE.sub(link_simple_repl, protected)

        converted = html.escape(protected)

        def color_repl(match: re.Match) -> str:
            color = self._sanitize_color(match.group(1))
            body = match.group(2)
            if not color:
                return body
            return f'<span style="color:{color};">{body}</span>'

        converted = self._COLOR_RE.sub(color_repl, converted)

        for _ in range(8):
            changed = False
            for pattern, html_tag in self._INLINE_FORMAT_PATTERNS:
                next_value = pattern.sub(
                    lambda m, tag=html_tag: f"<{tag}>{m.group(1)}</{tag}>", converted
                )
                if next_value != converted:
                    converted = next_value
                    changed = True
            if not changed:
                break

        converted = converted.replace("\\\\", "<br />")
        converted = self._emoticon_re.sub(self._emoticon_replacement, converted)

        for idx, replacement in enumerate(placeholders):
            converted = converted.replace(f"\x00{idx}\x00", replacement)

        return converted

    def _sanitize_color(self, color: str) -> str:
        candidate = color.strip()
        if re.fullmatch(r"#[0-9a-fA-F]{3,8}", candidate):
            return candidate
        if re.fullmatch(r"[a-zA-Z]+", candidate):
            return candidate.lower()
        return ""

    def _emoticon_replacement(self, match: re.Match) -> str:
        token = match.group(0)
        css_class = self._EMOTICON_CLASS_MAP[token]
        return f'<span class="jira-emoticon jira-{css_class}">{html.escape(token)}</span>'


def convert_jira_to_html(jira_text: str) -> str:
    return _JiraMarkupToHtmlConverter().convert(jira_text)
