"""Tests for BPM detection functionality."""

import pytest
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from typer.testing import CliRunner
from cb.cli import app
from cb.bpm import BPMDetector, find_audio_files, format_bpm_result, add_bpm_to_filename, add_bpm_to_tags


runner = CliRunner()


def create_test_audio(bpm: int, duration: float = 5.0, sr: int = 22050) -> np.ndarray:
    """Create a test audio signal with a specific BPM."""
    samples = int(duration * sr)
    beat_interval = 60.0 / bpm
    audio = np.zeros(samples)
    
    # Simple click track
    for beat_time in np.arange(0, duration, beat_interval):
        beat_sample = int(beat_time * sr)
        if beat_sample < samples - 100:
            audio[beat_sample:beat_sample+100] = 0.5
    
    # Normalize
    return audio / np.max(np.abs(audio)) * 0.9 if np.max(np.abs(audio)) > 0 else audio


class TestBPMDetector:
    """Test the BPMDetector class."""
    
    def test_init(self):
        """Test BPMDetector initialization."""
        detector = BPMDetector()
        assert detector.use_advanced == True
        
        detector_basic = BPMDetector(use_advanced=False)
        assert detector_basic.use_advanced == False
    
    def test_supported_formats(self):
        """Test supported format checking."""
        detector = BPMDetector()
        
        # Supported formats
        assert detector.is_supported_format(Path("test.mp3"))
        assert detector.is_supported_format(Path("test.wav"))
        assert detector.is_supported_format(Path("test.flac"))
        assert detector.is_supported_format(Path("test.m4a"))
        assert detector.is_supported_format(Path("test.ogg"))
        
        # Unsupported formats
        assert not detector.is_supported_format(Path("test.txt"))
        assert not detector.is_supported_format(Path("test.jpg"))
        assert not detector.is_supported_format(Path("test.mp4"))
    
    def test_detect_bpm_with_test_audio(self):
        """Test BPM detection with generated test audio."""
        detector = BPMDetector()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_audio = create_test_audio(120)
            sf.write(f.name, test_audio, 22050)
            
            bpm = detector.detect_bpm(Path(f.name))
            
            # Should detect BPM within reasonable range
            assert bpm is not None
            assert 110 <= bpm <= 130  # Allow for some detection variance
            
            Path(f.name).unlink()
    
    def test_detect_bpm_nonexistent_file(self):
        """Test BPM detection on non-existent file."""
        detector = BPMDetector()
        bpm = detector.detect_bpm(Path("/nonexistent/file.wav"))
        assert bpm is None
    
    def test_detect_bpm_empty_file(self):
        """Test BPM detection on empty audio file."""
        detector = BPMDetector()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # Create empty audio
            sf.write(f.name, np.array([]), 22050)
            
            bpm = detector.detect_bpm(Path(f.name))
            assert bpm is None
            
            Path(f.name).unlink()
    
    def test_detect_bpm_batch(self):
        """Test batch BPM detection."""
        detector = BPMDetector()
        
        files = []
        bpms = [120, 140]
        
        try:
            for target_bpm in bpms:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    test_audio = create_test_audio(target_bpm)
                    sf.write(f.name, test_audio, 22050)
                    files.append(Path(f.name))
            
            results = detector.detect_bpm_batch(files)
            
            assert len(results) == len(files)
            for file_path, bpm in results.items():
                assert bpm is not None
                # Should be within reasonable range of targets
                assert 110 <= bpm <= 150
        
        finally:
            for file_path in files:
                if file_path.exists():
                    file_path.unlink()


class TestFindAudioFiles:
    """Test audio file discovery."""
    
    def test_find_audio_files_empty_dir(self):
        """Test finding audio files in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = find_audio_files(Path(temp_dir))
            assert files == []
    
    def test_find_audio_files_with_audio(self):
        """Test finding audio files in directory with audio files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            audio_files = ["test1.mp3", "test2.wav", "test3.flac"]
            other_files = ["readme.txt", "image.jpg"]
            
            for name in audio_files + other_files:
                (temp_path / name).touch()
            
            found_files = find_audio_files(temp_path)
            found_names = [f.name for f in found_files]
            
            # Should find only audio files
            assert len(found_files) == len(audio_files)
            for audio_file in audio_files:
                assert audio_file in found_names
            
            for other_file in other_files:
                assert other_file not in found_names
    
    def test_find_audio_files_recursive(self):
        """Test recursive audio file search."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            sub_dir = temp_path / "subdir"
            sub_dir.mkdir()
            
            # Create files in root and subdirectory
            (temp_path / "root.mp3").touch()
            (sub_dir / "sub.wav").touch()
            
            # Recursive search
            files = find_audio_files(temp_path, recursive=True)
            assert len(files) == 2
            
            # Non-recursive search
            files = find_audio_files(temp_path, recursive=False)
            assert len(files) == 1
            assert files[0].name == "root.mp3"
    
    def test_find_audio_files_nonexistent_dir(self):
        """Test finding audio files in non-existent directory."""
        files = find_audio_files(Path("/nonexistent/directory"))
        assert files == []


class TestFormatBPMResult:
    """Test BPM result formatting."""
    
    def test_format_bpm_result_success(self):
        """Test formatting successful BPM detection result."""
        result = format_bpm_result(Path("test.mp3"), 120.5)
        assert result == "Track: test.mp3 → BPM: 120.5"
    
    def test_format_bpm_result_failure(self):
        """Test formatting failed BPM detection result."""
        result = format_bpm_result(Path("test.mp3"), None)
        assert result == "Track: test.mp3 → BPM: Unable to detect"


class TestExportFunctions:
    """Test BPM export functionality."""
    
    def test_add_bpm_to_filename(self):
        """Test adding BPM to filename."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_audio = create_test_audio(120)
            sf.write(f.name, test_audio, 22050)
            original_path = Path(f.name)
        
        new_path = None
        new_path2 = None
        
        try:
            # Test adding BPM to filename
            new_path = add_bpm_to_filename(original_path, 120.5, backup=True)
            
            assert new_path is not None
            assert "[120 BPM]" in new_path.name  # Rounded to integer
            assert new_path.exists()
            assert original_path.exists()  # Original should still exist (backup=True)
            
            # Test without backup
            new_path2 = add_bpm_to_filename(original_path, 120.5, backup=False)
            assert new_path2 is not None
            assert not original_path.exists()  # Original should be removed (backup=False)
            
        finally:
            # Clean up
            for path in [original_path, new_path, new_path2]:
                if path and path.exists():
                    path.unlink()
    
    def test_add_bpm_to_filename_existing_bpm(self):
        """Test adding BPM to filename that already has BPM."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.close()
            original_path = Path(f.name)
            
            # Rename to have existing BPM
            bpm_path = original_path.parent / f"{original_path.stem} [120 BPM].wav"
            original_path.rename(bpm_path)
        
        try:
            # Test updating BPM in filename
            new_path = add_bpm_to_filename(bpm_path, 140.0, backup=True)
            
            assert new_path is not None
            assert "[140 BPM]" in new_path.name
            assert "[120 BPM]" not in new_path.name
            
        finally:
            # Clean up
            for path in [original_path, bpm_path, new_path]:
                if path and path.exists():
                    path.unlink()
    
    def test_add_bpm_to_tags_unsupported_file(self):
        """Test adding BPM to tags on unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)
        
        try:
            success = add_bpm_to_tags(temp_path, 120.0)
            assert success == False
        finally:
            temp_path.unlink()


