"""
Lightweight CNN Keyword Spotter for Vaultryn Voice-Activated Safety System
Implements on-device keyword detection with privacy-first design
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchaudio
import numpy as np
import asyncio
import logging
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path
import json
import time
from collections import deque

from audio_processing import AudioConfig, MFCCProcessor

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for keyword spotter model"""
    input_channels: int = 1  # MFCC features
    n_mfcc: int = 40  # Number of MFCC coefficients
    conv_filters: List[int] = None  # CNN filter sizes
    conv_kernels: List[int] = None  # CNN kernel sizes
    pool_sizes: List[int] = None  # Pooling sizes
    fc_layers: List[int] = None  # Fully connected layer sizes
    dropout_rate: float = 0.3
    confidence_threshold: float = 0.98  # Threshold for keyword detection
    
    def __post_init__(self):
        if self.conv_filters is None:
            self.conv_filters = [16, 32, 64]
        if self.conv_kernels is None:
            self.conv_kernels = [3, 3, 3]
        if self.pool_sizes is None:
            self.pool_sizes = [2, 2, 2]
        if self.fc_layers is None:
            self.fc_layers = [128, 64]


class KeywordSpotter(nn.Module):
    """
    Lightweight CNN for keyword spotting
    Optimized for on-device inference with low latency and memory footprint
    """
    
    def __init__(self, config: ModelConfig):
        super(KeywordSpotter, self).__init__()
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Build CNN layers
        self.conv_layers = self._build_conv_layers()
        
        # Calculate flattened size after conv layers
        self._calculate_conv_output_size()
        
        # Build fully connected layers
        self.fc_layers = self._build_fc_layers()
        
        # Output layer (binary classification: keyword vs background)
        self.output_layer = nn.Linear(self.fc_layers[-1].out_features, 2)
        
        # Dropout for regularization
        self.dropout = nn.Dropout(config.dropout_rate)
        
        # Move to device
        self.to(self.device)
        
        logger.info(f"KeywordSpotter initialized on {self.device}")
    
    def _build_conv_layers(self) -> nn.ModuleList:
        """Build convolutional layers"""
        layers = nn.ModuleList()
        
        in_channels = self.config.input_channels
        
        for i, (filters, kernel, pool) in enumerate(zip(
            self.config.conv_filters,
            self.config.conv_kernels,
            self.config.pool_sizes
        )):
            layers.extend([
                nn.Conv2d(in_channels, filters, kernel_size=kernel, padding=1),
                nn.BatchNorm2d(filters),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(pool)
            ])
            in_channels = filters
        
        return layers
    
    def _build_fc_layers(self) -> nn.ModuleList:
        """Build fully connected layers"""
        layers = nn.ModuleList()
        
        for i, size in enumerate(self.config.fc_layers):
            if i == 0:
                layers.extend([
                    nn.Linear(self.conv_output_size, size),
                    nn.ReLU(inplace=True),
                    self.dropout
                ])
            else:
                layers.extend([
                    nn.Linear(self.fc_layers[i-1].out_features, size),
                    nn.ReLU(inplace=True),
                    self.dropout
                ])
        
        return layers
    
    def _calculate_conv_output_size(self):
        """Calculate the output size after convolutional layers"""
        # Create dummy input to calculate output size
        dummy_input = torch.randn(1, 1, self.config.n_mfcc, 31)  # Typical MFCC shape
        with torch.no_grad():
            x = dummy_input
            for layer in self.conv_layers:
                x = layer(x)
            self.conv_output_size = x.numel()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the network
        
        Args:
            x: Input tensor of shape [batch, channels, mfcc, time]
            
        Returns:
            Output logits of shape [batch, 2]
        """
        # Ensure input is on correct device
        x = x.to(self.device)
        
        # Pass through conv layers
        for layer in self.conv_layers:
            x = layer(x)
        
        # Flatten for fully connected layers
        x = x.view(x.size(0), -1)
        
        # Pass through fully connected layers
        for layer in self.fc_layers:
            x = layer(x)
        
        # Output layer
        x = self.output_layer(x)
        
        return x
    
    def predict(self, x: torch.Tensor) -> Tuple[int, float]:
        """
        Make prediction with confidence score
        
        Args:
            x: Input tensor
            
        Returns:
            Tuple of (predicted_class, confidence)
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probabilities = F.softmax(logits, dim=1)
            confidence, predicted_class = torch.max(probabilities, dim=1)
            
            return predicted_class.item(), confidence.item()
    
    def get_model_info(self) -> Dict:
        """Get model information for debugging"""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'model_size_mb': total_params * 4 / (1024 * 1024),  # Assuming float32
            'device': str(self.device),
            'config': self.config.__dict__
        }


