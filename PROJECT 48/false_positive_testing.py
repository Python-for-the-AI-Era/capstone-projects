"""
False Positive Testing and Threshold Tuning for Keyword Spotter
Comprehensive testing framework to ensure < 1 false positive per hour
"""

import asyncio
import logging
import time
import json
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import statistics

from audio_processing import AudioConfig, create_test_audio, MFCCProcessor
from keyword_spotter import KeywordSpotter, KeywordDetector, ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """Configuration for false positive testing"""
    test_duration_hours: float = 1.0  # Duration of background noise test
    sampling_rate: int = 16000
    chunk_duration_ms: int = 500
    confidence_thresholds: List[float] = None  # Thresholds to test
    
    # Test datasets
    background_noise_types: List[str] = None
    speech_variety_types: List[str] = None
    
    # Performance targets
    max_false_positives_per_hour: float = 1.0
    min_true_positive_rate: float = 0.99
    max_inference_time_ms: float = 200.0
    
    def __post_init__(self):
        if self.confidence_thresholds is None:
            self.confidence_thresholds = [0.90, 0.92, 0.94, 0.96, 0.98, 0.99]
        
        if self.background_noise_types is None:
            self.background_noise_types = [
                'silence', 'white_noise', 'pink_noise', 'brown_noise',
                'street_noise', 'office_noise', 'cafe_noise', 'traffic_noise',
                'wind', 'rain', 'thunder', 'tv_background', 'radio_background',
                'podcast_background', 'music_background', 'conversation_background'
            ]
        
        if self.speech_variety_types is None:
            self.speech_variety_types = [
                'news_broadcast', 'podcast', 'audiobook', 'lecture',
                'phone_call', 'group_conversation', 'meeting', 'interview',
                'sports_commentary', 'weather_report', 'traffic_report'
            ]


@dataclass
class TestResult:
    """Result of false positive test"""
    threshold: float
    total_predictions: int
    false_positives: int
    true_positives: int
    false_positive_rate: float
    true_positive_rate: float
    inference_time_ms: float
    test_duration_hours: float
    false_positives_per_hour: float
    meets_requirements: bool
    
    def to_dict(self) -> Dict:
        return asdict(self)


