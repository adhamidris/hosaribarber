def build_hair_transformation_prompt(
    *,
    use_composite_input: bool = False,
) -> str:
    primary_goal_instruction = (
        "Primary objective: produce a visibly different haircut on the selfie subject based on the reference style. "
        "Do not keep the original hairstyle unchanged."
    )

    identity_instruction = (
        "Create a photorealistic haircut simulation for a barbershop consultation. "
        "The selfie is the identity anchor and geometry source of truth. "
        "Preserve identity exactly: keep face shape, forehead proportions, skin tone, eyes, nose, mouth, "
        "ears, expression, and head pose unchanged."
    )

    hairline_instruction = (
        "Critical rule: keep the subject's natural hairline geometry unchanged. "
        "Do not move, redraw, raise, or lower the frontal hairline, temple corners, recession pattern, "
        "sideburn roots, or nape origin. Never invent a new hairline."
    )

    edit_scope_instruction = (
        "Edit only hair attributes from the reference: hairstyle silhouette, length, taper/fade pattern, "
        "texture, volume, curl/straight direction, and edge detailing. "
        "Do not change eyebrows, beard, clothing, accessories, background, lens perspective, framing, or age."
    )

    transfer_strength_instruction = (
        "Hair transfer strength: medium-high. The final hairstyle should be clearly noticeable at first glance "
        "while still realistic and naturally blended."
    )

    realism_instruction = (
        "Match original lighting, white balance, shadows, grain/noise, and skin detail so the result appears "
        "as the same photo captured in the same moment. Avoid beauty-filter smoothing, plastic hair, "
        "CGI artifacts, text, watermark, and collage output."
    )

    feasibility_instruction = (
        "If the reference haircut conflicts with the subject's hairline or hair density, adapt the style "
        "to fit naturally on the subject while preserving the original hairline and identity. "
        "When exact replication is not feasible, prioritize the closest visibly similar hairstyle rather than a minimal/no-op edit."
    )

    if use_composite_input:
        input_instruction = (
            "The input image is a two-panel composition: LEFT panel is the visitor selfie, "
            "RIGHT panel is the haircut reference. Output a single portrait based on the LEFT subject "
            "with hairstyle characteristics from the RIGHT reference."
        )
    else:
        input_instruction = (
            "You are given two images: image one is the visitor selfie, image two is the haircut reference. "
            "Use image one as strict identity/geometry source and image two as hairstyle guidance only."
        )

    output_instruction = "Return one final single portrait image only."

    return " ".join(
        part
        for part in (
            primary_goal_instruction,
            identity_instruction,
            hairline_instruction,
            edit_scope_instruction,
            transfer_strength_instruction,
            realism_instruction,
            feasibility_instruction,
            input_instruction,
            output_instruction,
        )
        if part
    )
