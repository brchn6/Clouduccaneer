"""Integration tests for CloudBuccaneer application."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
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
def sample_config():
    """Sample configuration for testing."""
    return {
        "download_dir": "/tmp/test_downloads",
        "out_template": "%(title)s - %(artist|uploader)s.%(ext)s",
        "rename": {
            "ascii": True,
            "keep_track": True,
            "move_covers": False
        },
        "spotify": {
            "download_dir": "/tmp/test_spotify",
            "quality": "320k",
            "format": "mp3",
            "lyrics": True,
            "playlist_numbering": True
        }
    }


class TestEndToEndWorkflows:
    """Test complete workflows from start to finish."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.fetch')
    def test_fetch_and_rename_workflow(self, mock_fetch, mock_load_config, 
                                     runner, sample_config, temp_dir):
        """Test complete fetch and rename workflow."""
        mock_load_config.return_value = sample_config
        mock_fetch.return_value = 0
        
        # Create some test files that would result from fetch
        test_files = [
            "01 - ARTIST - TITLE [FREE DL].mp3",
            "Artist - Another Song (bootleg).mp3"
        ]
        
        for filename in test_files:
            (temp_dir / filename).touch()
        
        # Step 1: Fetch (mocked)
        fetch_result = runner.invoke(app, ["fetch", "https://soundcloud.com/test/track"])
        assert fetch_result.exit_code == 0
        
        # Step 2: Rename the downloaded files
        with patch('cb.cli.plan_renames') as mock_plan_renames, \
             patch('cb.cli.apply_changes') as mock_apply_changes:
            
            mock_plan_renames.return_value = [
                (temp_dir / test_files[0], temp_dir / "01 - artist - title.mp3"),
                (temp_dir / test_files[1], temp_dir / "artist - another song.mp3")
            ]
            
            rename_result = runner.invoke(app, ["rename", str(temp_dir), "--apply"])
            assert rename_result.exit_code == 0
            mock_apply_changes.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.sc_search_urls')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_search_and_download_workflow(self, mock_fetch_many, mock_search_urls, 
                                        mock_load_config, runner, sample_config):
        """Test search and download workflow."""
        mock_load_config.return_value = sample_config
        mock_search_urls.return_value = ["url1", "url2", "url3"]
        mock_fetch_many.return_value = 0
        
        # Search and download
        result = runner.invoke(app, ["search", "electronic music", "--max", "3"])
        
        assert result.exit_code == 0
        assert "Found 3 result(s)" in result.stdout
        mock_fetch_many.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.list_flat')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_user_clustering_workflow(self, mock_fetch_many, mock_list_flat, 
                                    mock_load_config, runner, sample_config):
        """Test user content clustering workflow."""
        mock_load_config.return_value = sample_config
        mock_list_flat.return_value = ["track1", "track2"]
        mock_fetch_many.return_value = 0
        
        result = runner.invoke(app, ["cluster-user", "https://soundcloud.com/testuser"])
        
        assert result.exit_code == 0
        assert "Total items across buckets:" in result.stdout
        # Should call fetch_many for each bucket type
        assert mock_fetch_many.call_count == 4

    def test_dedupe_workflow(self, runner, temp_dir):
        """Test file deduplication workflow."""
        # Create test files including duplicates
        files = [
            "track.mp3",
            "track.1.mp3",
            "another.mp3", 
            "another.1.mp3",
            "clean.mp3"
        ]
        
        for filename in files:
            (temp_dir / filename).touch()
        
        # First do a dry run
        dry_result = runner.invoke(app, ["dedupe", str(temp_dir)])
        assert dry_result.exit_code == 0
        assert "[DRY]" in dry_result.stdout
        assert "track.1.mp3" in dry_result.stdout
        assert "another.1.mp3" in dry_result.stdout
        
        # Verify files still exist
        assert (temp_dir / "track.1.mp3").exists()
        assert (temp_dir / "another.1.mp3").exists()
        
        # Now apply the changes
        apply_result = runner.invoke(app, ["dedupe", str(temp_dir), "--apply"])
        assert apply_result.exit_code == 0
        assert "[DELETE]" in apply_result.stdout
        
        # Verify duplicates are removed
        assert not (temp_dir / "track.1.mp3").exists()
        assert not (temp_dir / "another.1.mp3").exists()
        # Originals should remain
        assert (temp_dir / "track.mp3").exists()
        assert (temp_dir / "another.mp3").exists()
        assert (temp_dir / "clean.mp3").exists()


