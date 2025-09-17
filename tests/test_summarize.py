"""Tests for conversation summarization functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cb.cli import app

runner = CliRunner()


def test_summarize_empty_conversation():
    """Test that empty conversation shows error message."""
    result = runner.invoke(app, ["summarize", "[]"])
    assert result.exit_code == 1
    assert (
        "It seems that the conversation you intended to provide is incomplete"
        in result.stdout
    )


def test_summarize_invalid_json():
    """Test that invalid JSON shows error message."""
    result = runner.invoke(app, ["summarize", "not valid json"])
    assert result.exit_code == 1
    assert "Error: Invalid JSON format or file not found" in result.stdout


def test_summarize_incomplete_conversation():
    """Test that conversation with only one message shows error."""
    conversation = '[{"role": "user", "content": "hello"}]'
    result = runner.invoke(app, ["summarize", conversation])
    assert result.exit_code == 1
    assert (
        "It seems that the conversation you intended to provide is incomplete"
        in result.stdout
    )


def test_summarize_empty_content():
    """Test that conversation with empty content shows error."""
    conversation = (
        '[{"role": "user", "content": ""}, {"role": "assistant", "content": ""}]'
    )
    result = runner.invoke(app, ["summarize", conversation])
    assert result.exit_code == 1
    assert (
        "It seems that the conversation you intended to provide is incomplete"
        in result.stdout
    )


def test_summarize_valid_conversation():
    """Test that valid conversation generates summary."""
    conversation = """[
        {"role": "user", "content": "Hello, can you help me download music?"},
        {"role": "assistant", "content": "Yes, I can help you with that. CloudBuccaneer is a tool for downloading SoundCloud tracks."}
    ]"""
    result = runner.invoke(app, ["summarize", conversation])
    assert result.exit_code == 0
    assert "# Conversation Summary" in result.stdout
    assert "**Total Messages:** 2" in result.stdout
    assert "**User Messages:** 1" in result.stdout
    assert "**Assistant Messages:** 1" in result.stdout


def test_summarize_file_input():
    """Test that file input works correctly."""
    conversation_data = [
        {
            "role": "user",
            "content": "I need help with downloading a SoundCloud playlist",
        },
        {"role": "assistant", "content": "I can help you with SoundCloud downloads."},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(conversation_data, f)
        temp_file = f.name

    try:
        result = runner.invoke(app, ["summarize", temp_file])
        assert result.exit_code == 0
        assert "# Conversation Summary" in result.stdout
        assert "**Total Messages:** 2" in result.stdout
    finally:
        Path(temp_file).unlink()


def test_summarize_with_output_file():
    """Test that output file option works."""
    conversation = """[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]"""

    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / "summary.md"
        result = runner.invoke(
            app, ["summarize", conversation, "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert f"Summary written to: {output_file}" in result.stdout
        assert output_file.exists()

        content = output_file.read_text()
        assert "# Conversation Summary" in content


def test_summarize_not_list():
    """Test that non-list JSON shows error."""
    conversation = '{"role": "user", "content": "hello"}'
    result = runner.invoke(app, ["summarize", conversation])
    assert result.exit_code == 1
    assert (
        "It seems that the conversation you intended to provide is incomplete"
        in result.stdout
    )


def test_summarize_missing_fields():
    """Test that messages without required fields are handled."""
    conversation = '[{"content": "hello"}, {"role": "assistant", "content": "hi"}]'
    result = runner.invoke(app, ["summarize", conversation])
    assert result.exit_code == 1
    assert (
        "It seems that the conversation you intended to provide is incomplete"
        in result.stdout
    )
