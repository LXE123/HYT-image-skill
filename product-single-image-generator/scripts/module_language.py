"""Task-specific visual responsibilities, not style presets or product facts."""

LANGUAGES = {
    "hero": ("Recognition and atmosphere: organize a complete product/context into a clear opening visual.", "Recognizable sellable object and its overall proposition", "A repeated generic slogan cannot replace product recognition"),
    "product_presentation": ("Product-led composition: make the evidenced form and distinguishing feature legible.", "The actual product and assigned differentiating feature", "An unrelated person, prop or headline cannot become the subject"),
    "material": ("Material evidence: use observation scale, surface light and a context cue to explain texture.", "Readable actual surface/texture at a credible scale", "A full-product hero with a material adjective is not material proof"),
    "detail": ("Local construction: isolate the assigned component and explain its actual connection or finishing.", "The named component, interface or finishing detail", "Another complete-product render cannot replace the required local evidence"),
    "lifestyle": ("Environmental storytelling: meaningful person/action/place with naturally readable wearing or use.", "The assigned person, activity and environment with correct product contact and scale", "A floating product hero or interchangeable portrait with a slogan is not the assigned use context"),
    "variants": ("Selection language: comparable views, consistent scale and clear labels for evidenced choices.", "Actual registered choices and the information needed to distinguish them", "One attractive product hero cannot stand in for a range or selection guide"),
    "fit": ("Explanatory selection: organize verified dimensions, compatibility or fit into an easy decision path.", "Verified fit/size information and the actual selection relationship", "A side view or texture photo alone cannot answer which version fits"),
    "operation": ("Sequential explanation: organize evidenced states and actions into a readable use sequence.", "The required verified states, order and action", "A static beauty shot or invented disassembly cannot replace operating evidence"),
    "care": ("Practical guidance: connect supported care instructions with the relevant product area or action.", "The actual supported care guidance and its product relationship", "A fresh hero or an unverified durability slogan cannot replace care information"),
    "main": ("Main-image identification: complete sellable object on the required clean background.", "Complete accurate product and allowed main-image presentation", "Atmospheric scenes or decorative typography cannot override main-image requirements"),
}

TEMPLATE_ROLES = {"main_product": "main", "material_macro": "material", "hardware_static": "detail", "lifestyle_simple": "lifestyle", "mechanism_steps": "operation", "size_fit": "fit", "range_story": "variants"}
PAGE_ROLES = {"hero": "hero", "craftsmanship": "detail", "material_and_details": "material", "lifestyle": "lifestyle", "range": "variants", "size_and_fit": "fit", "care": "care", "verified_use": "operation"}
ROLE_ALIASES = {**PAGE_ROLES, "construction": "detail", "component": "detail", "size": "fit", "use": "operation"}


def canonical_role(role):
    return ROLE_ALIASES.get(role, role) if isinstance(role, str) else role


def resolve_module_language(module, page=None):
    """A child's concrete task wins over a broad parent grouping."""
    intent = module.get("image_intent") or {}
    brief = module.get("creative_brief") or {}
    template = module.get("generation_template") or {}
    if not isinstance(intent, dict) or not isinstance(brief, dict) or not isinstance(template, dict):
        raise ValueError("module language needs object-shaped intent, creative brief and template")
    template_id = template.get("template_id")
    explicit = intent.get("module_role") or brief.get("module_role")
    role = canonical_role(explicit) if explicit else TEMPLATE_ROLES.get(template_id) or PAGE_ROLES.get((page or {}).get("content_role")) or "product_presentation"
    # Care/fit/range may use a generic product-overview template; their page job remains authoritative.
    if not explicit and template_id == "product_overview":
        role = PAGE_ROLES.get((page or {}).get("content_role"), role)
    if not isinstance(role, str) or not role.strip():
        raise ValueError("module_role must describe the current image responsibility")
    language = LANGUAGES.get(role)
    if language is None:
        language = (brief.get("visual_device", "Use the current task's planned visual relationship"),
                    module.get("buyer_question") or intent.get("buyer_question", "Answer the current buyer question"),
                    "Do not replace this custom task with a stock hero or another module's content")
    result = {
        "image_task_id": module.get("module_id") or module.get("candidate_id"),
        "role": role,
        "sales_task": module.get("sales_task") or intent.get("sales_task"),
        "buyer_question": module.get("buyer_question") or intent.get("buyer_question"),
        "visual_language": language[0],
        "must_show": [language[1]],
        "not_a_substitute": [language[2]],
        "continuity_rule": "Shared palette/light/type connect the set; this module's responsibility determines imagery, scale, density and graphic treatment. Do not inherit the opening hero's composition.",
    }
    required = intent.get("must_show", [])
    if not isinstance(required, list) or any(not isinstance(x, str) or not x.strip() for x in required):
        raise ValueError("image_intent.must_show must be an array of nonempty strings")
    result["must_show"] = list(dict.fromkeys([*result["must_show"], *required]))
    if page:
        result["parent"] = {k: page[k] for k in ("page_module_id", "content_role") if k in page}
    return result