class KeywordTrainer:
    """
    Training pipeline for keyword spotter
    Handles data loading, training, and validation
    """
    
    def __init__(self, model: KeywordSpotter, config: AudioConfig):
        self.model = model
        self.config = config
        self.device = model.device
        
        # Training hyperparameters
        self.learning_rate = 0.001
        self.batch_size = 32
        self.epochs = 50
        self.patience = 10  # Early stopping patience
        
        # Optimizer and loss
        self.optimizer = optim.Adam(model.parameters(), lr=self.learning_rate)
        self.criterion = nn.CrossEntropyLoss()
        
        # Training history
        self.train_losses = []
        self.val_losses = []
        self.val_accuracies = []
        
        logger.info("KeywordTrainer initialized")
    
    def prepare_dummy_dataset(self, num_positive: int = 1000, num_negative: int = 5000):
        """
        Create dummy dataset for demonstration
        In production, this would load real audio data
        
        Args:
            num_positive: Number of positive examples (keyword)
            num_negative: Number of negative examples (background)
        """
        from audio_processing import create_test_audio, MFCCProcessor
        
        processor = MFCCProcessor(self.config)
        
        # Create positive examples (keyword "help")
        positive_data = []
        for i in range(num_positive):
            # Create test audio with different characteristics
            audio = create_test_audio(duration_ms=500)
            features = processor.preprocess_audio_chunk(audio)
            positive_data.append((features, 1))  # Label 1 for keyword
        
        # Create negative examples (background noise)
        negative_data = []
        for i in range(num_negative):
            # Create different types of background audio
            duration = np.random.randint(300, 700)  # Variable duration
            audio = create_test_audio(duration_ms=duration)
            features = processor.preprocess_audio_chunk(audio)
            negative_data.append((features, 0))  # Label 0 for background
        
        # Combine and shuffle
        all_data = positive_data + negative_data
        np.random.shuffle(all_data)
        
        # Split into train/val
        split_idx = int(0.8 * len(all_data))
        train_data = all_data[:split_idx]
        val_data = all_data[split_idx:]
        
        return train_data, val_data
    
    def train_epoch(self, train_data: List[Tuple[torch.Tensor, int]]) -> float:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        # Create batches
        for i in range(0, len(train_data), self.batch_size):
            batch = train_data[i:i + self.batch_size]
            
            if len(batch) < self.batch_size:
                continue  # Skip incomplete batches
            
            # Prepare batch data
            features = torch.stack([item[0] for item in batch])
            labels = torch.tensor([item[1] for item in batch])
            
            features = features.to(self.device)
            labels = labels.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            outputs = self.model(features)
            loss = self.criterion(outputs, labels)
            
            # Backward pass
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        return total_loss / num_batches if num_batches > 0 else 0.0
    
    def validate(self, val_data: List[Tuple[torch.Tensor, int]]) -> Tuple[float, float]:
        """Validate model performance"""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for features, label in val_data:
                features = features.to(self.device)
                label = torch.tensor(label).to(self.device)
                
                # Forward pass
                outputs = self.model(features.unsqueeze(0))
                loss = self.criterion(outputs, label.unsqueeze(0))
                
                total_loss += loss.item()
                
                # Calculate accuracy
                _, predicted = torch.max(outputs, 1)
                total += 1
                correct += (predicted == label).item()
        
        avg_loss = total_loss / len(val_data)
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    def train(self, train_data: List[Tuple[torch.Tensor, int]], 
              val_data: List[Tuple[torch.Tensor, int]]) -> Dict:
        """
        Train the keyword spotter model
        
        Args:
            train_data: Training dataset
            val_data: Validation dataset
            
        Returns:
            Training history and metrics
        """
        logger.info(f"Starting training for {self.epochs} epochs")
        
        best_val_acc = 0.0
        patience_counter = 0
        
        for epoch in range(self.epochs):
            # Train
            train_loss = self.train_epoch(train_data)
            self.train_losses.append(train_loss)
            
            # Validate
            val_loss, val_acc = self.validate(val_data)
            self.val_losses.append(val_loss)
            self.val_accuracies.append(val_acc)
            
            logger.info(f"Epoch {epoch+1}/{self.epochs}: "
                       f"Train Loss: {train_loss:.4f}, "
                       f"Val Loss: {val_loss:.4f}, "
                       f"Val Acc: {val_acc:.4f}")
            
            # Early stopping
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_counter = 0
                # Save best model
                torch.save(self.model.state_dict(), 'best_keyword_spotter.pth')
                logger.info(f"New best model saved with accuracy: {val_acc:.4f}")
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
        
        # Load best model
        self.model.load_state_dict(torch.load('best_keyword_spotter.pth'))
        
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'val_accuracies': self.val_accuracies,
            'best_accuracy': best_val_acc,
            'epochs_trained': epoch + 1
        }


