---
name: product-single-image-generator
description: Generate, inspect and correct one reference-grounded product image using an existing product package. Use per-image creative planning, focused generation inputs and visual QA; raw evidence intake belongs to the project builder.
---

# Product single images

Generate one independent image per call. A single image may contain related detail regions, approved copy/graphics, comparison or verified steps. A full A+ example supplies context; follow the current task rather than reproducing a long page or expanding one image into a set. Multi-image A+ assembly belongs to the design team.

## Select the current image

For set-linked work, use the Amazon skill's `set_runtime.py` packet. Read only the selected child's task, evidence, creative brief and review requirements. Content groups may contain several children: one completed child does not complete its parent. A batch uses `next-generation` to find unproduced work; `next` may instead request review of an existing output.

For a new standalone creative task, resolve the builder's existing product package and read [art direction](references/art-direction.md). Read [state/contracts](references/state-and-contract.md) when creating/editing local records or reconciling their state; a complete resolved task packet can be executed directly. Local initialization uses:

```text
python3 scripts/init_run_records.py <package> --run-id <id> --sku <sku> --view <view>
python3 scripts/compile_generation_prompt.py <package> --contract <relative-contract>
python3 scripts/validate_run_records.py <package> --contract <relative-contract> --ready-for-generation
```

Complete `image_intent`, shared `visual_system`, this image's `creative_brief` and relevant [quality fields](references/visual-quality.md). A blank scaffold or camera/product/text boxes are not a design. For raw mixed requirements, use the builder's [intake](../product-image-project-builder/references/automatic-intake.md).

## Generate from the assigned job

Establish the sales task, buyer question, role and necessary proof first. Material needs readable texture; structure needs its actual interface; selection needs verified choices; operation needs evidenced states; lifestyle needs the assigned person/action/environment. Use `image_intent.module_role` for the task role. Existing `creative_brief.module_role` remains a fallback when the intent has no role; store an imported task's role once. Template constraints govern evidence and physical states; the brief governs visual expression.

Real product evidence controls identity and geometry. Style/pose references have only their declared roles. Use the packet's selected references, and attach actual image data/files to the generator; paths in a prompt are not attachments. Send the current prompt only, without the whole plan, intake archive, history or unrelated QA. A file packet cannot erase earlier chat context. In web testing use the Amazon skill's [browser workflow](../product-amazon-image-set-generator/references/browser-testing.md) rather than requiring local scripts.

Make the chosen visual relationship, light, space and type treatment visible in the actual prompt and image. Keep the sold product readable and true to scale. Shared `visual_system` sets background lightness/colour, warm–cool balance, contrast/shadow and type-family boundaries; each child chooses composition, scene and density within them. Local adjustments, catalog recipes and references cannot override those boundaries. Keep required white main-image backgrounds and actual product colours. Copy/graphics are permitted when assigned. Preserve selected supplied wording and language exactly, including accents, punctuation, numbers and units; analysis text does not become lettering. Invent no product facts, hidden structure or operating states.

Separate assigned visual facts from exact copy. A copy-only selling point does not require an effect, action or visual proof. Combine naturally related points where supported and let other points remain typographic. Prefer integrated generation for short, sparse copy; prefer separate typesetting for dense parameters, small print, exact fonts or frequently revised copy. Keep an accurate, legible integrated result without an extra text pass. Follow the [text execution criteria](references/art-direction.md#文字生成与单独排字) and inspect every final word either way. For A+ output, deliver only 1464×600 and verify actual pixels; do not add mobile or unrequested language variants.

## Code crop before A+ review

Treat A+ landscape **2.44:1 (1464:600)** as a high-priority generation constraint, ahead of style/reference framing and local layout choices. State it at the start of every A+ image prompt; compose all required content within that canvas. If the current tool exposes supported ratio/size controls, set them too; otherwise use the prompt, without inventing parameters or switching to an API workflow. See [code export](references/state-and-contract.md#mandatory-a-code-export) for compatible source dimensions.

A+ delivery always runs [finalize_a_plus_image.py](scripts/finalize_a_plus_image.py); a pixel-size prompt is not the export step. Preserve the generated original separately. New A+ tasks require source/crop QA before guarded export: observe source regions, inspect the proposed crop against this task, then export using `--package`, `--contract` and `--review`. See [code export](references/state-and-contract.md#mandatory-a-code-export). Matching ratios resize the full frame; mismatched ratios crop then resize proportionally. Never stretch or pad. For set work, use `raw_output_path` and `output_path`; an existing raw resumes postprocessing. Standalone A+ initialization uses `--a-plus`.

For mismatched ratios, AI identifies a normalized `--keep-box` containing all required product, person/action and lettering in the original. The script finds a crop retaining that region; it refuses a region that cannot fit. Do not blindly center-crop or omit important content to make the command pass. Recompose/regenerate if needed; explicit `--allow-upscale` permits enlargement with sharpness review. Even an already exact-size original passes through the script into a separate final file. If code execution/Pillow is unavailable, report the unfinished export rather than claiming a compliant deliverable.

The guard checks projected region containment and explicit layout constraints, and requires a recorded visual judgment for that exact crop. It does not detect product boundaries or grade visual balance itself. Source/crop QA cannot substitute for final-image QA. Use the existing assistant/human observations; no segmentation model runtime is required.

## Inspect and record

Read [visual quality](references/visual-quality.md) when establishing inspection criteria or resolving an unclear check; reuse the current review packet's applicable checks afterward. The complete guide and example remain available for new risks and record editing. Inspect full-resolution pixels against original evidence. Check identity/topology, people, copy and actual canvas; add anatomy/contact, visible-hardware state and motion checks when relevant. Review `content_coverage`, `module_role_fit` and `design_quality` when required. Correct texture alone does not prove that the image answers its buyer question or realizes its design.

```text
python3 scripts/candidate_qa.py <package> --contract <relative-contract> --report qa/visual/<candidate>.json --init
```

New QA drafts bind review inputs and record observed final-image regions separately from target layout; annotate the assigned complete product, wearing area or detail, exact lettering, and uncertainty. Follow [actual composition and reuse](references/visual-quality.md#actual-composition-and-review-reuse). Scripts check bindings and explicit geometry on these annotations; they do not detect objects or establish aesthetics. Uncertain boundaries require review, never a default pass.

Before repeating visual inspection, query the saved report with the same command plus `--status`. Reuse valid observations for unchanged images/evidence/rules; an unchanged failure needs correction/replanning, not another identical inspection. After any image edit or crop, check the new final image. Link QA through the runtime for set work. Keep candidates pending human review and continue other authorized tasks. Only real user/designated-reviewer feedback can record acceptance.

## Correct the affected task

Focused feedback authorizes correction without repeating intake or asking for approval of routine design decisions. Retain the previous candidate and unrelated work. Structural errors require a new candidate from original evidence; local polish is for non-topological defects. A retry carries one current correction and stays within the original plus two retries. Pinned copy/layout/fact changes require an in-scope local revision rather than a hidden retry change. At the limit, replan or identify missing evidence; never invent it.

For changed source facts, use [state reconciliation](references/state-and-contract.md); preserve accepted history. Use [geometry checks](references/geometry-check.md) only for valid same-SKU/same-view masks. Geometry checks do not establish material, anatomy, topology or human acceptance.
