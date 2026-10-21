# Index schema

`product_evidence` contains independent product images. Each item needs:

- `evidence_id`: unique stable ID;
- `path` and `sha256`: package-relative source and its exact content hash;
- `source_type`: `REAL_PHOTO`, `DESIGN_RENDER`, `CAD_RENDER`, or `DETAIL`;
- `view`: the visible viewpoint, such as `front`, `back`, `side`, `inside`, or `detail_buckle`;
- `structures`: non-empty list of visible facts this image may constrain; use `full_product` for a complete silhouette;
- `hard_constraint`: boolean indicating whether downstream identity work must follow the visible facts.
- `observed_states`: optional list of visibly proven component-specific state IDs, required when downstream hardware/operation templates cite a state. See [hardware-evidence.md](hardware-evidence.md).

Use any number of images. Readiness is based on usable coverage rather than a fixed count. A source cannot constrain unseen structure. `REAL_PHOTO` is authoritative for visible material, colour, and manufacturing detail; renders cannot override it.

`render_templates` is optional but strongly recommended. Each item needs `template_id`, `view`, `rgb_path`, `mask_path`, and `status` (`approved` or `provisional`). It may include aligned `part_id_mask_path`, `depth_path`, `normal_path`, and `model_version`. RGB must be a clean render; the mask is an aligned product-only alpha/binary mask. Keep local structure annotations in `qa/identity_anchors/`, not in this list.

In `PHOTO_EVIDENCE` mode, at least one `product_evidence` item must have `source_type: REAL_PHOTO` and `hard_constraint: true`.

Each `known_issues` item needs `issue_id`, `structure`, `symptom`, and `status` (`open` or `resolved`). Each related `error_supplements` item needs `related_issue`, `path`, and `verified`. A resolved issue requires at least one related supplement with `verified: true`.
