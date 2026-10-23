# Integrated geometry check

Geometry checking is an optional module inside `product-single-image-generator`. It compares a saved candidate with an explicitly approved template for the same SKU and view. It does not infer identity, alter candidates, generate images, or approve commercial quality.

Compare compatible projections and product poses: a perspective view, wrapped wearing pose or assigned macro cannot be judged against a flat full-product silhouette merely because it is the same SKU. Use a suitable approved template when available; otherwise retain unavailable/review-required status and inspect against the product evidence. Do not reject a candidate solely for lacking a comparable template, force it into the template's composition, or relax thresholds to conceal a mismatch. A view change already authorized by the current task does not itself imply a product-structure error.

## Template configuration

Put one configuration at `qa/geometry/templates/<view>/config.json`, with its template image, binary mask, and annotation in the same folder. The template must be approved for the exact SKU and view. Build it primarily from an approved render/mask pair and bind it to the current identity-lockset version. Add local anchor IDs only for high-risk components.

```json
{
  "schema_version": 1,
  "sku": "SKU",
  "view": "flat_front",
  "approval_status": "APPROVED",
  "identity_lockset_version": 1,
  "source_render_template_ids": ["front"],
  "source_anchor_ids": ["buckle-front", "connector-end"],
  "template": {
    "image": "template.png",
    "mask": "mask.png",
    "annotation": "annotation.json"
  },
  "canvas": {"width": 1000, "height": 1000},
  "segmentation": {
    "roi": [0, 0, 1000, 1000],
    "min_red": 115,
    "min_red_green_delta": 7,
    "min_red_blue_delta": 7
  },
  "registration": {"max_translation_px": 12, "max_scale_delta": 0.05},
  "checks": {
    "max_outline_difference_percent": 3.0,
    "max_width_error_px": 4,
    "max_width_error_percent": 7.0
  },
  "measurement_columns": {
    "upper": {"x": 500, "y_range": [200, 400]}
  }
}
```

Segmentation thresholds and measurement columns are view-specific engineering parameters. Validate them with known-good and known-bad fixtures before setting `approval_status` to `APPROVED`. Record approval provenance in the decision log.

## Execution and records

Run:

```text
<package-python> scripts/run_geometry_check.py <package-path> --contract <contract-path>
```

The command derives the candidate and default config from the contract. Use `--config` only to select a different versioned configuration inside `qa/geometry/templates/`.

The checker verifies package containment, current SKU/view/lockset consistency, approved render sources, candidate hash, template assets, and configuration. It writes registration artifacts under `qa/geometry/registered/<run_id>/<candidate_id>/` and each versioned report in its own subdirectory under `qa/geometry/reports/<run_id>/<candidate_id>/`. A later approved config can check a candidate that previously had no usable template without overwriting the earlier availability result.

Exit statuses:

- `0`: `AUTO_PASSED`
- `2`: `REJECTED` by encoded geometry rules
- `3`: `REVIEW_REQUIRED` or `REVIEW_REQUIRED_NO_TEMPLATE`
- `4`: invalid or inconsistent input

The result summary is recorded directly in `PRODUCT_STATE.json`; do not manually copy measurements into state. Inspect `result.json`, `measurements.json`, `overlay.png`, and `outline_diff.png` inside the reported version directory. A repeated call may reuse the same immutable report, and the same candidate ID can be checked with a later versioned configuration, but it cannot be rebound to different candidate content.
