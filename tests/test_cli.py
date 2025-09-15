"""Comprehensive tests for CLI functionality."""

import json
import tempfile
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open
from cb.cli import app


@pytest.fixture
def runner():
    """Test runner fixture."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Temporary directory fixture."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_config():
    """Mock configuration fixture."""
    return {
        "download_dir": "/tmp/downloads",
        "out_template": "%(title)s - %(artist|uploader)s.%(ext)s",
        "rename": {"ascii": True, "keep_track": True, "move_covers": False}
    }


class TestFetchCommand:
    """Tests for the fetch command."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.fetch')
    def test_fetch_basic_url(self, mock_fetch, mock_load_config, runner, mock_config):
        """Test basic URL fetching."""
        mock_load_config.return_value = mock_config
        
        result = runner.invoke(app, ["fetch", "https://soundcloud.com/test/track"])
        
        assert result.exit_code == 0
        mock_fetch.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.fetch')
    def test_fetch_dry_run(self, mock_fetch, mock_load_config, runner, mock_config):
        """Test fetch command with dry run."""
        mock_load_config.return_value = mock_config
        
        result = runner.invoke(app, ["fetch", "https://soundcloud.com/test/track", "--dry"])
        
        assert result.exit_code == 0
        assert "[DRY] would fetch:" in result.stdout
        mock_fetch.assert_not_called()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.print_lines')
    @patch('cb.cli.ytwrap.duration_map')
    @patch('cb.cli.ytwrap.fetch')
    def test_fetch_with_duration_limit(self, mock_fetch, mock_duration_map, 
                                     mock_print_lines, mock_load_config, runner, mock_config):
        """Test fetch command with duration limiting."""
        mock_load_config.return_value = mock_config
        mock_print_lines.return_value = ["url1", "url2", "url3"]
        mock_duration_map.return_value = {"url1": 120, "url2": 300, "url3": 180}
        
        result = runner.invoke(app, ["fetch", "https://soundcloud.com/test/playlist", "--max-seconds", "200"])
        
        assert result.exit_code == 0
        # Should only fetch url1 and url3 (duration < 200)
        assert mock_fetch.call_count == 2

    @patch('cb.cli.load_config')
    def test_fetch_with_custom_dest(self, mock_load_config, runner, mock_config, temp_dir):
        """Test fetch command with custom destination."""
        mock_load_config.return_value = mock_config
        
        with patch('cb.cli.ytwrap.fetch') as mock_fetch:
            result = runner.invoke(app, ["fetch", "https://soundcloud.com/test/track", 
                                       "--dest", str(temp_dir)])
            
            assert result.exit_code == 0
            mock_fetch.assert_called_once()


class TestRenameCommand:
    """Tests for the rename command."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    def test_rename_no_changes(self, mock_plan_renames, mock_load_config, 
                              runner, mock_config, temp_dir):
        """Test rename command when no changes are needed."""
        mock_load_config.return_value = mock_config
        mock_plan_renames.return_value = []
        
        result = runner.invoke(app, ["rename", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "Nothing to change." in result.stdout

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    @patch('cb.cli.apply_changes')
    def test_rename_with_changes_apply(self, mock_apply_changes, mock_plan_renames, 
                                     mock_load_config, runner, mock_config, temp_dir):
        """Test rename command with changes and apply flag."""
        mock_load_config.return_value = mock_config
        changes = [("old_file.mp3", "new_file.mp3")]
        mock_plan_renames.return_value = changes
        
        result = runner.invoke(app, ["rename", str(temp_dir), "--apply"])
        
        assert result.exit_code == 0
        assert "[APPLY]" in result.stdout
        mock_apply_changes.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    def test_rename_dry_run(self, mock_plan_renames, mock_load_config, 
                           runner, mock_config, temp_dir):
        """Test rename command dry run."""
        mock_load_config.return_value = mock_config
        changes = [("old_file.mp3", "new_file.mp3")]
        mock_plan_renames.return_value = changes
        
        result = runner.invoke(app, ["rename", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "[DRY]" in result.stdout

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    def test_rename_custom_options(self, mock_plan_renames, mock_load_config, 
                                 runner, mock_config, temp_dir):
        """Test rename command with custom options."""
        mock_load_config.return_value = mock_config
        mock_plan_renames.return_value = []
        
        result = runner.invoke(app, ["rename", str(temp_dir), 
                                   "--no-ascii", "--no-keep-track", "--move-covers"])
        
        assert result.exit_code == 0
        mock_plan_renames.assert_called_once_with(
            temp_dir, ascii_only=False, keep_track=False
        )


class TestDedupeCommand:
    """Tests for the dedupe command."""

    def test_dedupe_dry_run(self, runner, temp_dir):
        """Test dedupe command dry run."""
        # Create test files
        (temp_dir / "track.mp3").touch()
        (temp_dir / "track.1.mp3").touch()
        (temp_dir / "another.1.mp3").touch()
        
        result = runner.invoke(app, ["dedupe", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "[DRY]" in result.stdout
        assert "track.1.mp3" in result.stdout
        assert "another.1.mp3" in result.stdout
        # Files should still exist
        assert (temp_dir / "track.1.mp3").exists()

    def test_dedupe_apply(self, runner, temp_dir):
        """Test dedupe command with apply flag."""
        # Create test files
        (temp_dir / "track.mp3").touch()
        (temp_dir / "track.1.mp3").touch()
        
        result = runner.invoke(app, ["dedupe", str(temp_dir), "--apply"])
        
        assert result.exit_code == 0
        assert "[DELETE]" in result.stdout
        # Duplicate file should be removed
        assert not (temp_dir / "track.1.mp3").exists()
        # Original file should remain
        assert (temp_dir / "track.mp3").exists()


class TestSearchCommand:
    """Tests for the search command."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.sc_search_urls')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_search_basic(self, mock_fetch_many, mock_sc_search_urls, 
                         mock_load_config, runner, mock_config):
        """Test basic search functionality."""
        mock_load_config.return_value = mock_config
        mock_sc_search_urls.return_value = ["url1", "url2"]
        
        result = runner.invoke(app, ["search", "test query"])
        
        assert result.exit_code == 0
        assert "Found 2 result(s)" in result.stdout
        mock_fetch_many.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.sc_search_urls')
    def test_search_no_results(self, mock_sc_search_urls, mock_load_config, 
                              runner, mock_config):
        """Test search with no results."""
        mock_load_config.return_value = mock_config
        mock_sc_search_urls.return_value = []
        
        result = runner.invoke(app, ["search", "nonexistent"])
        
        assert result.exit_code == 1
        assert "No results." in result.stdout

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.sc_search_url_title_pairs')
    def test_search_with_clustering(self, mock_sc_search_url_title_pairs, 
                                   mock_load_config, runner, mock_config):
        """Test search with clustering by uploader."""
        mock_load_config.return_value = mock_config
        mock_sc_search_url_title_pairs.return_value = [
            ("url1", "uploader1"),
            ("url2", "uploader1"),
            ("url3", "uploader2")
        ]
        
        result = runner.invoke(app, ["search", "test query", "--cluster"])
        
        assert result.exit_code == 0
        assert "Found 3 result(s) in 2 bucket(s)" in result.stdout

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.sc_search_urls')
    def test_search_dry_run(self, mock_sc_search_urls, mock_load_config, 
                           runner, mock_config):
        """Test search dry run."""
        mock_load_config.return_value = mock_config
        mock_sc_search_urls.return_value = ["url1", "url2"]
        
        result = runner.invoke(app, ["search", "test query", "--dry"])
        
        assert result.exit_code == 0
        assert "Found 2 result(s)" in result.stdout