class KeywordDetector:
    """
    Real-time keyword detection system
    Handles inference, confidence tracking, and alert triggering
    """
    
    def __init__(self, model: KeywordSpotter, config: AudioConfig):
        self.model = model
        self.config = config
        self.device = model.device
        
        # Detection parameters
        self.confidence_threshold = config.target_confidence
        self.detection_cooldown = 2.0  # Seconds between detections
        self.smoothing_window = 5  # Number of recent predictions to smooth
        
        # State tracking
        self.last_detection_time = 0.0
        self.prediction_history = deque(maxlen=self.smoothing_window)
        self.detection_count = 0
        
        # Performance metrics
        self.total_predictions = 0
        self.false_positive_count = 0
        self.true_positive_count = 0
        
        logger.info("KeywordDetector initialized")
    
    def detect_keyword(self, features: torch.Tensor) -> Optional[Dict]:
        """
        Detect keyword in audio features
        
        Args:
            features: MFCC features tensor
            
        Returns:
            Detection result or None if no keyword detected
        """
        try:
            current_time = time.time()
            
            # Check cooldown
            if current_time - self.last_detection_time < self.detection_cooldown:
                return None
            
            # Make prediction
            predicted_class, confidence = self.model.predict(features)
            self.total_predictions += 1
            
            # Add to history for smoothing
            self.prediction_history.append({
                'class': predicted_class,
                'confidence': confidence,
                'timestamp': current_time
            })
            
            # Check if keyword detected with sufficient confidence
            if predicted_class == 1 and confidence >= self.confidence_threshold:
                # Additional smoothing check
                if self._is_confirmed_detection():
                    self.last_detection_time = current_time
                    self.detection_count += 1
                    
                    result = {
                        'detected': True,
                        'confidence': confidence,
                        'timestamp': current_time,
                        'detection_id': self.detection_count,
                        'smoothed_confidence': self._get_smoothed_confidence()
                    }
                    
                    logger.info(f"Keyword detected: {result}")
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error in keyword detection: {e}")
            return None
    
    def _is_confirmed_detection(self) -> bool:
        """
        Apply smoothing to reduce false positives
        
        Returns:
            True if detection is confirmed by recent predictions
        """
        if len(self.prediction_history) < self.smoothing_window:
            return False
        
        # Check if recent predictions support keyword detection
        recent_predictions = list(self.prediction_history)[-self.smoothing_window:]
        keyword_votes = sum(1 for p in recent_predictions if p['class'] == 1)
        avg_confidence = sum(p['confidence'] for p in recent_predictions) / len(recent_predictions)
        
        # Require majority vote and minimum average confidence
        return keyword_votes >= 3 and avg_confidence >= 0.9
    
    def _get_smoothed_confidence(self) -> float:
        """Get smoothed confidence from recent predictions"""
        if not self.prediction_history:
            return 0.0
        
        recent_predictions = list(self.prediction_history)[-3:]
        return sum(p['confidence'] for p in recent_predictions) / len(recent_predictions)
    
    def get_detection_stats(self) -> Dict:
        """Get detection statistics"""
        return {
            'total_predictions': self.total_predictions,
            'detection_count': self.detection_count,
            'false_positive_rate': self.false_positive_count / max(self.total_predictions, 1),
            'detection_rate': self.detection_count / max(self.total_predictions, 1),
            'last_detection_time': self.last_detection_time,
            'confidence_threshold': self.confidence_threshold
        }
    
    def reset_stats(self):
        """Reset detection statistics"""
        self.total_predictions = 0
        self.false_positive_count = 0
        self.true_positive_count = 0
        self.detection_count = 0
        self.last_detection_time = 0.0
        self.prediction_history.clear()
        
        logger.info("Detection statistics reset")
    
    def set_confidence_threshold(self, threshold: float):
        """Update confidence threshold"""
        self.confidence_threshold = max(0.5, min(1.0, threshold))
        logger.info(f"Confidence threshold updated to {self.confidence_threshold}")


