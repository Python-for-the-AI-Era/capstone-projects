"""
Audio Processing Module for Vaultryn Voice-Activated Safety System
Handles MFCC feature extraction and audio preprocessing for on-device keyword spotting
"""

import torch
import torchaudio
import torchaudio.transforms as T
import numpy as np
import asyncio
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass
import io
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Configuration for audio processing"""
    sample_rate: int = 16000
    chunk_duration_ms: int = 500  # 500ms chunks for real-time processing
    context_duration_s: int = 5  # 5 seconds of context for SOS
    n_mfcc: int = 40  # Number of MFCC coefficients
    n_fft: int = 400  # FFT window size
    hop_length: int = 160  # Hop length for MFCC extraction
    n_mels: int = 40  # Number of mel filter banks
    target_confidence: float = 0.98  # Confidence threshold for keyword detection
    
    @property
    def chunk_samples(self) -> int:
        """Number of samples per chunk"""
        return int(self.sample_rate * self.chunk_duration_ms / 1000)
    
    @property
    def context_chunks(self) -> int:
        """Number of chunks in context window"""
        return int(self.context_duration_s * 1000 / self.chunk_duration_ms)


class MFCCProcessor:
    """
    MFCC feature extraction for keyword spotting
    Converts raw audio to spectrogram-like features suitable for CNN processing
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Initialize MFCC transform
        self.mfcc_transform = T.MFCC(
            sample_rate=config.sample_rate,
            n_mfcc=config.n_mfcc,
            melkwargs={
                'n_fft': config.n_fft,
                'hop_length': config.hop_length,
                'n_mels': config.n_mels,
                'power': 2.0
            }
        ).to(self.device)
        
        # Initialize normalization
        self.register_normalization_stats()
        
        logger.info(f"MFCC Processor initialized on {self.device}")
    
    def register_normalization_stats(self):
        """
        Register normalization statistics based on training data
        These would be computed from the training dataset
        """
        # Placeholder values - should be computed from actual training data
        self.mean = torch.tensor([-5.5, -4.8, -4.2, -3.7, -3.3, -2.9, -2.6, -2.3, 
                               -2.1, -1.9, -1.7, -1.5, -1.3, -1.1, -0.9, -0.8,
                               -0.6, -0.5, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2,
                               0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                               1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8]).to(self.device)
        
        self.std = torch.tensor([2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.1,
                               2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3,
                               1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5,
                               0.4, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1,
                               0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]).to(self.device)
    
    def extract_features(self, waveform: torch.Tensor) -> torch.Tensor:
        """
        Extract MFCC features from audio waveform
        
        Args:
            waveform: Audio tensor of shape [1, samples]
            
        Returns:
            MFCC features tensor of shape [1, n_mfcc, time_frames]
        """
        try:
            # Ensure waveform is on correct device
            waveform = waveform.to(self.device)
            
            # Extract MFCC features
            mfcc = self.mfcc_transform(waveform)
            
            # Normalize features
            mfcc_normalized = (mfcc - self.mean.view(-1, 1)) / self.std.view(-1, 1)
            
            # Clamp to prevent extreme values
            mfcc_clamped = torch.clamp(mfcc_normalized, -3.0, 3.0)
            
            return mfcc_clamped
            
        except Exception as e:
            logger.error(f"Error extracting MFCC features: {e}")
            raise
    
    def preprocess_audio_chunk(self, audio_data: bytes) -> torch.Tensor:
        """
        Preprocess raw audio chunk to MFCC features
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Preprocessed MFCC tensor
        """
        try:
            # Convert bytes to tensor
            waveform = self.bytes_to_waveform(audio_data)
            
            # Extract features
            features = self.extract_features(waveform)
            
            return features
            
        except Exception as e:
            logger.error(f"Error preprocessing audio chunk: {e}")
            raise
    
    def bytes_to_waveform(self, audio_data: bytes) -> torch.Tensor:
        """
        Convert raw audio bytes to PyTorch tensor
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            
        Returns:
            Audio waveform tensor
        """
        try:
            # Create in-memory WAV file
            audio_io = io.BytesIO(audio_data)
            
            # Read with torchaudio
            waveform, sample_rate = torchaudio.load(audio_io)
            
            # Resample if necessary
            if sample_rate != self.config.sample_rate:
                resampler = T.Resample(sample_rate, self.config.sample_rate).to(self.device)
                waveform = resampler(waveform)
            
            # Ensure mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Normalize to [-1, 1]
            waveform = waveform / 32768.0 if waveform.dtype == torch.int16 else waveform
            
            return waveform
            
        except Exception as e:
            logger.error(f"Error converting bytes to waveform: {e}")
            raise
    
    def create_spectrogram_image(self, mfcc_features: torch.Tensor) -> np.ndarray:
        """
        Convert MFCC features to visual spectrogram for debugging
        
        Args:
            mfcc_features: MFCC tensor
            
        Returns:
            Spectrogram image as numpy array
        """
        try:
            # Convert to numpy and transpose for visualization
            mfcc_np = mfcc_features.cpu().numpy()[0]  # Remove batch dimension
            
            # Normalize for visualization
            mfcc_vis = (mfcc_np - mfcc_np.min()) / (mfcc_np.max() - mfcc_np.min())
            
            # Convert to 8-bit image
            mfcc_image = (mfcc_vis * 255).astype(np.uint8)
            
            return mfcc_image
            
        except Exception as e:
            logger.error(f"Error creating spectrogram image: {e}")
            raise
    
    def save_debug_audio(self, audio_data: bytes, filename: str):
        """
        Save audio data for debugging purposes
        
        Args:
            audio_data: Raw audio bytes
            filename: Output filename
        """
        try:
            debug_dir = Path("debug_audio")
            debug_dir.mkdir(exist_ok=True)
            
            filepath = debug_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"Debug audio saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving debug audio: {e}")