class BackgroundNoiseGenerator:
    """
    Generate various types of background noise for testing
    Simulates real-world audio environments
    """
    
    def __init__(self, config: TestConfig, audio_config: AudioConfig):
        self.config = config
        self.audio_config = audio_config
        self.sample_rate = audio_config.sample_rate
        
    def generate_silence(self, duration_ms: int) -> np.ndarray:
        """Generate pure silence"""
        samples = int(self.sample_rate * duration_ms / 1000)
        return np.zeros(samples, dtype=np.float32)
    
    def generate_white_noise(self, duration_ms: int, amplitude: float = 0.1) -> np.ndarray:
        """Generate white noise"""
        samples = int(self.sample_rate * duration_ms / 1000)
        noise = np.random.normal(0, amplitude, samples).astype(np.float32)
        return noise
    
    def generate_pink_noise(self, duration_ms: int, amplitude: float = 0.1) -> np.ndarray:
        """Generate pink noise (1/f noise)"""
        samples = int(self.sample_rate * duration_ms / 1000)
        
        # Generate white noise
        white = np.random.normal(0, amplitude, samples)
        
        # Apply pink filter (simplified)
        pink = np.zeros_like(white)
        pink[0] = white[0]
        
        for i in range(1, samples):
            pink[i] = pink[i-1] * 0.99 + white[i] * 0.01
        
        return pink.astype(np.float32)
    
    def generate_brown_noise(self, duration_ms: int, amplitude: float = 0.1) -> np.ndarray:
        """Generate brown noise (1/f² noise)"""
        samples = int(self.sample_rate * duration_ms / 1000)
        
        # Generate white noise
        white = np.random.normal(0, amplitude, samples)
        
        # Apply brown filter
        brown = np.zeros_like(white)
        brown[0] = white[0]
        
        for i in range(1, samples):
            brown[i] = brown[i-1] * 0.999 + white[i] * 0.001
        
        return brown.astype(np.float32)
    
    def generate_street_noise(self, duration_ms: int) -> np.ndarray:
        """Generate street noise simulation"""
        samples = int(self.sample_rate * duration_ms / 1000)
        
        # Combine multiple noise sources
        noise = (self.generate_white_noise(duration_ms, 0.05) +
                self.generate_pink_noise(duration_ms, 0.03) +
                np.random.normal(0, 0.02, samples))  # Random spikes
        
        # Add occasional "car horn" sounds
        if np.random.random() < 0.1:  # 10% chance
            horn_start = np.random.randint(0, samples - 1000)
            horn_freq = 800 + np.random.random() * 400
            t = np.linspace(0, 1000/self.sample_rate, 1000)
            horn = 0.2 * np.sin(2 * np.pi * horn_freq * t) * np.exp(-t * 5)
            noise[horn_start:horn_start+1000] += horn.astype(np.float32)
        
        return noise
    
    def generate_office_noise(self, duration_ms: int) -> np.ndarray:
        """Generate office background noise"""
        samples = int(self.sample_rate * duration_ms / 1000)
        
        # Base noise (air conditioning, electronics)
        noise = self.generate_pink_noise(duration_ms, 0.02)
        
        # Add occasional keyboard sounds
        if np.random.random() < 0.3:  # 30% chance
            keyboard_start = np.random.randint(0, samples - 500)
            keyboard_freq = 2000 + np.random.random() * 1000
            t = np.linspace(0, 500/self.sample_rate, 500)
            keyboard = 0.1 * np.sin(2 * np.pi * keyboard_freq * t) * np.exp(-t * 20)
            noise[keyboard_start:keyboard_start+500] += keyboard.astype(np.float32)
        
        return noise
    
    def generate_conversation_background(self, duration_ms: int) -> np.ndarray:
        """Generate background conversation noise"""
        samples = int(self.sample_rate * duration_ms / 1000)
        
        # Base conversation-like noise (modulated noise)
        noise = self.generate_pink_noise(duration_ms, 0.08)
        
        # Add speech-like modulation
        t = np.linspace(0, duration_ms/1000, samples)
        modulation = 1 + 0.3 * np.sin(2 * np.pi * 2 * t) + 0.2 * np.sin(2 * np.pi * 5 * t)
        noise *= modulation
        
        return noise
    
    def generate_noise(self, noise_type: str, duration_ms: int) -> np.ndarray:
        """Generate specific type of noise"""
        generators = {
            'silence': self.generate_silence,
            'white_noise': self.generate_white_noise,
            'pink_noise': self.generate_pink_noise,
            'brown_noise': self.generate_brown_noise,
            'street_noise': self.generate_street_noise,
            'office_noise': self.generate_office_noise,
            'cafe_noise': self.generate_conversation_background,
            'traffic_noise': self.generate_street_noise,
            'wind': lambda d: self.generate_pink_noise(d, 0.06),
            'rain': lambda d: self.generate_pink_noise(d, 0.04),
            'thunder': self.generate_street_noise,
            'tv_background': self.generate_conversation_background,
            'radio_background': self.generate_conversation_background,
            'podcast_background': self.generate_conversation_background,
            'music_background': self.generate_conversation_background,
            'conversation_background': self.generate_conversation_background
        }
        
        generator = generators.get(noise_type, self.generate_white_noise)
        return generator(duration_ms)