class TestClusterUserCommand:
    """Tests for the cluster-user command."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.list_flat')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_cluster_user_basic(self, mock_fetch_many, mock_list_flat, 
                               mock_load_config, runner, mock_config):
        """Test basic cluster-user functionality."""
        mock_load_config.return_value = mock_config
        mock_list_flat.return_value = ["url1", "url2"]
        
        result = runner.invoke(app, ["cluster-user", "https://soundcloud.com/testuser"])
        
        assert result.exit_code == 0
        assert "Total items across buckets:" in result.stdout
        # Should call fetch_many for each bucket (uploads, reposts, likes, sets)
        assert mock_fetch_many.call_count == 4

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.list_flat')
    def test_cluster_user_dry_run(self, mock_list_flat, mock_load_config, 
                                 runner, mock_config):
        """Test cluster-user dry run."""
        mock_load_config.return_value = mock_config
        mock_list_flat.return_value = ["url1", "url2"]
        
        result = runner.invoke(app, ["cluster-user", "https://soundcloud.com/testuser", "--dry"])
        
        assert result.exit_code == 0
        assert "[uploads] 2 item(s)" in result.stdout


class TestFetchUserCommand:
    """Tests for the fetch-user command."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.list_flat')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_fetch_user_basic(self, mock_fetch_many, mock_list_flat, 
                             mock_load_config, runner, mock_config):
        """Test basic fetch-user functionality."""
        mock_load_config.return_value = mock_config
        mock_list_flat.return_value = ["url1", "url2", "url3"]
        
        result = runner.invoke(app, ["fetch-user", "https://soundcloud.com/testuser"])
        
        assert result.exit_code == 0
        mock_fetch_many.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.list_flat')
    def test_fetch_user_with_limit(self, mock_list_flat, mock_load_config, 
                                  runner, mock_config):
        """Test fetch-user with limit."""
        mock_load_config.return_value = mock_config
        mock_list_flat.return_value = ["url1", "url2", "url3", "url4", "url5"]
        
        with patch('cb.cli.ytwrap.fetch_many') as mock_fetch_many:
            result = runner.invoke(app, ["fetch-user", "https://soundcloud.com/testuser", 
                                       "--limit", "3"])
            
            assert result.exit_code == 0
            # Should only fetch the first 3 URLs
            args, kwargs = mock_fetch_many.call_args
            assert len(args[0]) == 3  # First argument should be list of 3 URLs


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_command(self, runner):
        """Test behavior with invalid command."""
        result = runner.invoke(app, ["invalid-command"])
        
        assert result.exit_code != 0

    @patch('cb.cli.load_config')
    def test_config_loading_error(self, mock_load_config, runner):
        """Test behavior when config loading fails."""
        mock_load_config.side_effect = Exception("Config error")
        
        result = runner.invoke(app, ["fetch", "test-url"])
        
        assert result.exit_code != 0

    def test_missing_required_argument(self, runner):
        """Test behavior with missing required arguments."""
        result = runner.invoke(app, ["rename"])
        
        assert result.exit_code != 0
        assert "Missing argument" in result.stdout or "Error" in result.stdout
