PROMPT_STYLE_FLASH = "flash"
PROMPT_STYLE_PRO = "pro"
PROMPT_MODE_CATALOG = "catalog"
PROMPT_MODE_EXPERT = "expert"
PROMPT_SET_DEFAULT = 1
PROMPT_SET_OPTIONS = (1, 2, 3, 4, 5)


def _resolve_prompt_set(prompt_set: int | str | None) -> int:
    if prompt_set is None:
        return PROMPT_SET_DEFAULT
    try:
        parsed = int(str(prompt_set).strip())
    except (TypeError, ValueError):
        return PROMPT_SET_DEFAULT
    if parsed in PROMPT_SET_OPTIONS:
        return parsed
    return PROMPT_SET_DEFAULT


def _normalize_style_description(style_description: str) -> str:
    return " ".join(str(style_description or "").split()).strip()


def _normalize_expert_preferences(expert_preferences: dict | None) -> dict[str, str]:
    if not isinstance(expert_preferences, dict):
        return {
            "style_vibe": "classic",
            "lifestyle": "balanced",
            "maintenance": "medium",
            "hair_length": "short",
        }

    normalized = {
        "style_vibe": str(expert_preferences.get("style_vibe", "classic") or "classic").strip().lower(),
        "lifestyle": str(expert_preferences.get("lifestyle", "balanced") or "balanced").strip().lower(),
        "maintenance": str(expert_preferences.get("maintenance", "medium") or "medium").strip().lower(),
        "hair_length": str(expert_preferences.get("hair_length", "short") or "short").strip().lower(),
    }

    return {
        "style_vibe": normalized["style_vibe"] if normalized["style_vibe"] else "classic",
        "lifestyle": normalized["lifestyle"] if normalized["lifestyle"] else "balanced",
        "maintenance": normalized["maintenance"] if normalized["maintenance"] else "medium",
        "hair_length": normalized["hair_length"] if normalized["hair_length"] else "short",
    }


def _inject_hair_color_into_style_instruction(style_instruction: str, hair_color_name: str) -> str:
    normalized_hair_color = (hair_color_name or "").strip()
    if not normalized_hair_color:
        return style_instruction
    trimmed_instruction = style_instruction.rstrip()
    if trimmed_instruction.endswith("."):
        trimmed_instruction = trimmed_instruction[:-1]
    return f"{trimmed_instruction} in {normalized_hair_color} color."


def _build_expert_prompt(
    *,
    hair_color_name: str,
    expert_preferences: dict | None,
) -> str:
    normalized_preferences = _normalize_expert_preferences(expert_preferences)
    normalized_hair_color = (hair_color_name or "").strip()

    style_vibe = normalized_preferences["style_vibe"]
    lifestyle = normalized_preferences["lifestyle"]
    maintenance = normalized_preferences["maintenance"]
    hair_length = normalized_preferences["hair_length"]

    color_instruction = (
        f"Target hair color: {normalized_hair_color}."
        if normalized_hair_color
        else "Target hair color: keep natural tone."
    )

    return " ".join(
        (
            "Operation: Expert Haircut Recommendation and Simulation.",
            "Role: You are a senior licensed barber and haircut consultant making a real, in-chair recommendation.",
            "Input Context: Image 1 is the subject selfie.",
            "Primary Goal: design and render a haircut that best fits the subject using professional barbering and facial-proportion analysis.",
            "Analysis Rules: estimate face shape, forehead height, hairline position, recession pattern, hair density, and crown behavior from the selfie.",
            "Current-State Check: identify current visible hair length and density first, then plan only feasible changes from that baseline.",
            "Decision Rules: choose cut geometry, fade/taper level, top length distribution, and edge transitions that improve facial balance and natural realism.",
            "User Preferences:",
            f"style vibe={style_vibe}; lifestyle={lifestyle}; maintenance level={maintenance}; preferred length={hair_length}.",
            "Feasibility Policy: prioritize physically realistic outcomes from the current hair state visible in Image 1.",
            "Preferences are guidance, not hard constraints. If a preference conflicts with visible hair reality, choose the closest feasible alternative.",
            "Length Realism Rules: do not invent non-existent long hair mass from very short cuts. Avoid major length jumps that would require months of growth.",
            "Conflict Rule Example: if the input haircut is very short and the preference asks for long hair, keep a short/near-short realistic result and express the requested vibe through texture, taper, and shape details.",
            "Service Realism Rules: keep the result achievable in a normal barbershop session without wigs, extensions, transplants, or synthetic add-ons.",
            "Realistic-over-Literal Rule: when realism and preference conflict, realism wins.",
            color_instruction,
            "Do not use external style-catalog assumptions. Generate a best-fit haircut directly from the subject analysis and the stated preferences.",
            "Strict Constraints: keep face identity, skin tone, body, clothing, and pose exactly unchanged.",
            "Keep background, camera angle, and lighting unchanged.",
            "Edit scalp hair only. Keep beard shape and beard color unchanged.",
            "Output: return one realistic, high-fidelity portrait image.",
        )
    )


