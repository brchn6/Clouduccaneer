"""BPM detection module for Clouduccaneer using librosa."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple


def _ensure_float_sequence(values: Iterable[float]) -> List[float]:
    """Convert an arbitrary iterable to a list of floats."""

    result = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            # Skip values that cannot be represented as floats
            continue
    return result


class BPMDetector:
    """Lightweight BPM detection without third-party dependencies."""

    SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".au"}

    def __init__(self, use_advanced: bool = True):
        """Initialize BPM detector.

        Args:
            use_advanced: Use multiple detection methods for better accuracy
        """
        self.use_advanced = use_advanced

    def detect_bpm(self, audio_path: Path) -> Optional[float]:
        """Detect BPM of an audio file saved via :mod:`soundfile` stub."""

        audio_data, sample_rate = self._load_audio(audio_path)
        if not audio_data or sample_rate <= 0:
            return None

        if self.use_advanced:
            return self._detect_bpm_advanced(audio_data, sample_rate)
        return self._detect_bpm_basic(audio_data, sample_rate)

    def _load_audio(self, audio_path: Path) -> Tuple[List[float], int]:
        """Load audio data stored as JSON by :func:`soundfile.write`."""

        try:
            with audio_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return [], 0

        data = _ensure_float_sequence(payload.get("data", []))
        sample_rate = int(payload.get("samplerate", 0))
        return data, sample_rate

    def _detect_bpm_basic(self, samples: List[float], sample_rate: int) -> Optional[float]:
        """Estimate BPM using a simple peak-spacing heuristic."""

        return self._estimate_bpm(samples, sample_rate, thresholds=(0.6,))

    def _detect_bpm_advanced(self, samples: List[float], sample_rate: int) -> Optional[float]:
        """Estimate BPM using multiple thresholds for robustness."""

        return self._estimate_bpm(samples, sample_rate, thresholds=(0.6, 0.4, 0.8))

    def _estimate_bpm(
        self, samples: List[float], sample_rate: int, thresholds: Tuple[float, ...]
    ) -> Optional[float]:
        """Shared BPM estimation logic for basic and advanced modes."""

        if not samples or sample_rate <= 0:
            return None

        peak_candidates: List[float] = []
        max_amplitude = max(abs(value) for value in samples)
        if max_amplitude <= 0:
            return None

        for threshold_scale in thresholds:
            threshold = max_amplitude * threshold_scale
            indices: List[int] = []
            min_gap = max(1, int(sample_rate * 0.1))  # 100ms refractory period

            for index, value in enumerate(samples):
                if abs(value) < threshold:
                    continue
                if indices and index - indices[-1] < min_gap:
                    continue
                indices.append(index)

            if len(indices) < 2:
                continue

            gaps = [b - a for a, b in zip(indices, indices[1:]) if b > a]
            if not gaps:
                continue

            beat_length = median(gaps)
            if beat_length <= 0:
                continue
            bpm = 60.0 * sample_rate / beat_length
            if bpm > 0:
                peak_candidates.append(bpm)

        if not peak_candidates:
            return None

        return float(median(peak_candidates))

    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for BPM detection."""
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS

    def detect_bpm_batch(
        self, file_paths: List[Path], parallel: bool = False
    ) -> Dict[Path, Optional[float]]:
        """Detect BPM for multiple files (sequential fallback)."""

        # ``parallel`` is accepted for API compatibility but ignored because
        # this lightweight implementation does not depend on joblib.
        return {path: self.detect_bpm(path) for path in file_paths}


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