class TestConfigurationIntegration:
    """Test configuration loading and application."""

    @patch('cb.utils.Path.exists')
    @patch('builtins.open')
    def test_config_override_behavior(self, mock_open, mock_exists, runner):
        """Test that configuration overrides work correctly."""
        # Mock config file exists
        mock_exists.return_value = True
        
        # Mock config file content
        import yaml
        config_content = yaml.dump({
            "download_dir": "/custom/download/path",
            "rename": {"ascii": False}
        })
        mock_open.return_value.__enter__.return_value.read.return_value = config_content
        
        # Test that custom config is used
        with patch('cb.cli.ytwrap.fetch') as mock_fetch:
            mock_fetch.return_value = 0
            
            result = runner.invoke(app, ["fetch", "test_url"])
            
            # Should use custom download directory
            assert result.exit_code == 0

    def test_environment_variable_config(self, runner, temp_dir):
        """Test configuration via environment variables."""
        # Create a custom config file
        config_file = temp_dir / "custom_config.yaml"
        config_content = """
download_dir: /env/downloads
rename:
  ascii: false
  keep_track: false
"""
        config_file.write_text(config_content)
        
        # Set environment variable
        with patch.dict(os.environ, {"CB_CONFIG": str(config_file)}):
            with patch('cb.cli.ytwrap.fetch') as mock_fetch:
                mock_fetch.return_value = 0
                
                result = runner.invoke(app, ["fetch", "test_url"])
                
                assert result.exit_code == 0
                # Config should be loaded from custom path


class TestErrorRecovery:
    """Test error handling and recovery scenarios."""

    @patch('cb.cli.load_config')
    def test_config_loading_failure_recovery(self, mock_load_config, runner):
        """Test graceful handling of config loading failures."""
        mock_load_config.side_effect = Exception("Config file corrupted")
        
        result = runner.invoke(app, ["fetch", "test_url"])
        
        # Should handle config error gracefully
        assert result.exit_code != 0

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.fetch')
    def test_download_failure_handling(self, mock_fetch, mock_load_config, 
                                     runner, sample_config):
        """Test handling of download failures."""
        mock_load_config.return_value = sample_config
        mock_fetch.return_value = 1  # Simulate failure
        
        result = runner.invoke(app, ["fetch", "invalid_url"])
        
        # Should handle download failure
        assert result.exit_code == 1

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    def test_rename_permission_error_handling(self, mock_plan_renames, 
                                            mock_load_config, runner, 
                                            sample_config, temp_dir):
        """Test handling of file permission errors during rename."""
        mock_load_config.return_value = sample_config
        
        # Create a file
        test_file = temp_dir / "test.mp3"
        test_file.touch()
        
        # Mock a permission error during rename planning
        mock_plan_renames.side_effect = PermissionError("Permission denied")
        
        result = runner.invoke(app, ["rename", str(temp_dir)])
        
        # Should handle permission error gracefully
        assert result.exit_code != 0

    def test_invalid_directory_handling(self, runner):
        """Test handling of invalid directories."""
        result = runner.invoke(app, ["rename", "/nonexistent/directory"])
        
        # Should handle non-existent directory gracefully
        assert result.exit_code != 0


class TestConcurrencyAndResourceManagement:
    """Test resource management and concurrent operations."""

    @patch('cb.cli.load_config')
    @patch('cb.cli.ytwrap.fetch_many')
    def test_large_batch_download(self, mock_fetch_many, mock_load_config, 
                                runner, sample_config):
        """Test handling of large batch downloads."""
        mock_load_config.return_value = sample_config
        mock_fetch_many.return_value = 0
        
        # Simulate a large search result
        with patch('cb.cli.ytwrap.sc_search_urls') as mock_search:
            # Return many URLs
            mock_search.return_value = [f"url{i}" for i in range(100)]
            
            result = runner.invoke(app, ["search", "popular music", "--max", "100"])
            
            assert result.exit_code == 0
            mock_fetch_many.assert_called_once()

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    @patch('cb.cli.apply_changes')
    def test_large_directory_rename(self, mock_apply_changes, mock_plan_renames, 
                                  mock_load_config, runner, sample_config, temp_dir):
        """Test handling of large directory renames."""
        mock_load_config.return_value = sample_config
        
        # Create many test files
        for i in range(50):
            (temp_dir / f"track_{i:03d} - ARTIST - TITLE [FREE DL].mp3").touch()
        
        # Mock many rename operations
        changes = [
            (temp_dir / f"track_{i:03d} - ARTIST - TITLE [FREE DL].mp3",
             temp_dir / f"track_{i:03d} - artist - title.mp3")
            for i in range(50)
        ]
        mock_plan_renames.return_value = changes
        
        result = runner.invoke(app, ["rename", str(temp_dir), "--apply"])
        
        assert result.exit_code == 0
        mock_apply_changes.assert_called_once()


