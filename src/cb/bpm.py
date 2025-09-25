"""BPM detection module for Clouduccaneer using librosa."""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import librosa
import numpy as np


class BPMDetector:
    """High-quality BPM detection using librosa."""

    SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".au"}

    def __init__(self, use_advanced: bool = True):
        """Initialize BPM detector.

        Args:
            use_advanced: Use multiple detection methods for better accuracy
        """
        self.use_advanced = use_advanced

    def detect_bpm(self, audio_path: Path) -> Optional[float]:
        """Detect BPM of an audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Detected BPM as float, or None if detection failed
        """
        try:
            # Load audio file
            y, sr = librosa.load(str(audio_path), sr=None)

            if len(y) == 0:
                return None

            # Suppress deprecation warnings for cleaner output
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                warnings.simplefilter("ignore", FutureWarning)

                if self.use_advanced:
                    return self._detect_bpm_advanced(y, sr)
                else:
                    return self._detect_bpm_basic(y, sr)

        except Exception:
            # Return None on any error (file corruption, unsupported format, etc.)
            return None

    def _detect_bpm_basic(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Basic BPM detection using beat tracking."""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return (
                float(tempo)
                if hasattr(tempo, "__len__") and len(tempo) > 0
                else float(tempo)
            )
        except Exception:
            return None

    def _detect_bpm_advanced(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Advanced BPM detection using multiple methods and consensus."""
        tempos = []

        try:
            # Method 1: Standard beat tracking
            tempo1, _ = librosa.beat.beat_track(y=y, sr=sr)
            if tempo1 is not None:
                tempos.append(
                    float(tempo1) if hasattr(tempo1, "__len__") else float(tempo1)
                )
        except Exception:
            pass

        try:
            # Method 2: Onset-based tempo estimation
            onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
            tempo2 = librosa.feature.rhythm.tempo(onset_envelope=onset_envelope, sr=sr)[
                0
            ]
            if tempo2 is not None:
                tempos.append(float(tempo2))
        except Exception:
            pass

        try:
            # Method 3: Multi-tempo estimation (take the strongest)
            tempo_multi = librosa.feature.rhythm.tempo(y=y, sr=sr, max_tempo=200)
            if len(tempo_multi) > 0:
                tempos.append(float(tempo_multi[0]))
        except Exception:
            pass

        if not tempos:
            return None

        # Use median for robustness
        return float(np.median(tempos))

    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for BPM detection."""
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS

    def detect_bpm_batch(
        self, file_paths: List[Path], parallel: bool = False, n_jobs: int = -1
    ) -> Dict[Path, Optional[float]]:
        """Detect BPM for multiple files.

        Args:
            file_paths: List of audio file paths
            parallel: Use parallel processing (requires joblib)
            n_jobs: Number of parallel jobs (-1 = all cores)

        Returns:
            Dictionary mapping file paths to detected BPMs
        """
        if parallel:
            try:
                from joblib import Parallel, delayed

                results = Parallel(n_jobs=n_jobs, verbose=1)(
                    delayed(self._detect_single)(path) for path in file_paths
                )
                return dict(zip(file_paths, results))
            except ImportError:
                # Fall back to sequential processing if joblib not available
                pass

        # Sequential processing
        results = {}
        for path in file_paths:
            results[path] = self.detect_bpm(path)
        return results

    def _detect_single(self, path: Path) -> Optional[float]:
        """Helper for parallel processing."""
        return self.detect_bpm(path)


def find_audio_files(directory: Path, recursive: bool = True) -> List[Path]:
    """Find all supported audio files in a directory.

    Args:
        directory: Directory to search
        recursive: Search recursively in subdirectories

    Returns:
        List of audio file paths
    """
    detector = BPMDetector()
    audio_files = []

    if not directory.is_dir():
        return []

    pattern = "**/*" if recursive else "*"

    for file_path in directory.glob(pattern):
        if file_path.is_file() and detector.is_supported_format(file_path):
            audio_files.append(file_path)

    return sorted(audio_files)


def format_bpm_result(file_path: Path, bpm: Optional[float]) -> str:
    """Format BPM detection result for display.

    Args:
        file_path: Path to audio file
        bpm: Detected BPM or None

    Returns:
        Formatted string for display
    """
    if bpm is not None:
        return f"Track: {file_path.name} → BPM: {bpm:.1f}"
    else:
        return f"Track: {file_path.name} → BPM: Unable to detect"


def add_bpm_to_filename(
    file_path: Path, bpm: float, backup: bool = True
) -> Optional[Path]:
    """Add BPM to filename while preserving the original file.

    Args:
        file_path: Path to audio file
        bpm: Detected BPM
        backup: Create backup of original file

    Returns:
        Path to new file with BPM in name, or None if failed
    """
    try:
        # Create new filename with BPM
        stem = file_path.stem
        suffix = file_path.suffix

        # Remove existing BPM from filename if present
        import re

        stem = re.sub(r"\s*\[\d+(\.\d+)?\s*BPM\]", "", stem)

        new_name = f"{stem} [{bpm:.0f} BPM]{suffix}"
        new_path = file_path.parent / new_name

        # Avoid overwriting existing files
        counter = 1
        while new_path.exists() and new_path != file_path:
            new_name = f"{stem} [{bpm:.0f} BPM] ({counter}){suffix}"
            new_path = file_path.parent / new_name
            counter += 1

        if new_path == file_path:
            return file_path  # Already has correct BPM in filename

        # Copy file to new location
        shutil.copy2(file_path, new_path)

        # Remove original file if backup not requested
        if not backup:
            file_path.unlink()

        return new_path

    except Exception:
        return None


def add_bpm_to_tags(file_path: Path, bpm: float) -> bool:
    """Add BPM to audio file metadata tags.

    Args:
        file_path: Path to audio file
        bpm: Detected BPM

    Returns:
        True if successful, False otherwise
    """
    try:
        from mutagen import File
        from mutagen.id3 import ID3, TBPM

        # Round BPM to nearest integer for tags
        bpm_int = int(round(bpm))

        # Try to load the file and add BPM tag
        audio_file = File(str(file_path))

        if audio_file is None:
            return False

        # Handle different file formats
        if hasattr(audio_file, "tags") and audio_file.tags is not None:
            if file_path.suffix.lower() == ".mp3":
                # MP3 with ID3 tags
                if not isinstance(audio_file.tags, ID3):
                    audio_file.add_tags()
                audio_file.tags.add(TBPM(encoding=3, text=str(bpm_int)))

            elif file_path.suffix.lower() == ".m4a":
                # MP4/M4A files
                audio_file.tags["tmpo"] = [bpm_int]

            elif file_path.suffix.lower() == ".flac":
                # FLAC files
                audio_file.tags["BPM"] = str(bpm_int)

            elif file_path.suffix.lower() in [".ogg", ".oga"]:
                # Ogg Vorbis files
                audio_file.tags["BPM"] = str(bpm_int)

            else:
                # Generic approach for other formats
                if hasattr(audio_file.tags, "__setitem__"):
                    audio_file.tags["BPM"] = str(bpm_int)
                else:
                    return False

            audio_file.save()
            return True

        else:
            # No tags exist, try to add them
            if file_path.suffix.lower() == ".mp3":
                audio_file.add_tags()
                audio_file.tags.add(TBPM(encoding=3, text=str(bpm_int)))
                audio_file.save()
                return True

        return False

    except Exception:
        return False


def analyze_bpm_batch(
    targets: List[Path],
    parallel: bool = False,
    n_jobs: int = -1,
    advanced: bool = True,
    recursive: bool = True,
    add_to_filename: bool = False,
    add_to_tags: bool = False,
    backup: bool = True,
) -> Dict[Path, Optional[float]]:
    """Analyze BPM for multiple audio files or directories.

    Args:
        targets: List of file or directory paths
        parallel: Use parallel processing for multiple files
        n_jobs: Number of parallel jobs (-1 = all cores)
        advanced: Use advanced multi-method detection
        recursive: Search recursively in directories
        add_to_filename: Add BPM to filename
        add_to_tags: Add BPM to file metadata tags
        backup: Create backup when modifying files

    Returns:
        Dictionary mapping file paths to detected BPMs
    """
    detector = BPMDetector(use_advanced=advanced)

    # Collect all audio files from targets
    all_files = []
    for target in targets:
        if target.is_file() and detector.is_supported_format(target):
            all_files.append(target)
        elif target.is_dir():
            all_files.extend(find_audio_files(target, recursive=recursive))

    if not all_files:
        return {}

    # Detect BPM for all files
    results = detector.detect_bpm_batch(all_files, parallel=parallel, n_jobs=n_jobs)

    # Apply filename/tag modifications if requested
    for file_path, bpm in results.items():
        if bpm is not None:
            if add_to_filename:
                add_bpm_to_filename(file_path, bpm, backup=backup)
            if add_to_tags:
                add_bpm_to_tags(file_path, bpm)

    return results
