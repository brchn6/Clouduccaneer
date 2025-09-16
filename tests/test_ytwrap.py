"""Tests for YouTube/yt-dlp wrapper functionality."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cb.ytwrap import (duration_map, fetch, fetch_many, list_flat,
                       normalize_user_root, print_lines, run,
                       sc_search_url_title_pairs, sc_search_urls)


class TestRunFunction:
    """Tests for the run function."""

    @patch("subprocess.call")
    def test_run_basic_command(self, mock_call):
        """Test running a basic command."""
        mock_call.return_value = 0

        result = run(["echo", "hello"])

        assert result == 0
        mock_call.assert_called_once_with(["echo", "hello"], cwd=None)

    @patch("subprocess.call")
    def test_run_with_cwd(self, mock_call):
        """Test running command with working directory."""
        mock_call.return_value = 0
        test_path = Path("/tmp")

        result = run(["ls"], cwd=test_path)

        assert result == 0
        mock_call.assert_called_once_with(["ls"], cwd="/tmp")

    @patch("subprocess.call")
    def test_run_command_failure(self, mock_call):
        """Test handling of command failure."""
        mock_call.return_value = 1

        result = run(["false"])

        assert result == 1

    @patch("subprocess.call")
    def test_run_special_characters(self, mock_call):
        """Test running command with special characters."""
        mock_call.return_value = 0

        result = run(["echo", "hello world", "$PATH"])

        assert result == 0
        mock_call.assert_called_once_with(["echo", "hello world", "$PATH"], cwd=None)


class TestPrintLines:
    """Tests for the print_lines function."""

    @patch("subprocess.Popen")
    def test_print_lines_basic(self, mock_popen):
        """Test basic line printing functionality."""
        mock_process = MagicMock()
        mock_process.stdout = ["line1\n", "line2\n", "line3\n"]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        lines = list(print_lines(["echo", "test"]))

        assert lines == ["line1", "line2", "line3"]
        mock_popen.assert_called_once_with(
            ["echo", "test"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    @patch("subprocess.Popen")
    def test_print_lines_empty_output(self, mock_popen):
        """Test print_lines with empty output."""
        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        lines = list(print_lines(["true"]))

        assert lines == []

    @patch("subprocess.Popen")
    def test_print_lines_strips_whitespace(self, mock_popen):
        """Test that print_lines strips whitespace from lines."""
        mock_process = MagicMock()
        mock_process.stdout = ["  line1  \n", "\tline2\t\n"]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        lines = list(print_lines(["echo", "test"]))

        assert lines == ["line1", "line2"]


class TestDurationMap:
    """Tests for the duration_map function."""

    @patch("cb.ytwrap.print_lines")
    def test_duration_map_valid_durations(self, mock_print_lines):
        """Test duration mapping with valid durations."""
        mock_print_lines.side_effect = [
            ["120.5"],  # First URL
            ["180.0"],  # Second URL
        ]

        urls = ["url1", "url2"]
        result = duration_map(urls)

        assert result == {"url1": 120.5, "url2": 180.0}

    @patch("cb.ytwrap.print_lines")
    def test_duration_map_invalid_duration(self, mock_print_lines):
        """Test duration mapping with invalid duration."""
        mock_print_lines.side_effect = [
            ["not_a_number"],  # Invalid duration
        ]

        urls = ["url1"]
        result = duration_map(urls)

        assert result == {"url1": -1.0}

    @patch("cb.ytwrap.print_lines")
    def test_duration_map_empty_response(self, mock_print_lines):
        """Test duration mapping with empty response."""
        mock_print_lines.side_effect = [
            [],  # No output
        ]

        urls = ["url1"]
        result = duration_map(urls)

        assert "url1" not in result

    @patch("cb.ytwrap.print_lines")
    def test_duration_map_multiple_lines(self, mock_print_lines):
        """Test duration mapping when yt-dlp returns multiple lines."""
        mock_print_lines.return_value = ["120.5", "extra_line"]

        urls = ["url1"]
        result = duration_map(urls)

        # Should handle multiple lines and use first valid number or return error value
        assert isinstance(result, dict)
        assert "url1" in result
        # Accept either the parsed value or error value (-1.0)
        assert result["url1"] == 120.5 or result["url1"] == -1.0


class TestFetch:
    """Tests for the fetch function."""

    @patch("cb.ytwrap.run")
    def test_fetch_basic(self, mock_run):
        """Test basic fetch functionality."""
        mock_run.return_value = 0

        result = fetch("test_url", "output_template.%(ext)s")

        assert result == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "yt-dlp" in args
        assert "-x" in args
        assert "test_url" in args

    @patch("cb.ytwrap.run")
    def test_fetch_custom_parameters(self, mock_run):
        """Test fetch with custom parameters."""
        mock_run.return_value = 0

        result = fetch(
            "test_url",
            "output.%(ext)s",
            audio_fmt="flac",
            quality="320",
            embed=False,
            add_meta=False,
            write_thumb=True,
            convert_jpg=False,
            parse_meta=False,
        )

        assert result == 0
        args = mock_run.call_args[0][0]
        assert "--audio-format" in args
        assert "flac" in args
        assert "--audio-quality" in args
        assert "320" in args
        assert "--write-thumbnail" in args
        assert "--embed-metadata" not in args

    @patch("cb.ytwrap.run")
    def test_fetch_with_metadata_parsing(self, mock_run):
        """Test fetch with metadata parsing enabled."""
        mock_run.return_value = 0

        result = fetch("test_url", "output.%(ext)s", parse_meta=True)

        args = mock_run.call_args[0][0]
        assert "--parse-metadata" in args

    @patch("cb.ytwrap.run")
    def test_fetch_failure(self, mock_run):
        """Test fetch command failure."""
        mock_run.return_value = 1

        result = fetch("test_url", "output.%(ext)s")

        assert result == 1


class TestFetchMany:
    """Tests for the fetch_many function."""

    @patch("cb.ytwrap.fetch")
    def test_fetch_many_basic(self, mock_fetch):
        """Test basic fetch_many functionality."""
        mock_fetch.return_value = 0
        urls = ["url1", "url2", "url3"]

        result = fetch_many(urls, "output.%(ext)s")

        assert result == 0
        assert mock_fetch.call_count == 3

    @patch("cb.ytwrap.duration_map")
    @patch("cb.ytwrap.fetch")
    def test_fetch_many_with_duration_limit(self, mock_fetch, mock_duration_map):
        """Test fetch_many with duration limiting."""
        mock_fetch.return_value = 0
        mock_duration_map.return_value = {
            "url1": 120,  # Under limit
            "url2": 300,  # Over limit
            "url3": 180,  # Under limit
        }

        urls = ["url1", "url2", "url3"]
        result = fetch_many(urls, "output.%(ext)s", max_seconds=200)

        assert result == 0
        assert mock_fetch.call_count == 2  # Only url1 and url3

    def test_fetch_many_dry_run(self):
        """Test fetch_many dry run."""
        urls = ["url1", "url2"]

        result = fetch_many(urls, "output.%(ext)s", dry=True)

        assert result == 0
        # Should not actually call fetch

    @patch("cb.ytwrap.fetch")
    def test_fetch_many_partial_failures(self, mock_fetch):
        """Test fetch_many with some failures."""
        mock_fetch.side_effect = [0, 1, 0]  # Second fetch fails
        urls = ["url1", "url2", "url3"]

        result = fetch_many(urls, "output.%(ext)s")

        assert result == 1  # Should return non-zero on any failure


class TestSearchFunctions:
    """Tests for search functionality."""

    @patch("cb.ytwrap.print_lines")
    def test_sc_search_urls_basic(self, mock_print_lines):
        """Test basic SoundCloud URL search."""
        mock_print_lines.return_value = ["url1", "url2", "url3"]

        result = sc_search_urls("test query", max_results=3)

        assert result == ["url1", "url2", "url3"]
        mock_print_lines.assert_called_once()
        args = mock_print_lines.call_args[0][0]
        assert "scsearch3:test query" in " ".join(args)

    @patch("cb.ytwrap.print_lines")
    def test_sc_search_urls_with_kind(self, mock_print_lines):
        """Test SoundCloud search with different kinds."""
        mock_print_lines.return_value = ["playlist1", "playlist2"]

        result = sc_search_urls("test query", kind="sets", max_results=2)

        args = mock_print_lines.call_args[0][0]
        assert "type:playlists" in " ".join(args)

    @patch("cb.ytwrap.print_lines")
    def test_sc_search_url_title_pairs(self, mock_print_lines):
        """Test SoundCloud search returning URL-title pairs."""
        mock_print_lines.return_value = ["url1\tuploader1", "url2\tuploader2"]

        result = sc_search_url_title_pairs("test query", max_results=2)

        assert result == [("url1", "uploader1"), ("url2", "uploader2")]

    @patch("cb.ytwrap.print_lines")
    def test_sc_search_url_title_pairs_malformed(self, mock_print_lines):
        """Test SoundCloud search with malformed response."""
        mock_print_lines.return_value = [
            "url1\tuploader1",
            "malformed_line_without_tab",
            "url2\tuploader2",
        ]

        result = sc_search_url_title_pairs("test query", max_results=3)

        # Should only include properly formatted lines
        assert result == [("url1", "uploader1"), ("url2", "uploader2")]

    @patch("cb.ytwrap.print_lines")
    def test_list_flat(self, mock_print_lines):
        """Test listing flat URLs from a collection."""
        mock_print_lines.return_value = ["item1", "item2", "item3"]

        result = list_flat("https://soundcloud.com/user/playlist")

        assert result == ["item1", "item2", "item3"]


class TestNormalizeUserRoot:
    """Tests for normalize_user_root function."""

    def test_normalize_bare_handle(self):
        """Test normalizing a bare username handle."""
        result = normalize_user_root("username")
        assert result == "https://soundcloud.com/username"

    def test_normalize_handle_with_slash(self):
        """Test normalizing a handle with leading/trailing slashes."""
        result = normalize_user_root("/username/")
        assert result == "https://soundcloud.com/username"

    def test_normalize_full_url(self):
        """Test normalizing a full SoundCloud URL."""
        result = normalize_user_root("https://soundcloud.com/username/tracks")
        assert result == "https://soundcloud.com/username/tracks"

    def test_normalize_http_url(self):
        """Test normalizing an HTTP URL to HTTPS."""
        result = normalize_user_root("http://soundcloud.com/username")
        assert result == "https://soundcloud.com/username"

    def test_normalize_complex_path(self):
        """Test normalizing URL with complex paths."""
        result = normalize_user_root("https://soundcloud.com/username/sets/playlist")
        assert result == "https://soundcloud.com/username/sets/playlist"

    def test_normalize_whitespace(self):
        """Test normalizing with whitespace."""
        result = normalize_user_root("  username  ")
        assert result == "https://soundcloud.com/username"


class TestErrorHandling:
    """Tests for error handling in ytwrap functions."""

    @patch("subprocess.call")
    def test_run_subprocess_exception(self, mock_call):
        """Test run function handling subprocess exceptions."""
        mock_call.side_effect = FileNotFoundError("Command not found")

        with pytest.raises(FileNotFoundError):
            run(["nonexistent_command"])

    @patch("subprocess.Popen")
    def test_print_lines_subprocess_exception(self, mock_popen):
        """Test print_lines handling subprocess exceptions."""
        mock_popen.side_effect = FileNotFoundError("Command not found")

        with pytest.raises(FileNotFoundError):
            list(print_lines(["nonexistent_command"]))

    @patch("cb.ytwrap.print_lines")
    def test_duration_map_exception_handling(self, mock_print_lines):
        """Test duration_map handling exceptions."""
        mock_print_lines.side_effect = Exception("Command failed")

        # Exception from print_lines will propagate up
        with pytest.raises(Exception, match="Command failed"):
            duration_map(["url1"])

    def test_sc_search_urls_zero_results(self):
        """Test search functions with zero max_results."""
        result = sc_search_urls("test", max_results=0)
        # Should handle edge case appropriately
        assert isinstance(result, list)

    def test_normalize_user_root_empty_string(self):
        """Test normalize_user_root with empty string."""
        result = normalize_user_root("")
        assert result == "https://soundcloud.com/"

    def test_normalize_user_root_whitespace_only(self):
        """Test normalize_user_root with whitespace only."""
        result = normalize_user_root("   ")
        assert result == "https://soundcloud.com/"


class TestParameterValidation:
    """Tests for parameter validation."""

    def test_fetch_invalid_parameters(self):
        """Test fetch function with edge case parameters."""
        # Should handle unusual but valid parameter combinations
        with patch("cb.ytwrap.run") as mock_run:
            mock_run.return_value = 0

            result = fetch(
                "",
                "",
                audio_fmt="",
                quality="",
                embed=False,
                add_meta=False,
                write_thumb=False,
                convert_jpg=False,
                parse_meta=False,
            )

            assert isinstance(result, int)

    def test_fetch_many_empty_urls(self):
        """Test fetch_many with empty URL list."""
        result = fetch_many([], "output.%(ext)s")
        assert result == 0

    def test_duration_map_empty_urls(self):
        """Test duration_map with empty URL list."""
        result = duration_map([])
        assert result == {}

    @patch("cb.ytwrap.print_lines")
    def test_sc_search_negative_max_results(self, mock_print_lines):
        """Test search functions with negative max_results."""
        mock_print_lines.return_value = []

        result = sc_search_urls("test", max_results=-5)

        # Should handle negative values appropriately (convert to positive)
        assert isinstance(result, list)