def _flash_input_context_instruction(use_composite_input: bool, with_beard_reference: bool) -> str:
    if use_composite_input:
        if with_beard_reference:
            return "Input: multi-panel image where LEFT is selfie, MIDDLE is hairstyle reference, and RIGHT is beard reference."
        return "Input: two-panel image where LEFT is selfie and RIGHT is hairstyle reference."
    if with_beard_reference:
        return "Input: Image 1 is selfie, Image 2 is hairstyle reference, and Image 3 is beard reference."
    return "Input: Image 1 is selfie and Image 2 is hairstyle reference."


def _pro_input_context_instruction(use_composite_input: bool, with_beard_reference: bool) -> str:
    if use_composite_input:
        if with_beard_reference:
            return (
                "Input Context: The input is a horizontal multi-panel image. "
                "Image 1 (LEFT): The Subject (Selfie). "
                "Image 2 (MIDDLE): The Hairstyle Reference. "
                "Image 3 (RIGHT): The Beard Reference."
            )
        return (
            "Input Context: The input is a two-panel image. "
            "Image 1 (LEFT): The Subject (Selfie). "
            "Image 2 (RIGHT): The Hairstyle Reference."
        )
    if with_beard_reference:
        return (
            "Input Context: Image 1: The Subject (Selfie). "
            "Image 2: The Hairstyle Reference. "
            "Image 3: The Beard Reference."
        )
    return "Input Context: Image 1: The Subject (Selfie). Image 2: The Hairstyle Reference."


def _build_flash_prompt(
    *,
    use_composite_input: bool,
    include_beard_reference: bool,
    style_description: str,
    hair_color_name: str,
    beard_color_name: str,
    apply_beard_edit: bool,
    prompt_set: int,
) -> str:
    normalized_style_description = _normalize_style_description(style_description)
    normalized_hair_color = (hair_color_name or "").strip()
    normalized_beard_color = (beard_color_name or "").strip()
    with_beard_reference = include_beard_reference and apply_beard_edit
    resolved_prompt_set = _resolve_prompt_set(prompt_set)
    style_description_instruction = (
        "Additional haircut description from style catalog: "
        f"{normalized_style_description}. "
        "Use this text together with Image 2 to improve haircut matching."
        if normalized_style_description
        else ""
    )

    if with_beard_reference:
        beard_instruction = "Use Image 3 as beard reference and blend sideburns naturally into the haircut."
        beard_color_instruction = (
            f"Set beard color to {normalized_beard_color}."
            if normalized_beard_color
            else "Keep beard color natural."
        )
    else:
        beard_instruction = "Keep beard shape and color unchanged."
        beard_color_instruction = ""

    if resolved_prompt_set == 2:
        style_instructions = (
            "Task: replace hairstyle in Image 1 using Image 2 as the only haircut target.",
            "Hard edit: completely remove the current scalp hair in Image 1 before applying the new style.",
            "Do not preserve old hair shape, length, or volume.",
            "Haircut match must be obvious: same silhouette, same fringe or part direction, same top mass, and same side/fade flow.",
            "If the result looks unchanged, regenerate with stronger replacement.",
        )
    elif resolved_prompt_set == 3:
        style_instructions = (
            "Replace only scalp hair in Image 1 with the hairstyle from Image 2.",
            "Match the reference haircut shape clearly, including top volume, part/fringe direction, and side taper.",
            "Prioritize haircut similarity over the original hairstyle.",
        )
    elif resolved_prompt_set == 4:
        style_instructions = (
            "Two-step edit: first remove existing scalp hair, then apply the hairstyle from Image 2.",
            "The final haircut should read as the reference style on the same person, not a light variation of the old cut.",
            "Match outline, layers, top lift, fringe/part, and fade gradient from the reference.",
            "Force a visible style change while preserving photorealism.",
        )
    elif resolved_prompt_set == 5:
        style_instructions = (
            "Change only the scalp hair in Image 1.",
            "Replace the hairstyle in Image 1 with the hairstyle from Image 2.",
            "Reference haircut is the source of truth. Do not keep the original haircut shape.",
            "Match the reference overall silhouette, total length, top volume, fringe/part direction, and side/fade shape.",
        )
    else:
        style_instructions = (
            "Use Image 2 as the haircut target for Image 1.",
            "Fully replace the current hairstyle in Image 1. Do not preserve the original hair shape or volume.",
            "Match the reference hairstyle clearly: silhouette, fringe/part direction, top volume, and side/fade shape.",
        )
    if style_instructions:
        style_instructions = (
            _inject_hair_color_into_style_instruction(style_instructions[0], normalized_hair_color),
            *style_instructions[1:],
        )

    return " ".join(
        part
        for part in (
            _flash_input_context_instruction(use_composite_input, with_beard_reference),
            style_description_instruction,
            *style_instructions,
            "Keep face, skin tone, body, and clothing unchanged.",
            "Keep face direction exactly the same as Image 1.",
            "Keep background, camera angle, and lighting unchanged.",
            beard_instruction,
            beard_color_instruction,
            "Return one realistic portrait image only.",
        )
        if part
    )


