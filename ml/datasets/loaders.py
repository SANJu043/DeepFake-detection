"""
Dataset loaders for deepfake detection.

Supports:
- FaceForensics++ (FF++)
- Celeb-DF (v2)
- DFDC (DeepFake Detection Challenge)
- Generic folder-based datasets

Each loader returns face-cropped frame tensors and binary labels (0=real, 1=fake).
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms


# ---------------------------------------------------------------------------
# Frame-level dataset (for spatial & frequency models)
# ---------------------------------------------------------------------------

class FrameDataset(Dataset):
    """
    Dataset of individual face-crop frames with binary labels.

    Directory structure:
        data_root/
        ├── real/
        │   ├── video001/
        │   │   ├── frame_000.jpg
        │   │   ├── frame_001.jpg
        │   │   └── ...
        │   └── ...
        └── fake/
            ├── video100/
            │   ├── frame_000.jpg
            │   └── ...
            └── ...
    """

    def __init__(
        self,
        data_root: str | Path,
        transform: Optional[Callable] = None,
        max_frames_per_video: int = 30,
        split: str = "train",
    ) -> None:
        self.data_root = Path(data_root)
        self.transform = transform or get_default_transform(split)
        self.max_frames_per_video = max_frames_per_video

        self.samples: List[Tuple[Path, int]] = []
        self._scan_directory()

    def _scan_directory(self) -> None:
        """Scan the data root for frame images."""
        for label_name, label in [("real", 0), ("fake", 1)]:
            label_dir = self.data_root / label_name
            if not label_dir.exists():
                continue

            for video_dir in sorted(label_dir.iterdir()):
                if not video_dir.is_dir():
                    continue

                frames = sorted(video_dir.glob("*.jpg")) + sorted(video_dir.glob("*.png"))
                # Subsample if too many frames
                if len(frames) > self.max_frames_per_video:
                    step = len(frames) // self.max_frames_per_video
                    frames = frames[::step][: self.max_frames_per_video]

                for frame_path in frames:
                    self.samples.append((frame_path, label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        path, label = self.samples[idx]
        img = cv2.imread(str(path))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.transform:
            img = self.transform(img)

        return img, label


# ---------------------------------------------------------------------------
# Sequence dataset (for temporal model)
# ---------------------------------------------------------------------------

class SequenceDataset(Dataset):
    """
    Dataset of frame sequences from videos with binary labels.

    Each sample is a sequence of face-crop features (pre-extracted)
    for one video, used to train the temporal BiGRU model.

    Directory structure:
        features_root/
        ├── real/
        │   ├── video001.pt   # tensor of shape (T, D)
        │   └── ...
        └── fake/
            ├── video100.pt
            └── ...
    """

    def __init__(
        self,
        features_root: str | Path,
        max_seq_len: int = 300,
    ) -> None:
        self.features_root = Path(features_root)
        self.max_seq_len = max_seq_len
        self.samples: List[Tuple[Path, int]] = []
        self._scan_directory()

    def _scan_directory(self) -> None:
        for label_name, label in [("real", 0), ("fake", 1)]:
            label_dir = self.features_root / label_name
            if not label_dir.exists():
                continue
            for feat_path in sorted(label_dir.glob("*.pt")):
                self.samples.append((feat_path, label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, int]:
        """Returns (features, label, actual_length)."""
        path, label = self.samples[idx]
        features = torch.load(path, map_location="cpu")  # (T, D)

        actual_len = min(features.shape[0], self.max_seq_len)
        if features.shape[0] > self.max_seq_len:
            # Uniform subsample
            indices = torch.linspace(0, features.shape[0] - 1, self.max_seq_len).long()
            features = features[indices]
            actual_len = self.max_seq_len

        return features, label, actual_len


def collate_sequences(
    batch: List[Tuple[torch.Tensor, int, int]],
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Collate variable-length sequences with zero-padding."""
    features_list, labels, lengths = zip(*batch)
    max_len = max(f.shape[0] for f in features_list)
    dim = features_list[0].shape[1]

    padded = torch.zeros(len(features_list), max_len, dim)
    for i, f in enumerate(features_list):
        padded[i, : f.shape[0], :] = f

    return padded, torch.tensor(labels, dtype=torch.long), torch.tensor(lengths, dtype=torch.long)


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def get_default_transform(split: str = "train") -> transforms.Compose:
    """Standard transform for 380×380 face crops."""
    if split == "train":
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
            transforms.Resize((380, 380)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((380, 380)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])


# ---------------------------------------------------------------------------
# DataLoader factories
# ---------------------------------------------------------------------------

def create_frame_loaders(
    data_root: str | Path,
    batch_size: int = 32,
    num_workers: int = 4,
    max_frames_per_video: int = 30,
) -> Dict[str, DataLoader]:
    """Create train/val/test DataLoaders for frame-level training."""
    loaders = {}
    for split in ["train", "val", "test"]:
        split_dir = Path(data_root) / split
        if not split_dir.exists():
            continue
        ds = FrameDataset(
            data_root=split_dir,
            max_frames_per_video=max_frames_per_video,
            split=split,
        )
        loaders[split] = DataLoader(
            ds,
            batch_size=batch_size,
            shuffle=(split == "train"),
            num_workers=num_workers,
            pin_memory=True,
            drop_last=(split == "train"),
        )
    return loaders


def create_sequence_loaders(
    features_root: str | Path,
    batch_size: int = 16,
    num_workers: int = 2,
    max_seq_len: int = 300,
) -> Dict[str, DataLoader]:
    """Create train/val/test DataLoaders for sequence-level training."""
    loaders = {}
    for split in ["train", "val", "test"]:
        split_dir = Path(features_root) / split
        if not split_dir.exists():
            continue
        ds = SequenceDataset(
            features_root=split_dir,
            max_seq_len=max_seq_len,
        )
        loaders[split] = DataLoader(
            ds,
            batch_size=batch_size,
            shuffle=(split == "train"),
            num_workers=num_workers,
            pin_memory=True,
            collate_fn=collate_sequences,
        )
    return loaders
