"""Command-line entry point for the chronological expense-model training pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.train import train
train()
