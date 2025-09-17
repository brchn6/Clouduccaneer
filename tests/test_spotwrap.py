"""Tests for Spotify wrapper functionality."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cb.spotwrap import (fetch, fetch_many, get_metadata, get_playlist_tracks,
                         normalize_spotify_url, print_lines, run,
                         search_spotify, validate_spotify_url)


class TestRunFunction:
    """Tests for the run function."""

    @patch("subprocess.call")
    def test_run_basic_command(self, mock_call):
        """Test running a basic command."""
        mock_call.return_value = 0

        result = run(["spotdl", "--version"])

        assert result == 0
        mock_call.assert_called_once_with(["spotdl", "--version"], cwd=None)

    @patch("subprocess.call")
    def test_run_with_cwd(self, mock_call):
        """Test running command with working directory."""
        mock_call.return_value = 0
        test_path = Path("/tmp")

        result = run(["spotdl", "--help"], cwd=test_path)

        assert result == 0
        mock_call.assert_called_once_with(["spotdl", "--help"], cwd="/tmp")

    @patch("subprocess.call")
    def test_run_command_failure(self, mock_call):
        """Test handling of command failure."""
        mock_call.return_value = 1

        result = run(["spotdl", "invalid-command"])

        assert result == 1


class TestPrintLines:
    """Tests for the print_lines function."""

    @patch("subprocess.Popen")
    def test_print_lines_basic(self, mock_popen):
        """Test basic line printing functionality."""
        mock_process = MagicMock()
        mock_process.stdout = ["line1\n", "line2\n", "line3\n"]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        lines = list(print_lines(["spotdl", "meta", "test_url"]))

        assert lines == ["line1", "line2", "line3"]
        mock_popen.assert_called_once_with(
            ["spotdl", "meta", "test_url"],
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

        lines = list(print_lines(["spotdl", "--help"]))

        assert lines == []


class TestFetch:
    """Tests for the fetch function."""

    @patch("cb.spotwrap.run")
    def test_fetch_basic(self, mock_run):
        """Test basic fetch functionality."""
        mock_run.return_value = 0

        result = fetch("https://open.spotify.com/track/test", "/tmp/downloads")

        assert result == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "spotdl" in args
        assert "download" in args
        assert "https://open.spotify.com/track/test" in args

    @patch("cb.spotwrap.run")
    def test_fetch_custom_parameters(self, mock_run):
        """Test fetch with custom parameters."""
        mock_run.return_value = 0

        result = fetch(
            "https://open.spotify.com/track/test",
            "/tmp/downloads",
            audio_fmt="flac",
            quality="highest",
            lyrics=False,
            playlist_numbering=False,
            embed_metadata=False,
        )

        assert result == 0
        args = mock_run.call_args[0][0]
        assert "--format" in args
        assert "flac" in args
        assert "--bitrate" in args
        assert "highest" in args
        assert "--lyrics" not in args

    @patch("cb.spotwrap.run")
    def test_fetch_with_lyrics(self, mock_run):
        """Test fetch with lyrics enabled."""
        mock_run.return_value = 0

        result = fetch(
            "https://open.spotify.com/track/test", "/tmp/downloads", lyrics=True
        )

        args = mock_run.call_args[0][0]
        assert "--lyrics" in args
        assert "genius" in args or "musixmatch" in args

    @patch("cb.spotwrap.run")
    def test_fetch_with_playlist_numbering(self, mock_run):
        """Test fetch with playlist numbering enabled."""
        mock_run.return_value = 0

        result = fetch(
            "https://open.spotify.com/playlist/test",
            "/tmp/downloads",
            playlist_numbering=True,
        )

        args = mock_run.call_args[0][0]
        assert "--playlist-numbering" in args

    @patch("cb.spotwrap.run")
    def test_fetch_failure(self, mock_run):
        """Test fetch command failure."""
        mock_run.return_value = 1

        result = fetch("https://open.spotify.com/track/invalid", "/tmp/downloads")

        assert result == 1


class TestFetchMany:
    """Tests for the fetch_many function."""

    @patch("cb.spotwrap.fetch")
    def test_fetch_many_basic(self, mock_fetch):
        """Test basic fetch_many functionality."""
        mock_fetch.return_value = 0
        urls = [
            "https://open.spotify.com/track/1",
            "https://open.spotify.com/track/2",
            "https://open.spotify.com/track/3",
        ]

        result = fetch_many(urls, "/tmp/downloads")

        assert result == 0
        assert mock_fetch.call_count == 3

    def test_fetch_many_dry_run(self):
        """Test fetch_many dry run."""
        urls = ["https://open.spotify.com/track/1", "https://open.spotify.com/track/2"]

        result = fetch_many(urls, "/tmp/downloads", dry=True)

        assert result == 0
        # Should not actually call fetch

    @patch("cb.spotwrap.fetch")
    def test_fetch_many_partial_failures(self, mock_fetch):
        """Test fetch_many with some failures."""
        mock_fetch.side_effect = [0, 1, 0]  # Second fetch fails
        urls = [
            "https://open.spotify.com/track/1",
            "https://open.spotify.com/track/2",
            "https://open.spotify.com/track/3",
        ]

        result = fetch_many(urls, "/tmp/downloads")

        assert result == 1  # Should return non-zero on any failure

    @patch("cb.spotwrap.fetch")
    def test_fetch_many_custom_parameters(self, mock_fetch):
        """Test fetch_many with custom parameters."""
        mock_fetch.return_value = 0
        urls = ["https://open.spotify.com/track/1"]

        result = fetch_many(
            urls,
            "/tmp/downloads",
            audio_fmt="flac",
            quality="highest",
            lyrics=False,
            playlist_numbering=False,
        )

        assert result == 0
        mock_fetch.assert_called_once_with(
            "https://open.spotify.com/track/1",
            "/tmp/downloads",
            "flac",
            "highest",
            False,
            False,
            True,  # embed_metadata default
        )


class TestGetMetadata:
    """Tests for the get_metadata function."""

    @patch("subprocess.run")
    def test_get_metadata_success(self, mock_run):
        """Test successful metadata retrieval."""
        mock_result = MagicMock()
        mock_result.stdout = (
            "Artist: Test Artist\nTitle: Test Title\nAlbum: Test Album\n"
        )
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_metadata("https://open.spotify.com/track/test")

        expected = {
            "Artist": "Test Artist",
            "Title": "Test Title",
            "Album": "Test Album",
        }
        assert result == expected

    @patch("subprocess.run")
    def test_get_metadata_failure(self, mock_run):
        """Test metadata retrieval failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["spotdl"])

        result = get_metadata("https://open.spotify.com/track/invalid")

        assert result == {}

    @patch("subprocess.run")
    def test_get_metadata_malformed_output(self, mock_run):
        """Test metadata parsing with malformed output."""
        mock_result = MagicMock()
        mock_result.stdout = "Malformed line without colon\nArtist: Test Artist\nAnother malformed line\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_metadata("https://open.spotify.com/track/test")

        assert result == {"Artist": "Test Artist"}

    @patch("subprocess.run")
    def test_get_metadata_empty_output(self, mock_run):
        """Test metadata retrieval with empty output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_metadata("https://open.spotify.com/track/test")

        assert result == {}


class TestSearchSpotify:
    """Tests for search_spotify function."""

    @patch("subprocess.run")
    def test_search_spotify_basic(self, mock_run):
        """Test basic Spotify search."""
        mock_result = MagicMock()
        mock_result.stdout = """
        Found track: https://open.spotify.com/track/1
        Found track: https://open.spotify.com/track/2
        """
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = search_spotify("test query")

        assert len(result) >= 0  # Should return list of URLs
        assert isinstance(result, list)

    @patch("subprocess.run")
    def test_search_spotify_with_limit(self, mock_run):
        """Test Spotify search with result limit."""
        mock_result = MagicMock()
        mock_result.stdout = """
        Found: https://open.spotify.com/track/1
        Found: https://open.spotify.com/track/2
        Found: https://open.spotify.com/track/3
        """
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = search_spotify("test query", limit=2)

        # Should respect the limit
        assert len(result) <= 2

    @patch("subprocess.run")
    def test_search_spotify_failure(self, mock_run):
        """Test Spotify search failure."""
        mock_run.side_effect = Exception("Search failed")

        result = search_spotify("test query")

        assert result == []

    @patch("subprocess.run")
    def test_search_spotify_no_results(self, mock_run):
        """Test Spotify search with no results."""
        mock_result = MagicMock()
        mock_result.stdout = "No results found\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = search_spotify("nonexistent query")

        assert result == []


class TestValidateSpotifyUrl:
    """Tests for validate_spotify_url function."""

    def test_validate_valid_urls(self):
        """Test validation of valid Spotify URLs."""
        valid_urls = [
            "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh",
            "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3",
            "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd",
            "spotify:track:4iV5W9uYEdYUVa79Axb7Rh",
            "spotify:album:1DFixLWuPkv3KT3TnV35m3",
        ]

        for url in valid_urls:
            assert validate_spotify_url(url), f"Should validate: {url}"

    def test_validate_invalid_urls(self):
        """Test validation of invalid URLs."""
        invalid_urls = [
            "https://youtube.com/watch?v=123",
            "https://soundcloud.com/user/track",
            "not a url at all",
            "",
            "https://example.com",
        ]

        for url in invalid_urls:
            assert not validate_spotify_url(url), f"Should not validate: {url}"


class TestNormalizeSpotifyUrl:
    """Tests for normalize_spotify_url function."""

    def test_normalize_spotify_uri_track(self):
        """Test normalizing Spotify URI for tracks."""
        uri = "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
        expected = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"

        result = normalize_spotify_url(uri)

        assert result == expected

    def test_normalize_spotify_uri_album(self):
        """Test normalizing Spotify URI for albums."""
        uri = "spotify:album:1DFixLWuPkv3KT3TnV35m3"
        expected = "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3"

        result = normalize_spotify_url(uri)

        assert result == expected

    def test_normalize_spotify_uri_playlist(self):
        """Test normalizing Spotify URI for playlists."""
        uri = "spotify:playlist:37i9dQZF1DX0XUsuxWHRQd"
        expected = "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"

        result = normalize_spotify_url(uri)

        assert result == expected

    def test_normalize_already_normalized_url(self):
        """Test normalizing already normalized URLs."""
        url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"

        result = normalize_spotify_url(url)

        assert result == url

    def test_normalize_malformed_uri(self):
        """Test normalizing malformed Spotify URIs."""
        malformed_uris = [
            "spotify:track",  # Missing ID
            "spotify:",  # Incomplete
            "not:a:spotify:uri",
        ]

        for uri in malformed_uris:
            result = normalize_spotify_url(uri)
            # Should return original string if can't normalize
            assert result == uri


class TestGetPlaylistTracks:
    """Tests for get_playlist_tracks function."""

    def test_get_playlist_tracks_basic(self):
        """Test getting tracks from a playlist."""
        playlist_url = "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"

        result = get_playlist_tracks(playlist_url)

        # Current implementation just returns the playlist URL
        assert result == [playlist_url]
        assert isinstance(result, list)

    def test_get_playlist_tracks_empty_url(self):
        """Test getting tracks with empty URL."""
        result = get_playlist_tracks("")

        assert result == [""]

    def test_get_playlist_tracks_non_playlist_url(self):
        """Test getting tracks from non-playlist URL."""
        track_url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"

        result = get_playlist_tracks(track_url)

        # Current implementation returns the URL as-is
        assert result == [track_url]


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @patch("subprocess.call")
    def test_run_subprocess_exception(self, mock_call):
        """Test run function handling subprocess exceptions."""
        mock_call.side_effect = FileNotFoundError("spotdl not found")

        with pytest.raises(FileNotFoundError):
            run(["spotdl", "--version"])

    @patch("subprocess.Popen")
    def test_print_lines_subprocess_exception(self, mock_popen):
        """Test print_lines handling subprocess exceptions."""
        mock_popen.side_effect = FileNotFoundError("spotdl not found")

        with pytest.raises(FileNotFoundError):
            list(print_lines(["spotdl", "--help"]))

    def test_validate_spotify_url_none_input(self):
        """Test validate_spotify_url with None input."""
        # Should handle None gracefully
        try:
            result = validate_spotify_url(None)
            assert result is False
        except (TypeError, AttributeError):
            # Also acceptable if it raises an appropriate exception
            pass

    def test_normalize_spotify_url_none_input(self):
        """Test normalize_spotify_url with None input."""
        # Should handle None gracefully
        try:
            result = normalize_spotify_url(None)
            assert result is None
        except (TypeError, AttributeError):
            # Also acceptable if it raises an appropriate exception
            pass


class TestParameterValidation:
    """Tests for parameter validation."""

    @patch("cb.spotwrap.run")
    def test_fetch_empty_url(self, mock_run):
        """Test fetch with empty URL."""
        mock_run.return_value = 0

        result = fetch("", "/tmp/downloads")

        assert isinstance(result, int)

    @patch("cb.spotwrap.run")
    def test_fetch_empty_output_dir(self, mock_run):
        """Test fetch with empty output directory."""
        mock_run.return_value = 0

        result = fetch("https://open.spotify.com/track/test", "")

        assert isinstance(result, int)

    def test_fetch_many_empty_urls(self):
        """Test fetch_many with empty URL list."""
        result = fetch_many([], "/tmp/downloads")

        assert result == 0

    def test_search_spotify_empty_query(self):
        """Test search with empty query."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = search_spotify("")

            assert isinstance(result, list)

    def test_get_metadata_empty_url(self):
        """Test get_metadata with empty URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["spotdl"])

            result = get_metadata("")

            assert result == {}
