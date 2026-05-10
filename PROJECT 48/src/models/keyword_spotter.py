"""
Lightweight PyTorch CNN keyword spotter for voice-activated safety alerts.

This module implements a small CNN model optimized for on-device processing
with low latency and minimal memory footprint.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import logging
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for keyword spotter model."""
    input_features: int = 13  # MFCC features
    sequence_length: int = 50  # Time steps
    conv_channels: List[int] = (32, 64, 128)
    conv_kernels: List[int] = (3, 3, 3)
    conv_strides: List[int] = (1, 1, 1)
    pool_sizes: List[int] = (2, 2, 2)
    dropout_rate: float = 0.3
    hidden_size: int = 128
    num_classes: int = 2  # keyword vs background
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    
    @property
    def input_shape(self) -> Tuple[int, int]:
        """Input shape (features, sequence_length)."""
        return (self.input_features, self.sequence_length)


class LightweightCNN(nn.Module):
    """
    Lightweight CNN for keyword spotting.
    
    Architecture optimized for on-device processing:
    - Small number of parameters
    - Low computational complexity
    - Fast inference
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize the model.
        
        Args:
            config: Model configuration
        """
        super().__init__()
        self.config = config
        self.device = torch.device(config.device)
        
        # Build convolutional layers
        self.conv_layers = nn.ModuleList()
        self.pool_layers = nn.ModuleList()
        
        in_channels = 1  # MFCC is single channel
        
        for i, (out_channels, kernel_size, stride, pool_size) in enumerate(
            zip(config.conv_channels, config.conv_kernels, config.conv_strides, config.pool_sizes)
        ):
            # Convolutional layer
            conv = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding=1),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
                nn.Dropout2d(config.dropout_rate * 0.5)  # Reduced dropout in conv layers
            )
            self.conv_layers.append(conv)
            
            # Pooling layer
            pool = nn.MaxPool2d(pool_size)
            self.pool_layers.append(pool)
            
            in_channels = out_channels
        
        # Calculate flattened size after conv layers
        self._calculate_flattened_size()
        
        # Fully connected layers
        self.fc_layers = nn.Sequential(
            nn.Linear(self.flattened_size, config.hidden_size),
            nn.ReLU(inplace=True),
            nn.Dropout(config.dropout_rate),
            nn.Linear(config.hidden_size, config.num_classes)
        )
        
        # Initialize weights
        self._initialize_weights()
        
        # Move to device
        self.to(self.device)
        
        logger.info(f"LightweightCNN initialized with {self.count_parameters()} parameters")
    
    def _calculate_flattened_size(self):
        """Calculate the size after convolutional layers."""
        # Create dummy input to calculate size
        dummy_input = torch.randn(1, 1, *self.config.input_shape)
        
        x = dummy_input
        for conv, pool in zip(self.conv_layers, self.pool_layers):
            x = conv(x)
            x = pool(x)
        
        self.flattened_size = x.view(x.size(0), -1).size(1)
    
    def _initialize_weights(self):
        """Initialize model weights."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch_size, 1, features, sequence_length)
            
        Returns:
            Output logits of shape (batch_size, num_classes)
        """
        # Ensure input is on correct device
        x = x.to(self.device)
        
        # Convolutional layers
        for conv, pool in zip(self.conv_layers, self.pool_layers):
            x = conv(x)
            x = pool(x)
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # Fully connected layers
        x = self.fc_layers(x)
        
        return x
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """
        Make prediction with softmax output.
        
        Args:
            x: Input tensor
            
        Returns:
            Predicted probabilities
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probabilities = F.softmax(logits, dim=1)
        return probabilities
    
    def count_parameters(self) -> int:
        """Count total number of parameters."""
        return sum(p.numel() for p in self.parameters())
    
    def count_trainable_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class KeywordSpotter:
    """
    Keyword spotter with training and inference capabilities.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize keyword spotter.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self.model = LightweightCNN(config)
        self.device = torch.device(config.device)
        
        # Training state
        self.is_training = False
        self.training_history = []
        
        # Inference state
        self.detection_threshold = 0.8
        self.confidence_history = deque(maxlen=10)  # Smooth confidence values
        self.detection_cooldown = 1.0  # seconds between detections
        self.last_detection_time = 0.0
        
        logger.info(f"Keyword spotter initialized with model: {self.model.__class__.__name__}")
    
    def train(self, train_loader, val_loader, num_epochs: int = 50, learning_rate: float = 0.001) -> Dict[str, Any]:
        """
        Train the keyword spotter.
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            num_epochs: Number of training epochs
            learning_rate: Learning rate
            
        Returns:
            Training history
        """
        self.is_training = True
        self.model.train()
        
        # Optimizer and loss function
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate, weight_decay=1e-4)
        criterion = nn.CrossEntropyLoss()
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='max', factor=0.5, patience=5, verbose=True
        )
        
        # Training loop
        best_val_acc = 0.0
        training_history = {
            'train_loss': [],
            'train_acc': [],
            'val_loss': [],
            'val_acc': [],
            'epochs': []
        }
        
        logger.info(f"Starting training for {num_epochs} epochs")
        
        for epoch in range(num_epochs):
            epoch_start_time = datetime.now()
            
            # Training phase
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            
            for batch_idx, (data, target) in enumerate(train_loader):
                data, target = data.to(self.device), target.to(self.device)
                
                optimizer.zero_grad()
                output = self.model(data)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                _, predicted = torch.max(output.data, 1)
                train_total += target.size(0)
                train_correct += (predicted == target).sum().item()
            
            # Validation phase
            self.model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0
            
            with torch.no_grad():
                for data, target in val_loader:
                    data, target = data.to(self.device), target.to(self.device)
                    output = self.model(data)
                    loss = criterion(output, target)
                    val_loss += loss.item()
                    _, predicted = torch.max(output.data, 1)
                    val_total += target.size(0)
                    val_correct += (predicted == target).sum().item()
            
            # Calculate metrics
            train_loss /= len(train_loader)
            train_acc = 100. * train_correct / train_total
            val_loss /= len(val_loader)
            val_acc = 100. * val_correct / val_total
            
            # Update history
            training_history['train_loss'].append(train_loss)
            training_history['train_acc'].append(train_acc)
            training_history['val_loss'].append(val_loss)
            training_history['val_acc'].append(val_acc)
            training_history['epochs'].append(epoch + 1)
            
            # Learning rate scheduling
            scheduler.step(val_acc)
            
            # Save best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self.save_model('best_model.pth')
            
            # Log progress
            epoch_time = (datetime.now() - epoch_start_time).total_seconds()
            logger.info(
                f"Epoch {epoch+1}/{num_epochs} ({epoch_time:.1f}s) - "
                f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}% - "
                f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%"
            )
            
            self.model.train()
        
        self.is_training = False
        self.training_history = training_history
        
        logger.info(f"Training completed. Best validation accuracy: {best_val_acc:.2f}%")
        return training_history
    
    def detect_keyword(self, mfcc_features: torch.Tensor) -> Tuple[bool, float]:
        """
        Detect keyword in audio features.
        
        Args:
            mfcc_features: MFCC features tensor
            
        Returns:
            Tuple of (detected, confidence)
        """
        self.model.eval()
        
        with torch.no_grad():
            # Ensure correct input shape
            if mfcc_features.dim() == 2:
                mfcc_features = mfcc_features.unsqueeze(0)  # Add batch dimension
            if mfcc_features.dim() == 3:
                mfcc_features = mfcc_features.unsqueeze(1)  # Add channel dimension
            
            # Move to device
            mfcc_features = mfcc_features.to(self.device)
            
            # Get prediction
            probabilities = self.model.predict(mfcc_features)
            keyword_prob = probabilities[0, 1].item()  # Probability of keyword class
            
            # Smooth confidence values
            self.confidence_history.append(keyword_prob)
            if len(self.confidence_history) > 0:
                smoothed_confidence = np.mean(self.confidence_history)
            else:
                smoothed_confidence = keyword_prob
            
            # Check cooldown
            current_time = datetime.now().timestamp()
            if current_time - self.last_detection_time < self.detection_cooldown:
                return False, smoothed_confidence
            
            # Detection logic
            detected = smoothed_confidence >= self.detection_threshold
            
            if detected:
                self.last_detection_time = current_time
                logger.info(f"Keyword detected with confidence: {smoothed_confidence:.3f}")
            
            return detected, smoothed_confidence
    
    def set_detection_threshold(self, threshold: float):
        """
        Set detection threshold.
        
        Args:
            threshold: Detection threshold (0.0 to 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        self.detection_threshold = threshold
        logger.info(f"Detection threshold set to: {threshold}")
    
    def set_detection_cooldown(self, cooldown: float):
        """
        Set detection cooldown period.
        
        Args:
            cooldown: Cooldown period in seconds
        """
        self.detection_cooldown = max(0.0, cooldown)
        logger.info(f"Detection cooldown set to: {cooldown}s")
    
    def evaluate(self, test_loader) -> Dict[str, float]:
        """
        Evaluate model on test set.
        
        Args:
            test_loader: Test data loader
            
        Returns:
            Evaluation metrics
        """
        self.model.eval()
        
        test_loss = 0.0
        correct = 0
        total = 0
        all_predictions = []
        all_targets = []
        
        criterion = nn.CrossEntropyLoss()
        
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data.to(self.device), target.to(self.device)
                
                output = self.model(data)
                loss = criterion(output, target)
                test_loss += loss.item()
                
                _, predicted = torch.max(output.data, 1)
                total += target.size(0)
                correct += (predicted == target).sum().item()
                
                # Store for additional metrics
                probabilities = F.softmax(output, dim=1)
                all_predictions.extend(probabilities.cpu().numpy())
                all_targets.extend(target.cpu().numpy())
        
        # Calculate metrics
        test_loss /= len(test_loader)
        test_acc = 100. * correct / total
        
        # Calculate additional metrics
        all_predictions = np.array(all_predictions)
        all_targets = np.array(all_targets)
        
        # False positive rate (for background class)
        background_mask = all_targets == 0
        if np.any(background_mask):
            fpr = np.mean(all_predictions[background_mask, 1] >= self.detection_threshold)
        else:
            fpr = 0.0
        
        # True positive rate (for keyword class)
        keyword_mask = all_targets == 1
        if np.any(keyword_mask):
            tpr = np.mean(all_predictions[keyword_mask, 1] >= self.detection_threshold)
        else:
            tpr = 0.0
        
        metrics = {
            'test_loss': test_loss,
            'test_accuracy': test_acc,
            'false_positive_rate': fpr,
            'true_positive_rate': tpr,
            'detection_threshold': self.detection_threshold
        }
        
        logger.info(f"Test results - Loss: {test_loss:.4f}, Acc: {test_acc:.2f}%, "
                   f"FPR: {fpr:.3f}, TPR: {tpr:.3f}")
        
        return metrics
    
    def save_model(self, filepath: str):
        """
        Save model state.
        
        Args:
            filepath: Path to save model
        """
        model_state = {
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'detection_threshold': self.detection_threshold,
            'training_history': self.training_history,
            'timestamp': datetime.now().isoformat()
        }
        
        torch.save(model_state, filepath)
        logger.info(f"Model saved to: {filepath}")
    
    def load_model(self, filepath: str):
        """
        Load model state.
        
        Args:
            filepath: Path to load model from
        """
        model_state = torch.load(filepath, map_location=self.device)
        
        self.model.load_state_dict(model_state['model_state_dict'])
        self.detection_threshold = model_state.get('detection_threshold', 0.8)
        self.training_history = model_state.get('training_history', [])
        
        logger.info(f"Model loaded from: {filepath}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information.
        
        Returns:
            Model information dictionary
        """
        return {
            'model_type': 'LightweightCNN',
            'parameters': {
                'total': self.model.count_parameters(),
                'trainable': self.model.count_trainable_parameters()
            },
            'input_shape': self.config.input_shape,
            'output_classes': self.config.num_classes,
            'detection_threshold': self.detection_threshold,
            'device': str(self.device),
            'config': {
                'conv_channels': self.config.conv_channels,
                'hidden_size': self.config.hidden_size,
                'dropout_rate': self.config.dropout_rate
            }
        }
    
    def export_for_mobile(self, filepath: str):
        """
        Export model for mobile deployment.
        
        Args:
            filepath: Path to save mobile model
        """
        try:
            # Create dummy input for tracing
            dummy_input = torch.randn(1, 1, *self.config.input_shape).to(self.device)
            
            # Trace the model
            traced_model = torch.jit.trace(self.model, dummy_input)
            
            # Save traced model
            traced_model.save(filepath)
            
            logger.info(f"Mobile model exported to: {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting mobile model: {e}")
            raise
    
    def __del__(self):
        """Cleanup when spotter is destroyed."""
        if hasattr(self, 'model'):
            del self.model


