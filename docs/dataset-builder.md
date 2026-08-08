# Dataset Builder and Model Lifecycle

The Dataset Builder is the human-verification layer for product-specific object detectors. It reuses the Product database, camera/Block assignments, Stream Manager, VisionDB, training process, real-camera benchmarks, and the canonical production detector path.

## Data lifecycle

1. The operator creates an immutable dataset version for an existing Product.
2. Frames come from Stream Manager or an explicit upload. A perceptual hash rejects near duplicates.
3. AI suggestions are stored as `UNVERIFIED`; they cannot be approved until the operator accepts, modifies, or deletes them.
4. Approving a frame writes its verified, normalized boxes into a one-class YOLO dataset. Similarity clusters remain entirely in either train or validation.
5. Training creates a new immutable model record and runs asynchronously. Status reflects the real child process (`QUEUED`, `TRAINING`, `COMPLETED`, or `FAILED`).
6. A model is deployable only after real-camera benchmark accuracy is at least 90%. Deployment updates the active-model registry atomically and leaves previous weights intact for rollback.

## Storage

- Original source images: `dataset_sources/<dataset_id>/`
- Materialized YOLO versions: `datasets/<product_class>/v<version>/`
- Immutable weights: `models/dataset_builder/<product_class>/<model_name>/best.pt`
- Active registry: `models/active_models.json`
- Metadata: the shared VisionDB tables prefixed with `vision_dataset_`, plus `vision_models`, `vision_model_deployments`, and `vision_review_queue`

Legacy Baget images can be imported for relabeling. Historical labels and their incorrect taxonomy are deliberately ignored.

## API

All lifecycle endpoints are under `/api/v1/datasets`: dataset creation/list/detail/health, live capture and auto-capture, upload/import/export, annotation save/approval/rejection, training, model benchmark/deploy/rollback, and review-queue handling.

Deployment never falls back silently. If explicitly deployed custom weights cannot load, the detector reports `<PRODUCT> DETECTOR UNAVAILABLE`.