class KeywordTestGenerator:
    """
    Generate keyword test samples for true positive testing
    """
    
    def __init__(self, config: TestConfig, audio_config: AudioConfig):
        self.config = config
        self.audio_config = audio_config
        self.sample_rate = audio_config.sample_rate
        
        # Target keyword: "help"
        self.keyword = "help"
    
    def generate_keyword_sample(self, variation: str = "normal") -> np.ndarray:
        """
        Generate a keyword sample with variations
        
        Args:
            variation: Type of variation to apply
            
        Returns:
            Audio array containing keyword
        """
        duration_ms = 500  # Typical keyword duration
        samples = int(self.sample_rate * duration_ms / 1000)
        t = np.linspace(0, duration_ms/1000, samples)
        
        # Generate base keyword-like signal
        # This is a simplified simulation - in reality, you'd use real recordings
        if variation == "normal":
            # Normal "help" pronunciation
            freq1, freq2, freq3 = 200, 400, 800  # Formant frequencies
            signal = (0.3 * np.sin(2 * np.pi * freq1 * t) +
                     0.2 * np.sin(2 * np.pi * freq2 * t) +
                     0.1 * np.sin(2 * np.pi * freq3 * t))
            
        elif variation == "whisper":
            # Whispered version
            freq1, freq2 = 150, 300
            signal = (0.2 * np.sin(2 * np.pi * freq1 * t) +
                     0.1 * np.sin(2 * np.pi * freq2 * t))
            
        elif variation == "shout":
            # Shouted version
            freq1, freq2, freq3 = 250, 500, 1000
            signal = (0.5 * np.sin(2 * np.pi * freq1 * t) +
                     0.4 * np.sin(2 * np.pi * freq2 * t) +
                     0.3 * np.sin(2 * np.pi * freq3 * t))
            
        elif variation == "fast":
            # Fast pronunciation
            duration_ms = 300
            samples = int(self.sample_rate * duration_ms / 1000)
            t = np.linspace(0, duration_ms/1000, samples)
            freq1, freq2 = 250, 500
            signal = (0.4 * np.sin(2 * np.pi * freq1 * t) +
                     0.3 * np.sin(2 * np.pi * freq2 * t))
            
        elif variation == "slow":
            # Slow pronunciation
            duration_ms = 800
            samples = int(self.sample_rate * duration_ms / 1000)
            t = np.linspace(0, duration_ms/1000, samples)
            freq1, freq2, freq3 = 180, 360, 720
            signal = (0.3 * np.sin(2 * np.pi * freq1 * t) +
                     0.2 * np.sin(2 * np.pi * freq2 * t) +
                     0.1 * np.sin(2 * np.pi * freq3 * t))
            
        else:
            # Default to normal
            return self.generate_keyword_sample("normal")
        
        # Add envelope for natural speech
        envelope = np.exp(-((t - duration_ms/2000) ** 2) / (duration_ms/4000) ** 2)
        signal *= envelope
        
        # Add small amount of noise
        signal += np.random.normal(0, 0.02, len(signal))
        
        return signal.astype(np.float32)
    
    def generate_keyword_variations(self) -> List[np.ndarray]:
        """Generate multiple variations of the keyword"""
        variations = ["normal", "whisper", "shout", "fast", "slow"]
        return [self.generate_keyword_sample(var) for var in variations]