class TestBPMCLI:
    """Test BPM CLI command."""
    
    def test_bpm_command_help(self):
        """Test BPM command help output."""
        result = runner.invoke(app, ["bpm", "--help"])
        assert result.exit_code == 0
        # Strip ANSI codes for testing
        clean_output = result.stdout.encode('ascii', 'ignore').decode('ascii')
        assert "Analyze audio files and detect their BPM" in clean_output
        assert "parallel" in clean_output
        assert "advanced" in clean_output
        assert "recursive" in clean_output
    
    def test_bpm_command_nonexistent_file(self):
        """Test BPM command with non-existent file."""
        result = runner.invoke(app, ["bpm", "/nonexistent/file.mp3"])
        assert result.exit_code == 1
        assert "Error: Path does not exist" in result.stdout
    
    def test_bpm_command_unsupported_format(self):
        """Test BPM command with unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)
        
        try:
            result = runner.invoke(app, ["bpm", str(temp_path)])
            assert result.exit_code == 1
            assert "Error: Unsupported file format" in result.stdout
            assert "Supported formats:" in result.stdout
        finally:
            temp_path.unlink()
    
    def test_bpm_command_single_file(self):
        """Test BPM command with single audio file."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_audio = create_test_audio(120)
            sf.write(f.name, test_audio, 22050)
            temp_path = Path(f.name)
        
        try:
            result = runner.invoke(app, ["bpm", str(temp_path)])
            assert result.exit_code == 0
            assert "Analyzing:" in result.stdout
            assert "Track:" in result.stdout
            assert "BPM:" in result.stdout
        finally:
            temp_path.unlink()
    
    def test_bpm_command_directory(self):
        """Test BPM command with directory containing audio files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test audio file
            audio_file = temp_path / "test.wav"
            test_audio = create_test_audio(120)
            sf.write(str(audio_file), test_audio, 22050)
            
            result = runner.invoke(app, ["bpm", str(temp_path)])
            assert result.exit_code == 0
            assert "Found 1 audio file(s)" in result.stdout
            assert "Track: test.wav" in result.stdout
            assert "Summary:" in result.stdout
    
    def test_bpm_command_empty_directory(self):
        """Test BPM command with directory containing no audio files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create non-audio file
            (temp_path / "readme.txt").touch()
            
            result = runner.invoke(app, ["bpm", str(temp_path)])
            assert result.exit_code == 0
            assert "No supported audio files found" in result.stdout
            assert "Supported formats:" in result.stdout
    
    def test_bpm_command_advanced_flag(self):
        """Test BPM command with advanced/basic flag."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_audio = create_test_audio(120)
            sf.write(f.name, test_audio, 22050)
            temp_path = Path(f.name)
        
        try:
            # Test with advanced mode (default)
            result = runner.invoke(app, ["bpm", str(temp_path), "--advanced"])
            assert result.exit_code == 0
            
            # Test with basic mode
            result = runner.invoke(app, ["bpm", str(temp_path), "--basic"])
            assert result.exit_code == 0
        finally:
            temp_path.unlink()
    
    def test_bpm_command_export_options(self):
        """Test BPM command with export options."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            test_audio = create_test_audio(120)
            sf.write(f.name, test_audio, 22050)
            temp_path = Path(f.name)
        
        try:
            # Test export to filename
            result = runner.invoke(app, ["bpm", str(temp_path), "--export-filename"])
            assert result.exit_code == 0
            assert "Exported to filename:" in result.stdout
            
            # Test export flags in help
            result = runner.invoke(app, ["bpm", "--help"])
            assert result.exit_code == 0
            # Remove ANSI codes more thoroughly for testing
            import re
            clean_output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout)
            assert "export-filename" in clean_output
            assert "export-tags" in clean_output
            assert "backup" in clean_output
            
        finally:
            # Clean up any exported files
            temp_dir = temp_path.parent
            for file in temp_dir.glob(f"{temp_path.stem}*BPM*"):
                file.unlink()
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])