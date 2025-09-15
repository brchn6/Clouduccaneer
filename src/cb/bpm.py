"""BPM detection module for Clouduccaneer using librosa."""

from __future__ import annotations
import librosa
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import warnings


class BPMDetector:
    """High-quality BPM detection using librosa."""
    
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aiff', '.au'}
    
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
                    
        except Exception as e:
            # Return None on any error (file corruption, unsupported format, etc.)
            return None
    
    def _detect_bpm_basic(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Basic BPM detection using beat tracking."""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return float(tempo) if hasattr(tempo, '__len__') and len(tempo) > 0 else float(tempo)
        except:
            return None
    
    def _detect_bpm_advanced(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Advanced BPM detection using multiple methods and consensus."""
        tempos = []
        
        try:
            # Method 1: Standard beat tracking
            tempo1, _ = librosa.beat.beat_track(y=y, sr=sr)
            if tempo1 is not None:
                tempos.append(float(tempo1) if hasattr(tempo1, '__len__') else float(tempo1))
        except:
            pass
            
        try:
            # Method 2: Onset-based tempo estimation  
            onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
            tempo2 = librosa.feature.rhythm.tempo(onset_envelope=onset_envelope, sr=sr)[0]
            if tempo2 is not None:
                tempos.append(float(tempo2))
        except:
            pass
            
        try:
            # Method 3: Multi-tempo estimation (take the strongest)
            tempo_multi = librosa.feature.rhythm.tempo(y=y, sr=sr, max_tempo=200)
            if len(tempo_multi) > 0:
                tempos.append(float(tempo_multi[0]))
        except:
            pass
        
        if not tempos:
            return None
            
        # Use median for robustness
        return float(np.median(tempos))
    
    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for BPM detection."""
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def detect_bpm_batch(self, file_paths: List[Path], 
                         parallel: bool = False) -> Dict[Path, Optional[float]]:
        """Detect BPM for multiple files.
        
        Args:
            file_paths: List of audio file paths
            parallel: Use parallel processing (requires joblib)
            
        Returns:
            Dictionary mapping file paths to detected BPMs
        """
        if parallel:
            try:
                from joblib import Parallel, delayed
                results = Parallel(n_jobs=-1, verbose=1)(
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