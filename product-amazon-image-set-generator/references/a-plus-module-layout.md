# Department desktop A+ image workflow

Use only when the user requests A+ (alone or together with Gallery), or that scope is already established. An unqualified set request does not select A+ automatically. The reference Amazon page contributes its module structure only. It is not the user's product or a style reference. The department requested separate images and will assemble/layout the final A+ content. Do not generate an assembled A+ page, a multi-module contact sheet, or platform UI. Plan exact copy/graphics for each actual-product image as needed. “Separate images” is not a no-copy instruction: selling-point graphics, comparisons, internal detail panels and verified steps are allowed. Do not transcribe the reference seller's copy or invent its claims.

## Start or resume

Resolve the same existing product package and its current evidence/locks. For a new A+-only set:

```text
python3 scripts/init_visual_set.py <package> --set-id <new-set-id> --deliverable a-plus
```

This selects standard mode and A+ only, normally 13 independent images. Use `--count 9` through `--count 15` for the normal range. For both channels choose `--deliverable both`: each channel normally gets 13 images, not 13 combined. Explicit per-channel counts take precedence. If this set already exists, query `set_runtime.py ... next` instead of initializing again; saved scope/mode takes precedence over new defaults. Existing standalone/Gallery work stays in the same product package and keeps its own contracts and decisions.

The nine-image structural seed is below. It is a starting map, not a mandatory final content list or image limit:

Treat this table as a one-to-many mapping, never as seven generation calls. The seed arithmetic is `1 + 1 + 2 + 2 + 1 + 1 + 1 = 9` independent files. A normally selected 13-image set must have 13 explicit child IDs before production, even when the source document describes only seven groups. Group descriptions are input responsibilities; each child needs its own visual proof, copy assignment and design treatment, which may be an explanatory graphic or comparison rather than a photograph. Display the planned group count and image count separately; check the latter against the saved target, including in a no-script web run.

| Page module | Display type | Image task IDs | Content responsibility |
|---|---|---|---|
| `aplus-hero` | Full background | `a-plus-01` | Product introduction |
| `aplus-craftsmanship` | Full background | `a-plus-02` | Construction/finishing |
| `aplus-material-details` | Carousel | `a-plus-03`, `a-plus-04` | Material/signature component details |
| `aplus-lifestyle` | Carousel | `a-plus-05`, `a-plus-06` | Two distinct relevant use contexts |
| `aplus-range` | Full background | `a-plus-07` | Evidenced choices/variants |
| `aplus-size` | Full background | `a-plus-08` | Verified size/compatibility |
| `aplus-care` | Full background | `a-plus-09` | Supported care guidance |

For counts 10–15 the initializer adds distinct drafts: material experience (10), evidenced use/adjustment (11), active lifestyle (12), everyday lifestyle (13), additional construction (14), and work/study lifestyle (15). The operation task creates its own use group instead of being mislabelled as material or care. Thus the usual 13-image draft has eight initial groups; seven is only the original reference seed. Every addition still needs real evidence and a concrete composition before approval. Full lifestyle images should show a recognizable person/action/environment; do not reduce every scene to a wrist crop.

This is a revisable starting structure, not a platform-wide seven-module limit. No seed establishes leather, cowhide, steel, a watch, particular colours, model gender, compatibility, care advice or a mechanism. Replace/merge unsupported or irrelevant responsibilities using the actual product's evidence; never invent facts to fill the initial slots. Care and size guidance require the user's verified specs/instructions. Different lifecycle/lifestyle images need distinct buyer relevance, not an arbitrary extra pose.

