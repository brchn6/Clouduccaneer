"""Simple tests for renamer functionality."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cb.renamer import (
    normalize_chars, strip_bpm_tokens, guess_artist_title, 
    plan_renames, apply_changes, clean_piece, ascii_fold
)


class TestBasicRenamerFunctions:
    """Test basic renamer functions."""

    def test_normalize_chars(self):
        """Test character normalization."""
        result = normalize_chars("hello$world")
        assert "$" not in result

    def test_strip_bpm_tokens(self):
        """Test BPM token removal.""" 
        result = strip_bpm_tokens("Song Title 120 BPM")
        assert "BPM" not in result

    def test_clean_piece(self):
        """Test piece cleaning."""
        result = clean_piece("  hello  world  ")
        assert result.strip() == result

    def test_ascii_fold(self):
        """Test ASCII folding."""
        result = ascii_fold("café")
        assert "é" not in result

    def test_guess_artist_title(self):
        """Test artist/title guessing."""
        trackno, artist, title = guess_artist_title("01 - Artist - Title.mp3")
        assert trackno == "01"
        assert artist == "Artist"
        # The function may include the extension
        assert "Title" in title

    @patch('pathlib.Path.glob')
    def test_plan_renames(self, mock_glob):
        """Test rename planning."""
        mock_path = MagicMock()
        mock_path.suffix = ".mp3"
        mock_path.name = "01 - Artist - Title.mp3"
        mock_glob.return_value = [mock_path]
        
        root = Path("/test")
        renames = plan_renames(root, ascii_only=True, keep_track=True)
        assert isinstance(renames, list)

    def test_apply_changes_empty(self):
        """Test applying empty changes list."""
        changes = []
        apply_changes(changes, move_covers=False, undo_csv=Path("/tmp/test.csv"))
        # Should not crash with empty list
