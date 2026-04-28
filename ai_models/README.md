# AI Models

The MVP runs **lightweight rule-based / scene-aware substitutes** that share
the same interfaces as production-grade models.

| Module | MVP implementation | Production swap-in |
| --- | --- | --- |
| `app.ai.vision.MockVisionDetector` | scene-descriptor → label mapper | `YoloDetector` (YOLOv8n/s) — toggle with `ENABLE_YOLO=true` and `pip install ".[ai]"` |
| `app.ai.audio.RuleBasedAudioClassifier` | label → confidence map | YAMNet / PANNs CNN |
| `app.ai.fusion.FusionEngine` | probabilistic-OR fusion | Trained gating network / GNN |
| `app.prediction.HeatmapEngine` | temporal-decay grid | LSTM / GNN forecaster |

## Adding a new vision model

```python
from app.ai.vision import VisionDetector, VisionDetection

class MyDetector(VisionDetector):
    def infer(self, frame):
        return [VisionDetection("violence", 0.9)]
```

Wire it in `app.ai.vision.build_default_detector()`.

## YOLOv8 setup

```bash
cd backend
pip install -e ".[ai]"
export ENABLE_YOLO=true
export YOLO_MODEL=yolov8n.pt
uvicorn app.main:app
```

Ultralytics will auto-download the weights on first inference. Replace
`MockVisionDetector` consumers (the camera sensor) with a real RTSP / USB
stream by subclassing `app.sensors.camera.CameraSensor`.