class AudioBuffer:
    """
    Circular buffer for maintaining audio context
    Keeps the last N seconds of audio for SOS alert context
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.buffer = []
        self.max_size = config.context_chunks
        
        logger.info(f"Audio buffer initialized with {self.max_size} chunks capacity")
    
    def add_chunk(self, audio_data: bytes):
        """
        Add audio chunk to buffer
        
        Args:
            audio_data: Raw audio chunk bytes
        """
        try:
            if len(self.buffer) >= self.max_size:
                # Remove oldest chunk
                self.buffer.pop(0)
            
            self.buffer.append(audio_data)
            
        except Exception as e:
            logger.error(f"Error adding chunk to buffer: {e}")
    
    def get_context(self) -> bytes:
        """
        Get all audio data in buffer as single bytes object
        
        Returns:
            Concatenated audio context bytes
        """
        try:
            if not self.buffer:
                return b''
            
            # Concatenate all chunks
            context = b''.join(self.buffer)
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting context from buffer: {e}")
            return b''
    
    def clear(self):
        """Clear the audio buffer"""
        self.buffer.clear()
        logger.info("Audio buffer cleared")
    
    def size(self) -> int:
        """Get current buffer size"""
        return len(self.buffer)
    
    def duration_seconds(self) -> float:
        """Get current buffer duration in seconds"""
        return self.size() * self.config.chunk_duration_ms / 1000


class AudioRecorder:
    """
    Async audio recorder for real-time audio processing
    Handles microphone input and chunking for keyword spotting
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.is_recording = False
        self.audio_buffer = AudioBuffer(config)
        
        # Audio recording parameters
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = config.sample_rate
        self.chunk_size = config.chunk_samples
        
        try:
            import pyaudio
            self.pyaudio = pyaudio.PyAudio()
            logger.info("PyAudio initialized successfully")
        except ImportError:
            logger.error("PyAudio not available. Install with: pip install pyaudio")
            self.pyaudio = None
    
    async def start_recording(self):
        """Start recording audio in background"""
        if not self.pyaudio:
            raise RuntimeError("PyAudio not available")
        
        self.is_recording = True
        
        # Start recording task
        recording_task = asyncio.create_task(self._record_loop())
        
        logger.info("Audio recording started")
        return recording_task
    
    async def stop_recording(self):
        """Stop recording audio"""
        self.is_recording = False
        logger.info("Audio recording stopped")
    
    async def _record_loop(self):
        """Main recording loop"""
        try:
            # Open audio stream
            stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            logger.info("Audio stream opened")
            
            while self.is_recording:
                try:
                    # Read audio chunk
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # Add to buffer
                    self.audio_buffer.add_chunk(data)
                    
                    # Yield control to event loop
                    await asyncio.sleep(0)
                    
                except Exception as e:
                    logger.error(f"Error reading audio chunk: {e}")
                    await asyncio.sleep(0.1)  # Brief pause on error
            
            # Clean up
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            self.is_recording = False
    
    def get_audio_chunk(self) -> Optional[bytes]:
        """
        Get the most recent audio chunk
        
        Returns:
            Most recent audio chunk or None if buffer is empty
        """
        try:
            if self.audio_buffer.size() > 0:
                return self.audio_buffer.buffer[-1]
            return None
        except Exception as e:
            logger.error(f"Error getting audio chunk: {e}")
            return None
    
    def get_context_audio(self) -> bytes:
        """
        Get full audio context for SOS alert
        
        Returns:
            Audio context bytes
        """
        return self.audio_buffer.get_context()


