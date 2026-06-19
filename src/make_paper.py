#!/usr/bin/env python3
"""Convert paper.md to PDF using weasyprint."""
from weasyprint import HTML
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def md_to_html(md):
    lines = md.split("\n")
    html_parts = [
        "<html><head><meta charset='utf-8'><style>",
        "body { font-family: 'Times New Roman', Times, serif; max-width: 800px; margin: auto; padding: 40px 60px; font-size: 12pt; line-height: 1.5; color: #000; }",
        "h1 { font-size: 24pt; text-align: center; margin-top: 20px; }",
        "h2 { font-size: 18pt; margin-top: 24px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }",
        "h3 { font-size: 14pt; margin-top: 18px; }",
        "p { text-align: justify; margin: 6px 0; }",
        "pre { background: #f5f5f5; padding: 12px; font-size: 9pt; border: 1px solid #ddd; overflow-x: auto; white-space: pre-wrap; }",
        "code { font-size: 9pt; }",
        "table { border-collapse: collapse; width: 100%; margin: 12px 0; }",
        "td, th { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 10pt; }",
        "th { background: #f0f0f0; font-weight: bold; }",
        "hr { margin: 20px 0; }",
        "ul { margin: 6px 0; }",
        "li { margin: 2px 0; }",
        ".abstract { font-style: italic; text-align: justify; margin: 20px 40px; font-size: 11pt; }",
        "</style></head><body>",
    ]

    in_pre = False

    for raw_line in lines:
        stripped = raw_line

        # Handle code blocks
        if stripped.startswith("```"):
            if not in_pre:
                html_parts.append("<pre>")
                in_pre = True
            else:
                html_parts.append("</pre>")
                in_pre = False
            continue

        if in_pre:
            html_parts.append(
                stripped.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            continue

        # Skip table separators
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue

        # Headers
        if stripped.startswith("# ") and not stripped.startswith("## "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped == "---":
            html_parts.append("<hr>")
        elif stripped.startswith("- **") and "**: " in stripped:
            parts = stripped[4:].split("**: ", 1)
            html_parts.append(f"<p><strong>{parts[0]}</strong>: {parts[1]}</p>")
        elif stripped.startswith("| "):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            html_parts.append(
                "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
            )
        elif stripped.startswith("- "):
            html_parts.append(f"<li>{stripped[2:]}</li>")
        elif stripped.strip() == "":
            pass
        else:
            text = stripped
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
            text = re.sub(r"\[(\d+)\]", r"[\1]", text)
            if text.strip():
                html_parts.append(f"<p>{text}</p>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


if __name__ == "__main__":
    paper_dir = os.path.join(os.path.dirname(__file__), "..", "paper")
    md_path = os.path.join(paper_dir, "paper.md")
    pdf_path = os.path.join(paper_dir, "paper.pdf")

    md = open(md_path).read()
    html = md_to_html(md)
    HTML(string=html).write_pdf(pdf_path)
    print(f"PDF created: {pdf_path}")