def create_dataset_from_features(features_list: List[torch.Tensor], 
                               labels: List[int]) -> torch.utils.data.TensorDataset:
    """
    Create PyTorch dataset from features and labels.
    
    Args:
        features_list: List of MFCC features
        labels: List of corresponding labels
        
    Returns:
        PyTorch dataset
    """
    # Ensure all features have the same shape
    max_length = max(feat.shape[1] for feat in features_list)
    
    # Pad or truncate features
    padded_features = []
    for feat in features_list:
        if feat.shape[1] < max_length:
            # Pad with zeros
            padding = torch.zeros(feat.shape[0], max_length - feat.shape[1])
            padded_feat = torch.cat([feat, padding], dim=1)
        else:
            # Truncate
            padded_feat = feat[:, :max_length]
        
        padded_features.append(padded_feat)
    
    # Stack features and convert labels
    features_tensor = torch.stack(padded_features)
    labels_tensor = torch.tensor(labels, dtype=torch.long)
    
    return torch.utils.data.TensorDataset(features_tensor, labels_tensor)


def calculate_model_size(model: nn.Module) -> Dict[str, float]:
    """
    Calculate model size in different units.
    
    Args:
        model: PyTorch model
        
    Returns:
        Size information dictionary
    """
    param_size = 0
    buffer_size = 0
    
    for param in model.parameters():
        param_size += param.nelement() * param.element_size()
    
    for buffer in model.buffers():
        buffer_size += buffer.nelement() * buffer.element_size()
    
    size_all = param_size + buffer_size
    
    return {
        'parameters_mb': param_size / (1024 ** 2),
        'buffers_mb': buffer_size / (1024 ** 2),
        'total_mb': size_all / (1024 ** 2),
        'parameters': sum(p.numel() for p in model.parameters()),
        'buffers': sum(b.nelement() for b in model.buffers())
    }


def benchmark_inference(model: nn.Module, input_shape: Tuple[int, int], 
                      num_runs: int = 100) -> Dict[str, float]:
    """
    Benchmark model inference speed.
    
    Args:
        model: PyTorch model
        input_shape: Input shape (features, sequence_length)
        num_runs: Number of benchmark runs
        
    Returns:
        Benchmark results
    """
    import time
    
    model.eval()
    device = next(model.parameters()).device
    
    # Create dummy input
    dummy_input = torch.randn(1, 1, *input_shape).to(device)
    
    # Warmup
    for _ in range(10):
        with torch.no_grad():
            _ = model(dummy_input)
    
    # Benchmark
    times = []
    for _ in range(num_runs):
        start_time = time.time()
        with torch.no_grad():
            _ = model(dummy_input)
        end_time = time.time()
        times.append(end_time - start_time)
    
    return {
        'mean_time_ms': np.mean(times) * 1000,
        'std_time_ms': np.std(times) * 1000,
        'min_time_ms': np.min(times) * 1000,
        'max_time_ms': np.max(times) * 1000,
        'fps': 1.0 / np.mean(times)
    }
