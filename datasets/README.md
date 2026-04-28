# Datasets

The MVP generates **synthetic** sensor and incident data via the simulation
engine in `backend/simulations/`. No real surveillance footage is shipped.

For training upgraded models you can drop datasets here:

- Vision: COCO-style bounding boxes for violence / weapons / abandoned-object
  classes. See `app.ai.vision.YoloDetector` for the consumer.
- Audio: ESC-50 / UrbanSound8k / a custom siren+gunshot+scream corpus,
  mel-spectrogram features. Consumer: `app.ai.audio`.
- Crime history: CSV/Parquet of geo-tagged incidents to seed
  `app.prediction.HeatmapEngine` (you can point the engine to a different
  source by overriding the `compute()` method).
