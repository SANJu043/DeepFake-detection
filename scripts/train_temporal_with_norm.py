import sys
import time
from pathlib import Path
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.datasets.loaders import create_sequence_loaders
from ml.models.temporal_bigru import TemporalBiGRU

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Training TemporalBiGRU on: {device}")

WEIGHTS_DIR = ROOT / "weights"
CHECKPOINTS_DIR = ROOT / "checkpoints"

loaders = create_sequence_loaders(ROOT / "data" / "features", batch_size=16, num_workers=0)
train_loader = loaders["train"]
val_loader = loaders["val"]

epochs = 25
model = TemporalBiGRU(input_size=1792, hidden_size=128, num_layers=1, dropout=0.35).to(device)
optimizer = AdamW(model.parameters(), lr=0.0005, weight_decay=3e-3)
scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
criterion = nn.BCELoss()

best_val_loss = float("inf")
best_weights = None

for epoch in range(1, epochs + 1):
    t0 = time.time()
    model.train()
    train_loss, train_corr, train_tot = 0.0, 0, 0
    for x, y, lengths in train_loader:
        x, y, lengths = x.to(device), y.float().to(device), lengths.to(device)
        optimizer.zero_grad()
        preds = model(x, lengths)
        loss = criterion(preds, y)
        loss.backward()
        optimizer.step()

        train_loss += loss.item() * len(y)
        train_corr += ((preds > 0.5) == y).sum().item()
        train_tot += len(y)
    scheduler.step()

    model.eval()
    val_loss, val_corr, val_tot = 0.0, 0, 0
    with torch.no_grad():
        for x, y, lengths in val_loader:
            x, y, lengths = x.to(device), y.float().to(device), lengths.to(device)
            preds = model(x, lengths)
            loss = criterion(preds, y)
            val_loss += loss.item() * len(y)
            val_corr += ((preds > 0.5) == y).sum().item()
            val_tot += len(y)

    elapsed = time.time() - t0
    tr_l, tr_a = train_loss / max(train_tot, 1), train_corr / max(train_tot, 1)
    v_l, v_a = val_loss / max(val_tot, 1), val_corr / max(val_tot, 1)
    print(f"Epoch {epoch:2d}/{epochs} | Train loss: {tr_l:.4f} acc: {tr_a:.4f} | Val loss: {v_l:.4f} acc: {v_a:.4f} | {elapsed:.2f}s")

    if v_l < best_val_loss:
        best_val_loss = v_l
        best_weights = model.state_dict().copy()

torch.save(best_weights or model.state_dict(), WEIGHTS_DIR / "temporal.pt")
torch.save(best_weights or model.state_dict(), CHECKPOINTS_DIR / "temporal_bigru_best.pt")
print(f"Saved TemporalBiGRU to weights/temporal.pt & checkpoints/temporal_bigru_best.pt (Val loss: {best_val_loss:.4f})")