def _build_pro_prompt(
    *,
    use_composite_input: bool,
    include_beard_reference: bool,
    style_description: str,
    hair_color_name: str,
    beard_color_name: str,
    apply_beard_edit: bool,
    prompt_set: int,
) -> str:
    normalized_style_description = _normalize_style_description(style_description)
    normalized_hair_color = (hair_color_name or "").strip()
    normalized_beard_color = (beard_color_name or "").strip()
    with_beard_reference = include_beard_reference and apply_beard_edit
    resolved_prompt_set = _resolve_prompt_set(prompt_set)
    style_description_instruction = (
        "REFERENCE TEXT: Additional haircut description from style catalog: "
        f"{normalized_style_description}. "
        "Use this text together with Image 2 to improve haircut matching."
        if normalized_style_description
        else ""
    )

    if with_beard_reference:
        beard_instruction = "BEARD: Replace beard shape using Image 3, blending sideburns naturally into the haircut."
        beard_color_instruction = (
            f"Set beard color to {normalized_beard_color}."
            if normalized_beard_color
            else "Keep beard color natural."
        )
    else:
        beard_instruction = "BEARD: Keep beard shape and color unchanged."
        beard_color_instruction = ""

    if resolved_prompt_set == 2:
        process_instruction = (
            "Execution Guidelines: "
            "1. REPLACE: Completely remove the subject's original hairstyle. "
            "Do not let the original hair volume or shape limit the new style. "
            "2. MATCH: Visibly transfer the structure of the reference hairstyle to the subject. "
            "You must match the reference silhouette, fringe direction, top volume, side/fade gradation, and parting."
        )
    elif resolved_prompt_set == 3:
        process_instruction = (
            "Execution Guidelines: Perform a direct hair replacement only. "
            "Remove existing scalp hair, then reconstruct the reference style with clear silhouette match, "
            "fringe/part match, top-volume match, and side/fade match. "
            "The output must show a visible haircut change."
        )
    elif resolved_prompt_set == 4:
        process_instruction = (
            "Execution Guidelines: Stage 1 erase original scalp hair influence. "
            "Stage 2 apply the reference haircut faithfully. "
            "Stage 3 verify the output is visibly different from the input haircut while identity and scene remain unchanged."
        )
    elif resolved_prompt_set == 5:
        process_instruction = (
            "Execution Guidelines: Edit scalp hair only. Replace the hairstyle in Image 1 with Image 2 and treat the reference "
            "as the source of truth. Match silhouette, total length, top volume, fringe/part direction, and side/fade shape."
        )
    else:
        process_instruction = (
            "Execution Guidelines: Replace the hair in Image 1 with the hairstyle in Image 2. "
            "Fully remove original hairstyle constraints and transfer the reference haircut structure, including silhouette, "
            "fringe/part direction, top volume, side/fade gradation, and parting."
        )
    if normalized_hair_color:
        process_instruction = f"{process_instruction} Apply the hairstyle in {normalized_hair_color} color."

    return " ".join(
        part
        for part in (
            "Operation: Hair Replacement.",
            _pro_input_context_instruction(use_composite_input, with_beard_reference),
            "Primary Instruction: Create a realistic haircut simulation using the reference hairstyle.",
            style_description_instruction,
            process_instruction,
            "Strict Constraints: IDENTITY: Keep the face, skin tone, body, and clothing of Image 1 exactly unchanged.",
            "POSE: Keep face direction exactly the same as Image 1.",
            "ENVIRONMENT: Keep the background, camera angle, and lighting of Image 1 exactly unchanged.",
            beard_instruction,
            beard_color_instruction,
            "OUTPUT: Return a single, high-fidelity portrait image.",
        )
        if part
    )


def build_hair_transformation_prompt(
    *,
    use_composite_input: bool = False,
    include_beard_reference: bool = False,
    style_description: str = "",
    hair_color_name: str = "",
    beard_color_name: str = "",
    apply_beard_edit: bool = False,
    prompt_style: str = PROMPT_STYLE_PRO,
    prompt_set: int | str | None = PROMPT_SET_DEFAULT,
    prompt_mode: str = PROMPT_MODE_CATALOG,
    expert_preferences: dict | None = None,
) -> str:
    if str(prompt_mode or "").strip().lower() == PROMPT_MODE_EXPERT:
        return _build_expert_prompt(
            hair_color_name=hair_color_name,
            expert_preferences=expert_preferences,
        )

    resolved_prompt_set = _resolve_prompt_set(prompt_set)
    normalized_style = str(prompt_style or "").strip().lower()
    if normalized_style == PROMPT_STYLE_FLASH:
        return _build_flash_prompt(
            use_composite_input=use_composite_input,
            include_beard_reference=include_beard_reference,
            style_description=style_description,
            hair_color_name=hair_color_name,
            beard_color_name=beard_color_name,
            apply_beard_edit=apply_beard_edit,
            prompt_set=resolved_prompt_set,
        )
    return _build_pro_prompt(
        use_composite_input=use_composite_input,
        include_beard_reference=include_beard_reference,
        style_description=style_description,
        hair_color_name=hair_color_name,
        beard_color_name=beard_color_name,
        apply_beard_edit=apply_beard_edit,
        prompt_set=resolved_prompt_set,
    )
