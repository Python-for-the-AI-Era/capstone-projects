#!/usr/bin/env python3
"""
Training script for the keyword spotter model.

This script trains the lightweight CNN model for keyword detection
with proper data preparation, augmentation, and evaluation.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from audio.processor import AudioProcessor, AudioConfig, AudioAugmentation
from models.keyword_spotter import KeywordSpotter, ModelConfig, create_dataset_from_features
from utils.data_generator import generate_training_data, load_background_audio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeywordSpotterTrainer:
    """Trainer for keyword spotter model."""
    
    def __init__(self, config: ModelConfig):
        """
        Initialize trainer.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self.device = torch.device(config.device)
        
        # Initialize components
        self.audio_processor = AudioProcessor(AudioConfig(
            sample_rate=16000,
            window_size=0.5,
            hop_size=0.1,
            n_mfcc=config.input_features
        ))
        self.augmentation = AudioAugmentation(sample_rate=16000)
        self.spotter = KeywordSpotter(config)
        
        # Training state
        self.training_history = []
        self.best_model_path = None
        self.training_stats = {
            'total_samples': 0,
            'keyword_samples': 0,
            'background_samples': 0,
            'augmentation_factor': 0
        }
        
        logger.info(f"Keyword spotter trainer initialized with config: {config}")
    
    def prepare_training_data(self, keyword_samples_dir: str, background_audio_dir: str) -> tuple:
        """
        Prepare training data from keyword and background audio samples.
        
        Args:
            keyword_samples_dir: Directory containing keyword audio samples
            background_audio_dir: Directory containing background audio
            
        Returns:
            Tuple of (features, labels)
        """
        logger.info("Preparing training data...")
        
        keyword_features = []
        background_features = []
        
        # Process keyword samples
        keyword_dir = Path(keyword_samples_dir)
        if keyword_dir.exists():
            for audio_file in keyword_dir.glob("*.wav"):
                try:
                    mfcc, _ = self.audio_processor.process_audio_file(str(audio_file))
                    keyword_features.append(mfcc)
                    logger.debug(f"Processed keyword sample: {audio_file}")
                except Exception as e:
                    logger.warning(f"Error processing {audio_file}: {e}")
        
        # Process background audio
        background_dir = Path(background_audio_dir)
        if background_dir.exists():
            for audio_file in background_dir.glob("*.wav"):
                try:
                    mfcc, _ = self.audio_processor.process_audio_file(str(audio_file))
                    background_features.append(mfcc)
                    logger.debug(f"Processed background sample: {audio_file}")
                except Exception as e:
                    logger.warning(f"Error processing {audio_file}: {e}")
        
        # Generate synthetic data if needed
        if len(keyword_features) < 100:
            logger.info("Generating synthetic keyword samples...")
            synthetic_features = generate_training_data(
                target_keyword="help",
                num_samples=100 - len(keyword_features),
                sample_rate=16000,
                duration=1.0
            )
            keyword_features.extend(synthetic_features)
        
        if len(background_features) < 500:
            logger.info("Generating synthetic background samples...")
            synthetic_background = load_background_audio(
                num_samples=500 - len(background_features),
                sample_rate=16000,
                duration=1.0
            )
            background_features.extend(synthetic_background)
        
        # Create labels (1 for keyword, 0 for background)
        keyword_labels = [1] * len(keyword_features)
        background_labels = [0] * len(background_features)
        
        # Combine data
        all_features = keyword_features + background_features
        all_labels = keyword_labels + background_labels
        
        # Update statistics
        self.training_stats.update({
            'total_samples': len(all_features),
            'keyword_samples': len(keyword_features),
            'background_samples': len(background_features)
        })
        
        logger.info(f"Training data prepared: {len(keyword_features)} keyword samples, "
                   f"{len(background_features)} background samples")
        
        return all_features, all_labels
    
    def augment_data(self, features: list, labels: list, augmentation_factor: int = 3) -> tuple:
        """
        Augment training data to improve model robustness.
        
        Args:
            features: List of MFCC features
            labels: List of labels
            augmentation_factor: Number of augmented samples per original
            
        Returns:
            Tuple of (augmented_features, augmented_labels)
        """
        logger.info(f"Augmenting data with factor {augmentation_factor}...")
        
        augmented_features = []
        augmented_labels = []
        
        for i, (feature, label) in enumerate(zip(features, labels)):
            # Add original
            augmented_features.append(feature)
            augmented_labels.append(label)
            
            # Add augmented versions
            for _ in range(augmentation_factor):
                # Convert to waveform (simplified inverse MFCC)
                # In practice, you'd store original waveforms for augmentation
                augmented_feature = feature.clone()
                
                # Apply simple augmentation (time shift simulation)
                if torch.rand(1).item() < 0.5:
                    shift = torch.randint(-5, 5, (1,)).item()
                    if shift > 0:
                        augmented_feature = torch.cat([
                            augmented_feature[:, shift:],
                            torch.zeros_like(augmented_feature[:, :shift])
                        ], dim=1)
                    elif shift < 0:
                        augmented_feature = torch.cat([
                            torch.zeros_like(augmented_feature[:, :abs(shift)]),
                            augmented_feature[:, :shift]
                        ], dim=1)
                
                # Add noise
                if torch.rand(1).item() < 0.3:
                    noise = torch.randn_like(augmented_feature) * 0.1
                    augmented_feature = augmented_feature + noise
                
                augmented_features.append(augmented_feature)
                augmented_labels.append(label)
        
        self.training_stats['augmentation_factor'] = augmentation_factor
        logger.info(f"Data augmentation completed: {len(augmented_features)} samples")
        
        return augmented_features, augmented_labels
    
    def create_data_loaders(self, features: list, labels: list, 
                          batch_size: int = 32, val_split: float = 0.2) -> tuple:
        """
        Create training and validation data loaders.
        
        Args:
            features: List of MFCC features
            labels: List of labels
            batch_size: Batch size
            val_split: Validation split ratio
            
        Returns:
            Tuple of (train_loader, val_loader)
        """
        # Create dataset
        dataset = create_dataset_from_features(features, labels)
        
        # Split into train and validation
        val_size = int(len(dataset) * val_split)
        train_size = len(dataset) - val_size
        
        train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
        
        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=2,
            pin_memory=True
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=2,
            pin_memory=True
        )
        
        logger.info(f"Data loaders created: {len(train_dataset)} train samples, "
                   f"{len(val_dataset)} validation samples")
        
        return train_loader, val_loader
    
    def train_model(self, train_loader: DataLoader, val_loader: DataLoader,
                   num_epochs: int = 50, learning_rate: float = 0.001,
                   save_path: str = "models/keyword_spotter.pth") -> dict:
        """
        Train the keyword spotter model.
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            num_epochs: Number of training epochs
            learning_rate: Learning rate
            save_path: Path to save best model
            
        Returns:
            Training history
        """
        logger.info(f"Starting model training for {num_epochs} epochs...")
        
        # Train the model
        training_history = self.spotter.train(
            train_loader, val_loader, num_epochs, learning_rate
        )
        
        # Save best model
        self.best_model_path = save_path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        self.spotter.save_model(save_path)
        
        # Export for mobile
        mobile_path = save_path.replace('.pth', '_mobile.pt')
        self.spotter.export_for_mobile(mobile_path)
        
        logger.info(f"Model training completed. Best model saved to: {save_path}")
        
        return training_history
    
    def evaluate_model(self, test_loader: DataLoader) -> dict:
        """
        Evaluate the trained model.
        
        Args:
            test_loader: Test data loader
            
        Returns:
            Evaluation metrics
        """
        logger.info("Evaluating model...")
        
        metrics = self.spotter.evaluate(test_loader)
        
        logger.info(f"Evaluation results: {metrics}")
        
        return metrics
    
    def test_false_positive_rate(self, duration_hours: float = 1.0) -> float:
        """
        Test false positive rate on background audio.
        
        Args:
            duration_hours: Duration of test audio in hours
            
        Returns:
            False positive rate per hour
        """
        logger.info(f"Testing false positive rate on {duration_hours} hours of background audio...")
        
        # Generate or load background audio
        background_audio = load_background_audio(
            num_samples=int(duration_hours * 60),  # 1 sample per minute
            sample_rate=16000,
            duration=5.0  # 5 seconds per sample
        )
        
        false_positives = 0
        total_samples = len(background_audio)
        
        for i, audio in enumerate(background_audio):
            # Process audio
            mfcc = self.audio_processor.extract_mfcc(audio.unsqueeze(0))
            
            # Detect keyword
            detected, confidence = self.spotter.detect_keyword(mfcc)
            
            if detected:
                false_positives += 1
                logger.debug(f"False positive at sample {i}, confidence: {confidence:.3f}")
        
        fpr = false_positives / total_samples
        fpr_per_hour = fpr * (60 / 5)  # Convert to per hour rate
        
        logger.info(f"False positive rate: {fpr:.4f} ({fpr_per_hour:.2f} per hour)")
        
        return fpr_per_hour
    
    def plot_training_history(self, history: dict, save_path: str = "plots/training_history.png"):
        """
        Plot training history.
        
        Args:
            history: Training history dictionary
            save_path: Path to save plot
        """
        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
            
            epochs = history['epochs']
            
            # Loss plot
            ax1.plot(epochs, history['train_loss'], label='Train Loss', color='blue')
            ax1.plot(epochs, history['val_loss'], label='Validation Loss', color='red')
            ax1.set_xlabel('Epoch')
            ax1.set_ylabel('Loss')
            ax1.set_title('Training and Validation Loss')
            ax1.legend()
            ax1.grid(True)
            
            # Accuracy plot
            ax2.plot(epochs, history['train_acc'], label='Train Accuracy', color='blue')
            ax2.plot(epochs, history['val_acc'], label='Validation Accuracy', color='red')
            ax2.set_xlabel('Epoch')
            ax2.set_ylabel('Accuracy (%)')
            ax2.set_title('Training and Validation Accuracy')
            ax2.legend()
            ax2.grid(True)
            
            plt.tight_layout()
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Training history plot saved to: {save_path}")
            
        except Exception as e:
            logger.error(f"Error plotting training history: {e}")
    
    def save_training_report(self, history: dict, metrics: dict, fpr: float,
                           save_path: str = "reports/training_report.json"):
        """
        Save comprehensive training report.
        
        Args:
            history: Training history
            metrics: Evaluation metrics
            fpr: False positive rate
            save_path: Path to save report
        """
        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            report = {
                'training_config': {
                    'model_config': self.config.__dict__,
                    'training_stats': self.training_stats,
                    'best_model_path': self.best_model_path
                },
                'training_history': history,
                'evaluation_metrics': metrics,
                'false_positive_rate_per_hour': fpr,
                'model_info': self.spotter.get_model_info(),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(save_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Training report saved to: {save_path}")
            
        except Exception as e:
            logger.error(f"Error saving training report: {e}")
    
    def run_full_training_pipeline(self, keyword_samples_dir: str, background_audio_dir: str,
                                 output_dir: str = "output") -> dict:
        """
        Run complete training pipeline.
        
        Args:
            keyword_samples_dir: Directory with keyword samples
            background_audio_dir: Directory with background audio
            output_dir: Output directory
            
        Returns:
            Training results
        """
        logger.info("Starting full training pipeline...")
        
        # Prepare data
        features, labels = self.prepare_training_data(keyword_samples_dir, background_audio_dir)
        
        # Augment data
        augmented_features, augmented_labels = self.augment_data(features, labels)
        
        # Create data loaders
        train_loader, val_loader = self.create_data_loaders(augmented_features, augmented_labels)
        
        # Train model
        history = self.train_model(train_loader, val_loader, save_path=f"{output_dir}/models/keyword_spotter.pth")
        
        # Evaluate model
        metrics = self.evaluate_model(val_loader)
        
        # Test false positive rate
        fpr = self.test_false_positive_rate()
        
        # Save results
        self.plot_training_history(history, f"{output_dir}/plots/training_history.png")
        self.save_training_report(history, metrics, fpr, f"{output_dir}/reports/training_report.json")
        
        results = {
            'training_history': history,
            'evaluation_metrics': metrics,
            'false_positive_rate_per_hour': fpr,
            'model_path': f"{output_dir}/models/keyword_spotter.pth",
            'mobile_model_path': f"{output_dir}/models/keyword_spotter_mobile.pt"
        }
        
        logger.info("Full training pipeline completed successfully!")
        return results


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description='Train keyword spotter model')
    parser.add_argument('--keyword-samples', type=str, default='data/keyword_samples',
                       help='Directory containing keyword audio samples')
    parser.add_argument('--background-audio', type=str, default='data/background_audio',
                       help='Directory containing background audio')
    parser.add_argument('--output-dir', type=str, default='output',
                       help='Output directory')
    parser.add_argument('--epochs', type=int, default=50,
                       help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                       help='Batch size')
    parser.add_argument('--learning-rate', type=float, default=0.001,
                       help='Learning rate')
    parser.add_argument('--device', type=str, default='auto',
                       help='Device to use (auto/cpu/cuda)')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine device
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    # Create model configuration
    config = ModelConfig(
        input_features=13,
        sequence_length=50,
        conv_channels=[32, 64, 128],
        conv_kernels=[3, 3, 3],
        conv_strides=[1, 1, 1],
        pool_sizes=[2, 2, 2],
        dropout_rate=0.3,
        hidden_size=128,
        num_classes=2,
        device=device
    )
    
    # Create trainer
    trainer = KeywordSpotterTrainer(config)
    
    # Run training pipeline
    results = trainer.run_full_training_pipeline(
        args.keyword_samples,
        args.background_audio,
        args.output_dir
    )
    
    # Print summary
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    print(f"Model trained on {trainer.training_stats['total_samples']} samples")
    print(f"Keyword samples: {trainer.training_stats['keyword_samples']}")
    print(f"Background samples: {trainer.training_stats['background_samples']}")
    print(f"Augmentation factor: {trainer.training_stats['augmentation_factor']}")
    print(f"\nFinal validation accuracy: {results['evaluation_metrics']['test_accuracy']:.2f}%")
    print(f"False positive rate: {results['false_positive_rate_per_hour']:.3f} per hour")
    print(f"Model saved to: {results['model_path']}")
    print(f"Mobile model saved to: {results['mobile_model_path']}")
    print("="*60)
    
    # Check if false positive rate meets target
    target_fpr = 1.0  # Target: < 1 false positive per hour
    if results['false_positive_rate_per_hour'] < target_fpr:
        print(f"✅ False positive rate target met: {results['false_positive_rate_per_hour']:.3f} < {target_fpr}")
    else:
        print(f"❌ False positive rate target not met: {results['false_positive_rate_per_hour']:.3f} >= {target_fpr}")
    
    return results['false_positive_rate_per_hour'] < target_fpr


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
