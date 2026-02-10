def build_hair_transformation_prompt(
    *,
    use_composite_input: bool = False,
    include_beard_reference: bool = False,
    hair_color_name: str = "",
    beard_color_name: str = "",
    apply_beard_edit: bool = False,
) -> str:
    normalized_hair_color = (hair_color_name or "").strip()
    normalized_beard_color = (beard_color_name or "").strip()

    primary_goal_instruction = "Apply the hairstyle reference clearly on the selfie person. Do not leave the original hairstyle unchanged."

    identity_instruction = (
        "Keep identity and scene unchanged: face, skin tone, body, clothing, background, camera angle, and lighting must stay the same."
    )

    hairline_instruction = (
        "Keep the natural hairline geometry unchanged. Never invent a new hairline."
    )

    edit_scope_instruction = (
        "Edit only hair and beard areas requested below. Avoid extra edits or beauty filters."
    )

    hair_color_instruction = (
        f"Set scalp hair color to {normalized_hair_color}."
        if normalized_hair_color
        else "Keep scalp hair color natural."
    )

    beard_style_instruction = (
        "Also apply beard shape and density from the beard reference image."
        if include_beard_reference and apply_beard_edit
        else "Keep beard shape unchanged."
    )

    beard_color_instruction = (
        f"Set beard color to {normalized_beard_color}."
        if apply_beard_edit and normalized_beard_color
        else "Keep beard color natural."
    )

    if use_composite_input:
        if include_beard_reference:
            input_instruction = (
                "The input is a horizontal multi-panel image: LEFT is selfie, MIDDLE is hairstyle reference, RIGHT is beard reference."
            )
        else:
            input_instruction = (
                "The input is a two-panel image: LEFT is selfie and RIGHT is hairstyle reference."
            )
    else:
        if include_beard_reference:
            input_instruction = (
                "You are given three images: selfie, hairstyle reference, beard reference."
            )
        else:
            input_instruction = (
                "You are given two images: selfie and hairstyle reference."
            )

    output_instruction = "Return one final single portrait image only."

    return " ".join(
        part
        for part in (
            primary_goal_instruction,
            identity_instruction,
            hairline_instruction,
            edit_scope_instruction,
            hair_color_instruction,
            beard_style_instruction,
            beard_color_instruction,
            input_instruction,
            output_instruction,
        )
        if part
    )
