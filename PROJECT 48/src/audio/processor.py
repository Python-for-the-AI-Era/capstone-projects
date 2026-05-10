"""
Audio processing module for voice-activated safety alert system.

This module handles real-time audio processing, MFCC feature extraction,
and audio streaming for keyword spotting.
"""

import torch
import torchaudio
import numpy as np
import librosa
import soundfile as sf
import logging
from typing import Optional, Tuple, List, Generator
from dataclasses import dataclass
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Configuration for audio processing."""
    sample_rate: int = 16000
    window_size: float = 0.5  # 500ms windows
    hop_size: float = 0.1   # 100ms hop
    n_mfcc: int = 13
    n_fft: int = 400
    hop_length: int = 160
    n_mels: int = 40
    f_min: float = 0.0
    f_max: float = 8000.0
    normalize: bool = True
    preemphasis: float = 0.97
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    
    @property
    def window_samples(self) -> int:
        """Number of samples in window."""
        return int(self.sample_rate * self.window_size)
    
    @property
    def hop_samples(self) -> int:
        """Number of samples in hop."""
        return int(self.sample_rate * self.hop_size)


class AudioProcessor:
    """Real-time audio processor for keyword spotting."""
    
    def __init__(self, config: AudioConfig):
        """
        Initialize audio processor.
        
        Args:
            config: Audio configuration
        """
        self.config = config
        self.device = torch.device(config.device)
        
        # Initialize MFCC transform
        self.mfcc_transform = torchaudio.transforms.MFCC(
            sample_rate=config.sample_rate,
            n_mfcc=config.n_mfcc,
            melkwargs={
                'n_fft': config.n_fft,
                'hop_length': config.hop_length,
                'n_mels': config.n_mels,
                'f_min': config.f_min,
                'f_max': config.f_max,
            }
        ).to(self.device)
        
        # Audio buffer for real-time processing
        self.audio_buffer = deque(maxlen=int(config.sample_rate * 2))  # 2 second buffer
        self.is_recording = False
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        
        # Statistics
        self.processed_frames = 0
        self.total_audio_time = 0.0
        
        logger.info(f"Audio processor initialized with config: {config}")
    
    def load_audio(self, file_path: str) -> Tuple[torch.Tensor, int]:
        """
        Load audio file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (audio_tensor, sample_rate)
        """
        try:
            waveform, sample_rate = torchaudio.load(file_path)
            
            # Convert to mono if needed
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Resample if needed
            if sample_rate != self.config.sample_rate:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, 
                    new_freq=self.config.sample_rate
                ).to(self.device)
                waveform = resampler(waveform.to(self.device))
                waveform = waveform.cpu()
            
            logger.info(f"Loaded audio: {file_path}, shape: {waveform.shape}")
            return waveform, self.config.sample_rate
            
        except Exception as e:
            logger.error(f"Error loading audio {file_path}: {e}")
            raise
    
    def extract_mfcc(self, waveform: torch.Tensor) -> torch.Tensor:
        """
        Extract MFCC features from audio waveform.
        
        Args:
            waveform: Audio waveform tensor
            
        Returns:
            MFCC features tensor
        """
        try:
            # Ensure waveform is on correct device
            waveform = waveform.to(self.device)
            
            # Apply preemphasis
            if self.config.preemphasis > 0:
                waveform = torch.cat([
                    waveform[:, :1], 
                    waveform[:, 1:] - self.config.preemphasis * waveform[:, :-1]
                ], dim=1)
            
            # Extract MFCC features
            mfcc = self.mfcc_transform(waveform)
            
            # Normalize if requested
            if self.config.normalize:
                mfcc = (mfcc - mfcc.mean(dim=2, keepdim=True)) / (mfcc.std(dim=2, keepdim=True) + 1e-8)
            
            # Transpose to (time, features) format
            mfcc = mfcc.transpose(1, 2)
            
            return mfcc
            
        except Exception as e:
            logger.error(f"Error extracting MFCC features: {e}")
            raise
    
    def create_windows(self, waveform: torch.Tensor) -> Generator[torch.Tensor, None, None]:
        """
        Create sliding windows from waveform.
        
        Args:
            waveform: Audio waveform tensor
            
        Yields:
            Audio window tensors
        """
        window_samples = self.config.window_samples
        hop_samples = self.config.hop_samples
        
        # Pad waveform if necessary
        if waveform.shape[1] < window_samples:
            padding = window_samples - waveform.shape[1]
            waveform = torch.nn.functional.pad(waveform, (0, padding))
        
        # Create windows
        for start in range(0, waveform.shape[1] - window_samples + 1, hop_samples):
            window = waveform[:, start:start + window_samples]
            yield window
    
    def process_audio_file(self, file_path: str) -> Tuple[torch.Tensor, List[int]]:
        """
        Process audio file and extract MFCC features.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (mfcc_features, window_timestamps)
        """
        try:
            # Load audio
            waveform, _ = self.load_audio(file_path)
            
            # Extract MFCC features for each window
            mfcc_features = []
            window_timestamps = []
            
            for i, window in enumerate(self.create_windows(waveform)):
                mfcc = self.extract_mfcc(window)
                mfcc_features.append(mfcc)
                
                # Calculate timestamp
                timestamp = i * self.config.hop_size
                window_timestamps.append(timestamp)
            
            # Stack features
            mfcc_features = torch.cat(mfcc_features, dim=0)
            
            logger.info(f"Processed audio file: {file_path}, features shape: {mfcc_features.shape}")
            return mfcc_features, window_timestamps
            
        except Exception as e:
            logger.error(f"Error processing audio file {file_path}: {e}")
            raise
    
    def process_real_time_audio(self, audio_chunk: np.ndarray) -> Optional[torch.Tensor]:
        """
        Process real-time audio chunk.
        
        Args:
            audio_chunk: Audio chunk as numpy array
            
        Returns:
            MFCC features tensor or None if insufficient data
        """
        try:
            # Convert to tensor
            if isinstance(audio_chunk, np.ndarray):
                waveform = torch.from_numpy(audio_chunk).float().unsqueeze(0)
            else:
                waveform = audio_chunk
            
            # Add to buffer
            self.audio_buffer.extend(waveform.squeeze().cpu().numpy())
            
            # Check if we have enough data for a window
            if len(self.audio_buffer) >= self.config.window_samples:
                # Extract window
                window_data = np.array(list(self.audio_buffer)[-self.config.window_samples:])
                window_tensor = torch.from_numpy(window_data).float().unsqueeze(0)
                
                # Extract MFCC features
                mfcc = self.extract_mfcc(window_tensor)
                
                # Update statistics
                self.processed_frames += 1
                self.total_audio_time += self.config.window_size
                
                return mfcc
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing real-time audio: {e}")
            return None
    
    def start_recording(self, duration: Optional[float] = None) -> None:
        """
        Start audio recording.
        
        Args:
            duration: Recording duration in seconds (None for continuous)
        """
        if self.is_recording:
            logger.warning("Recording already in progress")
            return
        
        self.is_recording = True
        self.recording_thread = threading.Thread(
            target=self._record_audio, 
            args=(duration,)
        )
        self.recording_thread.start()
        
        logger.info(f"Started audio recording{' for ' + str(duration) + 's' if duration else ''}")
    
    def stop_recording(self) -> None:
        """Stop audio recording."""
        if not self.is_recording:
            logger.warning("No recording in progress")
            return
        
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)
        
        logger.info("Stopped audio recording")
    
    def _record_audio(self, duration: Optional[float] = None) -> None:
        """
        Record audio from microphone.
        
        Args:
            duration: Recording duration in seconds
        """
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            
            # Configure stream
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=int(self.config.sample_rate * self.config.hop_size)
            )
            
            stream.start_stream()
            
            frames = []
            start_time = asyncio.get_event_loop().time()
            
            while self.is_recording:
                # Check duration limit
                if duration and (asyncio.get_event_loop().time() - start_time) >= duration:
                    break
                
                # Read audio chunk
                data = stream.read(int(self.config.sample_rate * self.config.hop_size))
                frames.append(data)
                
                # Process chunk
                audio_chunk = np.frombuffer(data, dtype=np.float32)
                mfcc = self.process_real_time_audio(audio_chunk)
                
                if mfcc is not None:
                    self.audio_queue.put(mfcc)
            
            # Stop and cleanup
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            self.is_recording = False
    
    def get_real_time_features(self) -> Generator[torch.Tensor, None, None]:
        """
        Get real-time MFCC features.
        
        Yields:
            MFCC features tensors
        """
        while self.is_recording:
            try:
                # Get features from queue with timeout
                mfcc = self.audio_queue.get(timeout=0.1)
                yield mfcc
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error getting real-time features: {e}")
                break
    
    def save_audio(self, waveform: torch.Tensor, file_path: str) -> None:
        """
        Save audio waveform to file.
        
        Args:
            waveform: Audio waveform tensor
            file_path: Output file path
        """
        try:
            # Ensure waveform is on CPU
            waveform = waveform.cpu()
            
            # Normalize to [-1, 1] range
            if torch.max(torch.abs(waveform)) > 1.0:
                waveform = waveform / torch.max(torch.abs(waveform))
            
            # Save using soundfile
            sf.write(file_path, waveform.squeeze().numpy(), self.config.sample_rate)
            
            logger.info(f"Saved audio to: {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving audio to {file_path}: {e}")
            raise
    
    def get_statistics(self) -> dict:
        """
        Get processing statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'processed_frames': self.processed_frames,
            'total_audio_time': self.total_audio_time,
            'is_recording': self.is_recording,
            'buffer_size': len(self.audio_buffer),
            'config': {
                'sample_rate': self.config.sample_rate,
                'window_size': self.config.window_size,
                'hop_size': self.config.hop_size,
                'n_mfcc': self.config.n_mfcc,
            }
        }
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processed_frames = 0
        self.total_audio_time = 0.0
        self.audio_buffer.clear()
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("Reset audio processor statistics")
    
    def __del__(self):
        """Cleanup when processor is destroyed."""
        if self.is_recording:
            self.stop_recording()