class AudioPreprocessor:
    """
    Main audio preprocessing pipeline
    Combines MFCC processing, buffering, and recording
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.mfcc_processor = MFCCProcessor(config)
        self.audio_buffer = AudioBuffer(config)
        self.recorder = AudioRecorder(config)
        
        logger.info("Audio preprocessor initialized")
    
    async def start(self):
        """Start audio processing pipeline"""
        try:
            # Start recording
            recording_task = await self.recorder.start_recording()
            
            logger.info("Audio processing pipeline started")
            return recording_task
            
        except Exception as e:
            logger.error(f"Error starting audio processing: {e}")
            raise
    
    async def stop(self):
        """Stop audio processing pipeline"""
        try:
            await self.recorder.stop_recording()
            logger.info("Audio processing pipeline stopped")
        except Exception as e:
            logger.error(f"Error stopping audio processing: {e}")
    
    async def get_processed_chunk(self) -> Optional[torch.Tensor]:
        """
        Get processed audio chunk with MFCC features
        
        Returns:
            MFCC features tensor or None if no audio available
        """
        try:
            # Get raw audio chunk
            audio_chunk = self.recorder.get_audio_chunk()
            
            if audio_chunk is None:
                return None
            
            # Process with MFCC
            features = self.mfcc_processor.preprocess_audio_chunk(audio_chunk)
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting processed chunk: {e}")
            return None
    
    def get_context_audio(self) -> bytes:
        """Get full audio context for SOS alert"""
        return self.recorder.get_context_audio()
    
    def save_debug_data(self, features: torch.Tensor, audio_data: bytes, prefix: str):
        """
        Save debug data for analysis
        
        Args:
            features: MFCC features tensor
            audio_data: Raw audio data
            prefix: Prefix for debug files
        """
        try:
            # Save spectrogram
            spectrogram = self.mfcc_processor.create_spectrogram_image(features)
            debug_dir = Path("debug_audio")
            debug_dir.mkdir(exist_ok=True)
            
            # Save as image
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 4))
            plt.imshow(spectrogram, aspect='auto', origin='lower')
            plt.colorbar(label='MFCC Coefficient')
            plt.title(f'MFCC Spectrogram - {prefix}')
            plt.xlabel('Time Frame')
            plt.ylabel('MFCC Coefficient')
            plt.tight_layout()
            plt.savefig(debug_dir / f"{prefix}_spectrogram.png", dpi=150)
            plt.close()
            
            # Save audio
            self.mfcc_processor.save_debug_audio(audio_data, f"{prefix}_audio.wav")
            
            logger.info(f"Debug data saved with prefix: {prefix}")
            
        except Exception as e:
            logger.error(f"Error saving debug data: {e}")


# Utility functions
def create_test_audio(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """
    Create test audio for development and testing
    
    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz
        
    Returns:
        Audio bytes in WAV format
    """
    try:
        import numpy as np
        
        # Generate sine wave test signal
        samples = int(sample_rate * duration_ms / 1000)
        t = np.linspace(0, duration_ms/1000, samples)
        frequency = 440  # A4 note
        
        # Create test signal (sine wave with some noise)
        signal = np.sin(2 * np.pi * frequency * t) + 0.1 * np.random.randn(samples)
        
        # Convert to 16-bit PCM
        signal_int16 = (signal * 32767).astype(np.int16)
        
        # Create WAV file in memory
        audio_io = io.BytesIO()
        
        with wave.open(audio_io, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(signal_int16.tobytes())
        
        audio_io.seek(0)
        return audio_io.getvalue()
        
    except Exception as e:
        logger.error(f"Error creating test audio: {e}")
        return b''


if __name__ == "__main__":
    # Test audio processing
    import asyncio
    
    async def test_audio_processing():
        """Test audio processing pipeline"""
        config = AudioConfig()
        processor = AudioPreprocessor(config)
        
        # Create test audio
        test_audio = create_test_audio()
        
        # Process test audio
        features = processor.mfcc_processor.preprocess_audio_chunk(test_audio)
        
        print(f"MFCC features shape: {features.shape}")
        print(f"Feature range: [{features.min().item():.3f}, {features.max().item():.3f}]")
        
        # Save debug data
        processor.save_debug_data(features, test_audio, "test")
        
        print("Audio processing test completed successfully")
    
    asyncio.run(test_audio_processing())