class TestDataIntegrityAndConsistency:
    """Test data integrity and consistency."""

    def test_undo_csv_creation_and_format(self, runner, temp_dir):
        """Test that undo CSV is created with correct format."""
        # Create test files
        source_file = temp_dir / "original.mp3"
        source_file.touch()
        
        with patch('cb.cli.load_config') as mock_load_config, \
             patch('cb.cli.plan_renames') as mock_plan_renames, \
             patch('cb.cli.apply_changes') as mock_apply_changes:
            
            mock_load_config.return_value = {
                "rename": {"ascii": True, "keep_track": True, "move_covers": False}
            }
            
            changes = [(source_file, temp_dir / "renamed.mp3")]
            mock_plan_renames.return_value = changes
            
            undo_file = temp_dir / "custom_undo.csv"
            result = runner.invoke(app, ["rename", str(temp_dir), 
                                       "--apply", "--undo", str(undo_file)])
            
            assert result.exit_code == 0
            mock_apply_changes.assert_called_once()
            
            # Check that undo file path was passed correctly
            call_args = mock_apply_changes.call_args
            assert call_args[1]['undo_csv'] == undo_file

    @patch('cb.cli.load_config')
    @patch('cb.cli.plan_renames')
    def test_rename_dry_run_no_side_effects(self, mock_plan_renames, 
                                          mock_load_config, runner, 
                                          sample_config, temp_dir):
        """Test that dry run doesn't modify any files."""
        mock_load_config.return_value = sample_config
        
        # Create test files
        original_files = []
        for i in range(5):
            filename = f"test_{i} - ARTIST [FREE DL].mp3"
            filepath = temp_dir / filename
            filepath.touch()
            original_files.append(filepath)
        
        # Get initial state
        initial_files = list(temp_dir.iterdir())
        
        mock_plan_renames.return_value = [
            (f, temp_dir / f"renamed_{i}.mp3") 
            for i, f in enumerate(original_files)
        ]
        
        # Run dry rename
        result = runner.invoke(app, ["rename", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "[DRY]" in result.stdout
        
        # Verify no files were actually changed
        final_files = list(temp_dir.iterdir())
        assert set(initial_files) == set(final_files)
        
        # All original files should still exist
        for original_file in original_files:
            assert original_file.exists()


class TestCrossModuleIntegration:
    """Test integration between different modules."""

    @patch('cb.cli.load_config')
    def test_utils_config_integration(self, mock_load_config, runner):
        """Test integration between utils and CLI modules."""
        test_config = {
            "download_dir": "/test/downloads",
            "out_template": "custom_template.%(ext)s",
            "rename": {"ascii": True, "keep_track": False}
        }
        mock_load_config.return_value = test_config
        
        # Test that config is properly used across modules
        with patch('cb.cli.ytwrap.fetch') as mock_fetch:
            mock_fetch.return_value = 0
            
            result = runner.invoke(app, ["fetch", "test_url"])
            
            assert result.exit_code == 0
            # Verify config was used
            mock_load_config.assert_called()

    def test_renamer_ytwrap_integration(self, runner, temp_dir):
        """Test integration between renamer and file operations."""
        # This would test that files downloaded by ytwrap
        # can be properly processed by renamer
        
        # Create files that simulate ytwrap output
        downloaded_files = [
            "Track Name - Artist Name.mp3",
            "01 - ANOTHER TRACK [FREE DL] - ARTIST.mp3",
            "messy_filename_123 (bootleg).mp3"
        ]
        
        for filename in downloaded_files:
            (temp_dir / filename).touch()
        
        with patch('cb.cli.load_config') as mock_load_config:
            mock_load_config.return_value = {
                "rename": {"ascii": True, "keep_track": True, "move_covers": False}
            }
            
            # Test that renamer can process these files
            result = runner.invoke(app, ["rename", str(temp_dir)])
            
            assert result.exit_code == 0


class TestVersionCompatibility:
    """Test compatibility and version handling."""

    def test_app_help_command(self, runner):
        """Test that help command works properly."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "CloudBuccaneer" in result.stdout

    def test_command_help_commands(self, runner):
        """Test that individual command help works."""
        commands = ["fetch", "rename", "dedupe", "search", "cluster-user", "fetch-user"]
        
        for command in commands:
            result = runner.invoke(app, [command, "--help"])
            assert result.exit_code == 0, f"Help for {command} failed"

    def test_invalid_command_handling(self, runner):
        """Test handling of invalid commands."""
        result = runner.invoke(app, ["nonexistent-command"])
        
        assert result.exit_code != 0
        # Should show available commands or error message
