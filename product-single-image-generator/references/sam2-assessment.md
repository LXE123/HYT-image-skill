# Guided segmentation: design decision

Decision on 2026-10-23: **do not integrate SAM 2 or install a model for this skill**. The prior research did not install dependencies, download checkpoints or run inference. Model deployment is not an outstanding task.

[Meta's SAM 2 project](https://ai.meta.com/research/sam2/) informed the target-selection idea. Apply that idea through the existing [actual-composition observations](visual-quality.md#actual-composition-and-review-reuse): clarify what must be protected, use focused guidance only when useful, and retain uncertainty when boundaries cannot be established.

Assistant/human annotations remain estimates rather than segmentation masks. Existing code computes region containment, crop geometry, overlap and output dimensions; visual review assesses identity, completeness and design. Keep these responsibilities and existing report bindings. No model adapter, checkpoint, dependency, new schema or additional review stage is introduced.
