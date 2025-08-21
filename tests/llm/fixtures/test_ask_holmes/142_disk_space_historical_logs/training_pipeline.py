#!/usr/bin/env python3
import os
import pickle
import numpy as np
from datetime import datetime, timedelta

# Directory for model checkpoints and temporary files
CHECKPOINT_DIR = "/var/log/aggregated/checkpoints"
TEMP_DIR = "/var/log/aggregated/temp"
DEBUG_MODE = (
    os.environ.get("DEBUG_MODE", "true").lower() == "true"
)  # Left on from debugging session!


def ensure_dirs():
    """Create necessary directories."""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def simulate_model_data():
    """Create a fake ML model state."""
    return {
        "weights": np.random.rand(1000, 1000),  # ~8MB per checkpoint
        "optimizer_state": np.random.rand(1000, 1000),
        "training_history": list(range(10000)),
        "config": {"learning_rate": 0.001, "batch_size": 32},
    }


def save_checkpoint(epoch, timestamp):
    """Save model checkpoint - problem: no cleanup of old checkpoints!"""
    checkpoint_path = os.path.join(
        CHECKPOINT_DIR, f"model_epoch_{epoch}_{timestamp.strftime('%Y%m%d_%H%M%S')}.pkl"
    )

    # In debug mode, also save auxiliary files
    if DEBUG_MODE:
        # Save full model state
        with open(checkpoint_path, "wb") as f:
            pickle.dump(simulate_model_data(), f)

        # Save gradients for debugging (another 8MB)
        grad_path = checkpoint_path.replace(".pkl", "_gradients.pkl")
        with open(grad_path, "wb") as f:
            pickle.dump(np.random.rand(1000, 1000), f)

        # Save activation maps (another 8MB)
        activation_path = checkpoint_path.replace(".pkl", "_activations.pkl")
        with open(activation_path, "wb") as f:
            pickle.dump(np.random.rand(1000, 1000), f)
    else:
        with open(checkpoint_path, "wb") as f:
            pickle.dump(simulate_model_data(), f)


def process_batch_data(timestamp, batch_num):
    """Process data batches and create temporary files."""
    # Common pattern: creating temp files for batch processing
    temp_file = os.path.join(
        TEMP_DIR, f"batch_{batch_num}_{timestamp.strftime('%Y%m%d_%H%M%S')}.tmp"
    )

    # Simulate preprocessing large batches
    with open(temp_file, "wb") as f:
        # Write preprocessed data (10MB per batch)
        f.write(b"x" * (10 * 1024 * 1024))

    # Bug: Exception handling doesn't clean up temp files
    try:
        # Process batch - sometimes fails on corrupted data
        if batch_num % 50 == 0:
            # Simulate common preprocessing errors
            raise ValueError(
                "Invalid shape for input tensor: expected (224, 224, 3), got (224, 224)"
            )
    except ValueError as e:
        # Log error but forgot to clean up temp file!
        print(
            f"{timestamp.isoformat()}Z ERROR: Batch {batch_num} preprocessing failed: {str(e)}"
        )
        pass
    except Exception as e:
        # Generic error handling, also forgets cleanup
        print(
            f"{timestamp.isoformat()}Z ERROR: Unexpected error processing batch {batch_num}: {str(e)}"
        )
        pass
    else:
        # Only removes on success
        os.remove(temp_file)


def run_ml_pipeline():
    """Main ML pipeline with disk space issues."""
    ensure_dirs()

    # Start 48 hours ago
    current_time = datetime.utcnow() - timedelta(hours=48)

    print(f"{current_time.isoformat()}Z INFO: ML Pipeline v1.2.3 started")
    print(f"{current_time.isoformat()}Z INFO: Loading dataset...")
    print(f"{current_time.isoformat()}Z INFO: Initializing model architecture")
    print(f"{current_time.isoformat()}Z INFO: Starting training run...")

    epoch = 0
    batch_num = 0

    # Phase 1: Normal operation (48-47 hours ago)
    for i in range(20):
        if i % 5 == 0:
            save_checkpoint(epoch, current_time)
            epoch += 1
            print(
                f"{current_time.isoformat()}Z INFO: Epoch {epoch} completed, loss: {0.15 - epoch * 0.01:.4f}, accuracy: {0.75 + epoch * 0.02:.3f}"
            )

        # Process some batches
        for j in range(10):
            process_batch_data(current_time, batch_num)
            batch_num += 1

        current_time += timedelta(minutes=3)

    # Continue training
    current_time = datetime.utcnow() - timedelta(hours=47)
    print(f"{current_time.isoformat()}Z INFO: Epoch 4 completed, loss: 0.0823")
    print(f"{current_time.isoformat()}Z INFO: Starting epoch 5")

    # Phase 2: Increased training activity (47-46 hours ago)
    for i in range(40):
        if i % 3 == 0:  # More frequent checkpoints
            save_checkpoint(epoch, current_time)
            epoch += 1

        # More batch processing
        for j in range(20):
            process_batch_data(current_time, batch_num)
            batch_num += 1

        current_time += timedelta(minutes=1.5)

    # Phase 3: Errors start appearing (46-45 hours ago)
    current_time = datetime.utcnow() - timedelta(hours=46)
    print(f"{current_time.isoformat()}Z INFO: Epoch 17 completed, loss: 0.0412")
    print(
        f"{current_time.isoformat()}Z ERROR: Failed to save checkpoint: [Errno 28] No space left on device"
    )
    print(
        f"{current_time.isoformat()}Z ERROR: Cannot create new temporary file for batch processing"
    )

    # Phase 4: Disk full (45 hours ago)
    current_time = datetime.utcnow() - timedelta(hours=45)
    print(
        f"{current_time.isoformat()}Z ERROR: OSError: [Errno 28] No space left on device"
    )
    print(f"{current_time.isoformat()}Z ERROR: Traceback (most recent call last):")
    print(
        f"{current_time.isoformat()}Z ERROR:   File '/app/pipeline.py', line 127, in save_checkpoint"
    )
    print(f"{current_time.isoformat()}Z ERROR:     pickle.dump(model_state, f)")
    print(
        f"{current_time.isoformat()}Z ERROR: OSError: [Errno 28] No space left on device"
    )
    print(
        f"{current_time.isoformat()}Z FATAL: Pipeline cannot continue - no space for checkpoints"
    )
    print(f"{current_time.isoformat()}Z INFO: Emergency shutdown initiated")

    # Exit with error
    exit(1)


if __name__ == "__main__":
    run_ml_pipeline()