class FalsePositiveTester:
    """
    Comprehensive false positive testing framework
    Tests keyword spotter against various background conditions
    """
    
    def __init__(self, model: KeywordSpotter, audio_config: AudioConfig, 
                 test_config: TestConfig):
        self.model = model
        self.audio_config = audio_config
        self.test_config = test_config
        
        # Initialize components
        self.noise_generator = BackgroundNoiseGenerator(test_config, audio_config)
        self.keyword_generator = KeywordTestGenerator(test_config, audio_config)
        self.mfcc_processor = MFCCProcessor(audio_config)
        
        # Test results storage
        self.test_results = []
        self.detailed_logs = []
        
        logger.info("FalsePositiveTester initialized")
    
    async def test_false_positive_rate(self, confidence_threshold: float) -> TestResult:
        """
        Test false positive rate for a specific confidence threshold
        
        Args:
            confidence_threshold: Confidence threshold to test
            
        Returns:
            Test result with metrics
        """
        logger.info(f"Testing false positive rate with threshold: {confidence_threshold}")
        
        # Create detector with specified threshold
        detector = KeywordDetector(self.model, self.audio_config)
        detector.set_confidence_threshold(confidence_threshold)
        
        # Test statistics
        total_predictions = 0
        false_positives = 0
        inference_times = []
        
        # Calculate number of chunks needed
        chunks_per_hour = 3600 * 1000 // self.test_config.chunk_duration_ms
        total_chunks = int(chunks_per_hour * self.test_config.test_duration_hours)
        
        logger.info(f"Processing {total_chunks} audio chunks...")
        
        start_time = time.time()
        
        # Process background noise chunks
        for chunk_idx in range(total_chunks):
            # Randomly select noise type
            noise_type = np.random.choice(self.test_config.background_noise_types)
            
            # Generate noise chunk
            noise_audio = self.noise_generator.generate_noise(
                noise_type, 
                self.test_config.chunk_duration_ms
            )
            
            # Convert to bytes (simulate real audio processing)
            audio_bytes = (noise_audio * 32767).astype(np.int16).tobytes()
            
            # Process with MFCC
            inference_start = time.time()
            features = self.mfcc_processor.preprocess_audio_chunk(audio_bytes)
            inference_time = (time.time() - inference_start) * 1000  # Convert to ms
            inference_times.append(inference_time)
            
            # Detect keyword
            detection = detector.detect_keyword(features)
            
            total_predictions += 1
            
            if detection:
                false_positives += 1
                logger.warning(f"False positive detected: {noise_type}, confidence: {detection['confidence']:.3f}")
                
                # Log detailed information
                self.detailed_logs.append({
                    'chunk_idx': chunk_idx,
                    'noise_type': noise_type,
                    'confidence': detection['confidence'],
                    'threshold': confidence_threshold,
                    'timestamp': time.time()
                })
            
            # Progress reporting
            if (chunk_idx + 1) % 1000 == 0:
                progress = (chunk_idx + 1) / total_chunks * 100
                current_fpr = false_positives / max(total_predictions, 1)
                logger.info(f"Progress: {progress:.1f}%, Current FPR: {current_fpr:.4f}")
        
        end_time = time.time()
        actual_duration = (end_time - start_time) / 3600  # Convert to hours
        
        # Calculate metrics
        false_positive_rate = false_positives / max(total_predictions, 1)
        false_positives_per_hour = false_positives / max(actual_duration, 1)
        avg_inference_time = statistics.mean(inference_times)
        
        # Check if meets requirements
        meets_requirements = (
            false_positives_per_hour <= self.test_config.max_false_positives_per_hour and
            avg_inference_time <= self.test_config.max_inference_time_ms
        )
        
        result = TestResult(
            threshold=confidence_threshold,
            total_predictions=total_predictions,
            false_positives=false_positives,
            true_positives=0,  # Will be calculated in separate test
            false_positive_rate=false_positive_rate,
            true_positive_rate=0.0,  # Will be calculated in separate test
            inference_time_ms=avg_inference_time,
            test_duration_hours=actual_duration,
            false_positives_per_hour=false_positives_per_hour,
            meets_requirements=meets_requirements
        )
        
        logger.info(f"False positive test completed: {false_positives}/{total_predictions} "
                   f"({false_positive_rate:.4f}) in {actual_duration:.2f} hours")
        
        return result
    
    async def test_true_positive_rate(self, confidence_threshold: float) -> TestResult:
        """
        Test true positive rate for keyword detection
        
        Args:
            confidence_threshold: Confidence threshold to test
            
        Returns:
            Test result with true positive metrics
        """
        logger.info(f"Testing true positive rate with threshold: {confidence_threshold}")
        
        # Create detector with specified threshold
        detector = KeywordDetector(self.model, self.audio_config)
        detector.set_confidence_threshold(confidence_threshold)
        
        # Generate keyword variations
        keyword_samples = self.keyword_generator.generate_keyword_variations()
        
        # Test statistics
        total_tests = len(keyword_samples) * 10  # Test each variation 10 times
        true_positives = 0
        inference_times = []
        
        for sample_idx, sample in enumerate(keyword_samples):
            for test_idx in range(10):
                # Add some noise to simulate real conditions
                noise = self.noise_generator.generate_white_noise(500, 0.05)
                noisy_sample = sample + noise
                
                # Convert to bytes
                audio_bytes = (noisy_sample * 32767).astype(np.int16).tobytes()
                
                # Process with MFCC
                inference_start = time.time()
                features = self.mfcc_processor.preprocess_audio_chunk(audio_bytes)
                inference_time = (time.time() - inference_start) * 1000
                inference_times.append(inference_time)
                
                # Detect keyword
                detection = detector.detect_keyword(features)
                
                if detection:
                    true_positives += 1
                    logger.debug(f"True positive detected: confidence {detection['confidence']:.3f}")
        
        # Calculate metrics
        true_positive_rate = true_positives / max(total_tests, 1)
        avg_inference_time = statistics.mean(inference_times)
        
        # Check if meets requirements
        meets_requirements = (
            true_positive_rate >= self.test_config.min_true_positive_rate and
            avg_inference_time <= self.test_config.max_inference_time_ms
        )
        
        result = TestResult(
            threshold=confidence_threshold,
            total_predictions=total_tests,
            false_positives=0,
            true_positives=true_positives,
            false_positive_rate=0.0,
            true_positive_rate=true_positive_rate,
            inference_time_ms=avg_inference_time,
            test_duration_hours=0.0,  # Not applicable for TP test
            false_positives_per_hour=0.0,
            meets_requirements=meets_requirements
        )
        
        logger.info(f"True positive test completed: {true_positives}/{total_tests} "
                   f"({true_positive_rate:.4f})")
        
        return result
    
    async def comprehensive_threshold_testing(self) -> List[TestResult]:
        """
        Test multiple confidence thresholds to find optimal setting
        
        Returns:
            List of test results for each threshold
        """
        logger.info("Starting comprehensive threshold testing...")
        
        all_results = []
        
        for threshold in self.test_config.confidence_thresholds:
            logger.info(f"Testing threshold: {threshold}")
            
            # Test false positive rate
            fp_result = await self.test_false_positive_rate(threshold)
            
            # Test true positive rate
            tp_result = await self.test_true_positive_rate(threshold)
            
            # Combine results
            combined_result = TestResult(
                threshold=threshold,
                total_predictions=fp_result.total_predictions + tp_result.total_predictions,
                false_positives=fp_result.false_positives,
                true_positives=tp_result.true_positives,
                false_positive_rate=fp_result.false_positive_rate,
                true_positive_rate=tp_result.true_positive_rate,
                inference_time_ms=(fp_result.inference_time_ms + tp_result.inference_time_ms) / 2,
                test_duration_hours=fp_result.test_duration_hours,
                false_positives_per_hour=fp_result.false_positives_per_hour,
                meets_requirements=(
                    fp_result.meets_requirements and tp_result.meets_requirements
                )
            )
            
            all_results.append(combined_result)
            
            # Brief pause between tests
            await asyncio.sleep(1)
        
        self.test_results = all_results
        logger.info("Comprehensive threshold testing completed")
        
        return all_results
    
    def find_optimal_threshold(self) -> Tuple[float, TestResult]:
        """
        Find the optimal confidence threshold based on test results
        
        Returns:
            Tuple of (optimal_threshold, best_result)
        """
        if not self.test_results:
            raise ValueError("No test results available. Run comprehensive testing first.")
        
        # Find threshold that meets requirements with highest TPR
        valid_results = [r for r in self.test_results if r.meets_requirements]
        
        if not valid_results:
            # If no threshold meets requirements, find the one with lowest FPR
            best_result = min(self.test_results, key=lambda r: r.false_positive_rate)
        else:
            # Find threshold with highest TPR among valid ones
            best_result = max(valid_results, key=lambda r: r.true_positive_rate)
        
        return best_result.threshold, best_result
    
    def generate_report(self, output_path: str = "false_positive_report.json"):
        """
        Generate comprehensive test report
        
        Args:
            output_path: Path to save report
        """
        if not self.test_results:
            raise ValueError("No test results available. Run testing first.")
        
        # Find optimal threshold
        optimal_threshold, optimal_result = self.find_optimal_threshold()
        
        # Prepare report data
        report = {
            'test_config': asdict(self.test_config),
            'optimal_threshold': optimal_threshold,
            'optimal_result': optimal_result.to_dict(),
            'all_results': [r.to_dict() for r in self.test_results],
            'detailed_logs': self.detailed_logs[:100],  # Limit logs size
            'summary': {
                'total_thresholds_tested': len(self.test_results),
                'thresholds_meeting_requirements': len([r for r in self.test_results if r.meets_requirements]),
                'best_false_positives_per_hour': min(r.false_positives_per_hour for r in self.test_results),
                'best_true_positive_rate': max(r.true_positive_rate for r in self.test_results),
                'average_inference_time': statistics.mean([r.inference_time_ms for r in self.test_results])
            }
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Test report saved to {output_path}")
        return report
    
    def create_visualizations(self, output_dir: str = "test_plots"):
        """
        Create visualization plots for test results
        
        Args:
            output_dir: Directory to save plots
        """
        if not self.test_results:
            raise ValueError("No test results available. Run testing first.")
        
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        # Extract data for plotting
        thresholds = [r.threshold for r in self.test_results]
        fp_rates = [r.false_positive_rate for r in self.test_results]
        fp_per_hour = [r.false_positives_per_hour for r in self.test_results]
        tp_rates = [r.true_positive_rate for r in self.test_results]
        inference_times = [r.inference_time_ms for r in self.test_results]
        
        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Plot 1: False Positive Rate vs Threshold
        ax1.plot(thresholds, fp_rates, 'b-o', linewidth=2, markersize=8)
        ax1.axhline(y=self.test_config.max_false_positives_per_hour/7200, 
                   color='r', linestyle='--', label='Target FPR')
        ax1.set_xlabel('Confidence Threshold')
        ax1.set_ylabel('False Positive Rate')
        ax1.set_title('False Positive Rate vs Confidence Threshold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Plot 2: False Positives Per Hour vs Threshold
        ax2.plot(thresholds, fp_per_hour, 'r-o', linewidth=2, markersize=8)
        ax2.axhline(y=self.test_config.max_false_positives_per_hour, 
                   color='r', linestyle='--', label='Target (<1/hour)')
        ax2.set_xlabel('Confidence Threshold')
        ax2.set_ylabel('False Positives Per Hour')
        ax2.set_title('False Positives Per Hour vs Confidence Threshold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Plot 3: True Positive Rate vs Threshold
        ax3.plot(thresholds, tp_rates, 'g-o', linewidth=2, markersize=8)
        ax3.axhline(y=self.test_config.min_true_positive_rate, 
                   color='r', linestyle='--', label='Target TPR')
        ax3.set_xlabel('Confidence Threshold')
        ax3.set_ylabel('True Positive Rate')
        ax3.set_title('True Positive Rate vs Confidence Threshold')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        
        # Plot 4: Inference Time vs Threshold
        ax4.plot(thresholds, inference_times, 'm-o', linewidth=2, markersize=8)
        ax4.axhline(y=self.test_config.max_inference_time_ms, 
                   color='r', linestyle='--', label='Target (<200ms)')
        ax4.set_xlabel('Confidence Threshold')
        ax4.set_ylabel('Average Inference Time (ms)')
        ax4.set_title('Inference Time vs Confidence Threshold')
        ax4.grid(True, alpha=0.3)
        ax4.legend()
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/threshold_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Create ROC-like curve
        plt.figure(figsize=(10, 8))
        plt.plot(fp_rates, tp_rates, 'b-o', linewidth=2, markersize=8)
        
        # Mark optimal point
        optimal_threshold, optimal_result = self.find_optimal_threshold()
        plt.plot(optimal_result.false_positive_rate, optimal_result.true_positive_rate, 
                'r*', markersize=15, label=f'Optimal ({optimal_threshold:.2f})')
        
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve for Keyword Detection')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(f"{output_dir}/roc_curve.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualizations saved to {output_dir}")


# Demo function
async def demo_false_positive_testing():
    """Demonstrate false positive testing"""
    # Initialize configurations
    audio_config = AudioConfig()
    model_config = ModelConfig()
    test_config = TestConfig(test_duration_hours=0.1)  # Short test for demo
    
    # Create model
    model = KeywordSpotter(model_config)
    
    # Create tester
    tester = FalsePositiveTester(model, audio_config, test_config)
    
    try:
        # Run comprehensive testing
        print("🧪 Starting false positive testing...")
        results = await tester.comprehensive_threshold_testing()
        
        # Find optimal threshold
        optimal_threshold, optimal_result = tester.find_optimal_threshold()
        
        print(f"\n📊 Test Results:")
        print(f"   Optimal Threshold: {optimal_threshold}")
        print(f"   False Positives/Hour: {optimal_result.false_positives_per_hour:.2f}")
        print(f"   True Positive Rate: {optimal_result.true_positive_rate:.4f}")
        print(f"   Inference Time: {optimal_result.inference_time_ms:.1f}ms")
        print(f"   Meets Requirements: {optimal_result.meets_requirements}")
        
        # Generate report
        report = tester.generate_report()
        print(f"\n📄 Report generated: false_positive_report.json")
        
        # Create visualizations
        tester.create_visualizations()
        print(f"📈 Visualizations created: test_plots/")
        
    except Exception as e:
        print(f"❌ Testing error: {e}")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_false_positive_testing())