class ModelManager:
    """
    Model management utilities
    Handles saving, loading, and quantization for deployment
    """
    
    @staticmethod
    def save_model(model: KeywordSpotter, filepath: str):
        """Save model with metadata"""
        try:
            # Create model directory
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Save model state and config
            torch.save({
                'model_state_dict': model.state_dict(),
                'model_config': model.config.__dict__,
                'model_info': model.get_model_info()
            }, filepath)
            
            logger.info(f"Model saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise
    
    @staticmethod
    def load_model(filepath: str, device: Optional[str] = None) -> KeywordSpotter:
        """Load model from file"""
        try:
            if device is None:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            # Load checkpoint
            checkpoint = torch.load(filepath, map_location=device)
            
            # Recreate model
            config = ModelConfig(**checkpoint['model_config'])
            model = KeywordSpotter(config)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.to(device)
            
            logger.info(f"Model loaded from {filepath}")
            return model
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    @staticmethod
    def quantize_model(model: KeywordSpotter, calibration_data: List[torch.Tensor]) -> KeywordSpotter:
        """
        Quantize model for on-device deployment
        
        Args:
            model: Trained model
            calibration_data: Sample data for calibration
            
        Returns:
            Quantized model
        """
        try:
            # Prepare model for quantization
            model.eval()
            model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
            torch.quantization.prepare(model, inplace=True)
            
            # Calibrate with sample data
            with torch.no_grad():
                for data in calibration_data:
                    model(data)
            
            # Convert to quantized model
            quantized_model = torch.quantization.convert(model, inplace=False)
            
            logger.info("Model quantized successfully")
            return quantized_model
            
        except Exception as e:
            logger.error(f"Error quantizing model: {e}")
            return model  # Return original model if quantization fails
    
    @staticmethod
    def export_torchscript(model: KeywordSpotter, sample_input: torch.Tensor, filepath: str):
        """
        Export model to TorchScript for mobile deployment
        
        Args:
            model: Trained model
            sample_input: Sample input for tracing
            filepath: Output file path
        """
        try:
            # Create model directory
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Export to TorchScript
            model.eval()
            traced_model = torch.jit.trace(model, sample_input)
            traced_model.save(filepath)
            
            logger.info(f"Model exported to TorchScript: {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting to TorchScript: {e}")
            raise


if __name__ == "__main__":
    # Test keyword spotter
    import asyncio
    
    async def test_keyword_spotter():
        """Test keyword spotter model"""
        # Initialize configurations
        audio_config = AudioConfig()
        model_config = ModelConfig()
        
        # Create model
        model = KeywordSpotter(model_config)
        
        # Print model info
        info = model.get_model_info()
        print(f"Model Info: {info}")
        
        # Create dummy data for testing
        from audio_processing import create_test_audio, MFCCProcessor
        processor = MFCCProcessor(audio_config)
        
        test_audio = create_test_audio()
        features = processor.preprocess_audio_chunk(test_audio)
        
        # Test prediction
        predicted_class, confidence = model.predict(features)
        print(f"Prediction: Class={predicted_class}, Confidence={confidence:.4f}")
        
        # Test detector
        detector = KeywordDetector(model, audio_config)
        result = detector.detect_keyword(features)
        print(f"Detection result: {result}")
        
        print("Keyword spotter test completed successfully")
    
    asyncio.run(test_keyword_spotter())