class AudioAugmentation:
    """Audio augmentation for training data generation."""
    
    def __init__(self, sample_rate: int = 16000):
        """
        Initialize audio augmentation.
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
    
    def add_noise(self, waveform: torch.Tensor, noise_factor: float = 0.005) -> torch.Tensor:
        """
        Add random noise to waveform.
        
        Args:
            waveform: Input waveform
            noise_factor: Noise intensity factor
            
        Returns:
            Waveform with added noise
        """
        noise = torch.randn_like(waveform) * noise_factor
        return waveform + noise
    
    def time_shift(self, waveform: torch.Tensor, shift_max: float = 0.2) -> torch.Tensor:
        """
        Apply random time shift to waveform.
        
        Args:
            waveform: Input waveform
            shift_max: Maximum shift as fraction of waveform length
            
        Returns:
            Time-shifted waveform
        """
        shift_samples = int(torch.randint(-shift_max * len(waveform), 
                                        shift_max * len(waveform), (1,)).item())
        
        if shift_samples > 0:
            # Pad at beginning
            waveform = torch.nn.functional.pad(waveform, (shift_samples, 0))
            waveform = waveform[:, :len(waveform) - shift_samples]
        elif shift_samples < 0:
            # Pad at end
            waveform = torch.nn.functional.pad(waveform, (0, -shift_samples))
            waveform = waveform[:, -shift_samples:]
        
        return waveform
    
    def pitch_shift(self, waveform: torch.Tensor, n_steps: int = 0) -> torch.Tensor:
        """
        Apply pitch shift to waveform.
        
        Args:
            waveform: Input waveform
            n_steps: Number of pitch steps
            
        Returns:
            Pitch-shifted waveform
        """
        try:
            # Convert to numpy for librosa processing
            audio = waveform.squeeze().numpy()
            
            # Apply pitch shift
            shifted_audio = librosa.effects.pitch_shift(
                y=audio, 
                sr=self.sample_rate, 
                n_steps=n_steps
            )
            
            # Convert back to tensor
            return torch.from_numpy(shifted_audio).float().unsqueeze(0)
            
        except Exception as e:
            logger.warning(f"Pitch shift failed: {e}")
            return waveform
    
    def volume_scale(self, waveform: torch.Tensor, scale_factor: float = 0.8) -> torch.Tensor:
        """
        Apply volume scaling to waveform.
        
        Args:
            waveform: Input waveform
            scale_factor: Volume scale factor
            
        Returns:
            Volume-scaled waveform
        """
        return waveform * scale_factor
    
    def augment(self, waveform: torch.Tensor, apply_prob: float = 0.5) -> torch.Tensor:
        """
        Apply random augmentations to waveform.
        
        Args:
            waveform: Input waveform
            apply_prob: Probability of applying each augmentation
            
        Returns:
            Augmented waveform
        """
        if torch.rand(1).item() < apply_prob:
            waveform = self.add_noise(waveform)
        
        if torch.rand(1).item() < apply_prob:
            waveform = self.time_shift(waveform)
        
        if torch.rand(1).item() < apply_prob:
            waveform = self.volume_scale(waveform)
        
        return waveform


def create_spectrogram(waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
    """
    Create spectrogram from waveform.
    
    Args:
        waveform: Input waveform
        sample_rate: Sample rate
        
    Returns:
        Spectrogram tensor
    """
    try:
        spectrogram_transform = torchaudio.transforms.Spectrogram(
            n_fft=400,
            hop_length=160,
            power=2.0
        )
        
        spectrogram = spectrogram_transform(waveform)
        
        # Convert to log scale
        spectrogram = torch.log(spectrogram + 1e-8)
        
        return spectrogram
        
    except Exception as e:
        logger.error(f"Error creating spectrogram: {e}")
        raise


def visualize_mfcc(mfcc_features: torch.Tensor, save_path: Optional[str] = None) -> None:
    """
    Visualize MFCC features.
    
    Args:
        mfcc_features: MFCC features tensor
        save_path: Path to save visualization
    """
    try:
        import matplotlib.pyplot as plt
        
        # Convert to numpy
        mfcc_np = mfcc_features.cpu().numpy()
        
        # Create plot
        plt.figure(figsize=(12, 8))
        plt.imshow(mfcc_np.T, origin='lower', aspect='auto', cmap='viridis')
        plt.colorbar(label='MFCC Coefficient')
        plt.xlabel('Time Frame')
        plt.ylabel('MFCC Coefficient')
        plt.title('MFCC Features')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved MFCC visualization to: {save_path}")
        else:
            plt.show()
        
        plt.close()
        
    except Exception as e:
        logger.error(f"Error visualizing MFCC: {e}")
        raise
