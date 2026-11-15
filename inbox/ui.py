"""Eval results page (Gradio, mounted at /ui): renders every eval/results/*.md report. The main UI is the board at /."""

import sqlite3

import gradio as gr

from inbox import config


def build_ui(conn: sqlite3.Connection) -> gr.Blocks:  # noqa: ARG001 (kept for the server's mount signature)
    def eval_md():
        files = sorted((config.ROOT / "eval" / "results").glob("*.md"))
        return "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in files) or "No eval results yet."

    with gr.Blocks(title="Voice Inbox · Eval results") as ui:
        gr.Markdown(f"# Eval results\n[← Back to the board](/) · LLM `{config.LLM_MODEL}` · ASR Parakeet TDT v3")
        ev = gr.Markdown(eval_md)
        gr.Button("Refresh").click(eval_md, None, ev)
    return ui