Output requirements are code-cropped PNGs at 1464 × 600 pixels (`aspect_ratio: 1464:600`, `postprocess: CODE_CROP_RESIZE`). Keep the generated original, then run the single-image [code export](../../product-single-image-generator/references/state-and-contract.md#mandatory-a-code-export) before review; the image model does not establish exact delivered pixels. These pixels apply only to A+; Gallery uses its own main/secondary canvas. New A+ tasks use this same canvas even when generic ungrouped templates are explicitly selected. No 600 × 450 mobile or 970 × 600 standard-A+ versions are requested. These dimensions are the user's department brief, not a claim about all Amazon module specifications.

## Three separate classifications

- `display_type` owns page presentation: `FULL_BACKGROUND_IMAGE` or `CAROUSEL`.
- `content_role`, `sales_task`, `buyer_question` own the page's information responsibility. Construction explains finishing; a material page explains surface/material; a component detail explains a particular evidenced structure. Avoid using the same evidence/copy to repeat one claim across all three.
- The image task's `template_id` owns how one image is generated. A content responsibility does not dictate its display type or lock it to one rendering template.

Keep the existing `modules[].module_id` as the independent image-task ID for compatibility. `a_plus_layout.page_modules[].page_module_id` is its parent presentation ID. Each A+ image belongs to exactly one page position; Gallery images cannot be members. `sequence` and `image_ids` order control presentation, not identity. Do not rename existing IDs when inserting a task.

## Module expression and production progression

Each module has a different communication function within the shared visual identity. The shared system owns atmosphere, palette/light/type continuity and general composition principles, not one mandatory product/text arrangement. Specify the current image's concrete device and treatment in its creative brief; the module function determines the appropriate scale, density, evidence and reading path.

| Responsibility | Dominant design language | What cannot substitute for it |
|---|---|---|
| Product introduction | Recognition, product-led atmosphere and overall form | A slogan that hides what is sold |
| Material | Surface light, observation scale, texture/context relationship | Complete-product beauty shot with a material adjective |
| Construction/component | Local structure, interface and finishing explanation | Another hero showing no relevant local evidence |
| Variants/selection | Comparable views, consistent scale, clear choice labels | One attractive variant standing in for a range |
| Fit/compatibility | Verified decision information and explanatory relationships | Side profile alone with no selection information |
| Operation | Evidenced states, sequence and action clarity | Static hero or invented mechanism |
| Care | Supported guidance linked to a product area or action | Generic durability slogan or another hero |
| Lifestyle | Meaningful person/action/environment and natural product presence | Interchangeable portrait or floating product beside a slogan |

These are functional responsibilities, not fixed layouts, colours or a closed list of styles. A current explicit/custom role belongs in `image_intent.module_role` (older `creative_brief.module_role` remains a fallback); replan the real task when changing responsibility. Do not use a role label to fabricate evidence or silently replace a missing size/operation task. Children in the same carousel may have different functions: material photography and hardware explanation should remain distinct.

New drafts use `module_language_policy_version: 1`. The resolver supplies one current `module_language` to generation and review, including its task ID, role, buyer question, expression principle, `must_show` and `not_a_substitute`; the complete role library and neighbouring prompts are not forwarded. `module_role_fit` checks the actual pixels against that responsibility. Existing plans without the policy retain their previous requirements; use a revised draft for intentional upgrades. Merely writing a role or passing a script does not prove that the image performs it.

Within an already authorized multi-image/pilot batch, query `set_runtime.py <package> --set-id <set> next-generation`, then `prepare --module-id <returned-id>`. This selects only unproduced tasks and leaves existing candidates pending review. Ordinary `next` remains the review-first control entry: a repeated pending image is a request to inspect, not to regenerate. Never fabricate acceptance to advance. When no unproduced tasks remain, review/resolve remaining candidates; the set is not automatically complete.

## Local additions and revisions

Add detail to an existing group when it answers that group's buyer question. For example, from this skill directory:

```text
python3 scripts/add_a_plus_image.py <package> --set-id <set-id> --page-module-id aplus-craftsmanship --image-id craft-edge-detail --template-id hardware_static --target-view edge_detail --sales-task "Show evidenced edge finishing" --buyer-question "How is this edge finished?"
```

The helper only edits an unproduced draft. It creates one blank image spec, preserves other specs/IDs, updates order and state, and promotes a single-image page to a carousel when needed. Fill the new image's actual evidence, locks, claims, composition and quality fields before approving. Use `--after-image-id <id>` to insert within a group.

Normal local additions do not activate large production. Reaching 30–40 A+ image tasks requires an explicit user request for expanded mode: initialize a new set with `--mode expanded`, or use `--activate-expanded` when extending this unproduced draft. The latter retains its page grouping and 1464 × 600 canvas. The limit is 40 per channel; 15 Gallery plus 15 A+ remains ordinary production. Normal detail additions within 9–15 do not activate expanded mode. Do not use the activation flag on the user's behalf merely because more images might be useful.

A new buyer question can justify a new group. Use the same helper with a new `--page-module-id`, `--new-page --content-role <role>` and optionally `--after-page-id <id>`. The new page initially takes the new image's sales task and buyer question; edit the page-level responsibility if it later contains several images. An unsupported template/claim is not made valid by adding a group.

If evidence for variants, sizing, care or operation is missing, record a gap/block or explicitly replan the responsibility and update its name/question; never count an unrelated macro as fulfilling that topic.

For merging or reordering draft groups, edit only their membership/order and the image index order/sequence; keep IDs and image spec content stable. Every A+ image must still appear exactly once. Revalidate the complete plan afterward. Shared style remains pinned once; do not automatically attach neighbouring outputs or earlier failed attempts.

Approved plans/specs remain immutable. An approved set needs a new set revision before adding, removing, or changing membership, facts, copy, pose or layout. Record the affected image IDs and reasons in the new plan's `revision_change` object (`source_set_id`, `source_plan_sha256`, `affected_image_ids`, `reason`). Check shared product/claim/style changes against every dependent image. Unchanged outputs keep their original acceptance history; this extension does **not** automatically transfer acceptance to a new plan or implement cross-revision output reuse. Do not promise that behaviour or reset existing accepted decisions. Eligible older outputs remain opt-in references under the existing rules.

## Work packets, review and delivery

`next` reports separate page-module and image-task counts, plus only the current task's parent and position. `prepare` still produces one image's focused prompt and evidence packet. Parent/page metadata is for orchestration; send only `prompt` and the listed image references to the generator. Other slides are not additional context automatically.

Use the existing per-image QA and human acceptance workflow. Verify actual output dimensions at review; a prompt containing dimensions is not evidence that the image has those dimensions. Check colour/product appearance and visual-system consistency across images in the same group without using previous generated images as product truth. Check the final order for repeated messages or missing buyer questions.

```text
python3 scripts/set_runtime.py <package> --set-id <set-id> handoff
```

This synchronizes state and returns a compact designer manifest: page order/type/role, individual image IDs/statuses and accepted output/QA pointers. Draft/unreviewed items stay labelled; they are not final deliverables. No image stitching or upload occurs. A page's derived status is accepted only when all required child images are accepted; it is not a separate human decision and does not certify the designer's eventual assembled page. The existing per-image gates still determine set completion.
