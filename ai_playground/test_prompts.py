from django.test import SimpleTestCase

from .prompts import (
    PROMPT_STYLE_FLASH,
    PROMPT_STYLE_PRO,
    build_hair_transformation_prompt,
)


class HairTransformationPromptTests(SimpleTestCase):
    def test_flash_prompt_is_direct_and_compact(self):
        prompt = build_hair_transformation_prompt(prompt_style=PROMPT_STYLE_FLASH)
        lowered = prompt.lower()
        self.assertIn("use image 2 as the haircut target for image 1", lowered)
        self.assertIn("fully replace the current hairstyle in image 1", lowered)
        self.assertIn("keep face, skin tone, body, and clothing unchanged", lowered)
        self.assertIn("return one realistic portrait image only", lowered)
        self.assertNotIn("execution guidelines", lowered)
        self.assertNotIn("strict constraints", lowered)

    def test_flash_composite_prompt_mentions_left_right_panels(self):
        prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_FLASH,
            use_composite_input=True,
        )
        lowered = prompt.lower()
        self.assertIn("input: two-panel image", lowered)
        self.assertIn("left is selfie", lowered)
        self.assertIn("right is hairstyle reference", lowered)

    def test_pro_prompt_keeps_structured_rules(self):
        prompt = build_hair_transformation_prompt(prompt_style=PROMPT_STYLE_PRO)
        lowered = prompt.lower()
        self.assertIn("operation: hair replacement", lowered)
        self.assertIn("execution guidelines", lowered)
        self.assertIn("strict constraints", lowered)
        self.assertIn("you may alter the hairline", lowered)

    def test_flash_prompt_set_2_pushes_for_visible_change(self):
        prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_FLASH,
            prompt_set=2,
        )
        lowered = prompt.lower()
        self.assertIn("if the result looks unchanged, regenerate with stronger replacement", lowered)
        self.assertIn("hard edit: completely remove the current scalp hair", lowered)

    def test_pro_prompt_set_3_requires_visible_haircut_change(self):
        prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_PRO,
            prompt_set=3,
        )
        lowered = prompt.lower()
        self.assertIn("output must show a visible haircut change", lowered)

    def test_flash_prompt_set_5_is_concise_and_hair_only(self):
        prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_FLASH,
            prompt_set=5,
        )
        lowered = prompt.lower()
        self.assertIn("change only the scalp hair in image 1", lowered)
        self.assertIn("reference haircut is the source of truth", lowered)
        self.assertIn("match the reference overall silhouette", lowered)

    def test_invalid_prompt_set_falls_back_to_default_set(self):
        default_prompt = build_hair_transformation_prompt(prompt_style=PROMPT_STYLE_FLASH, prompt_set=1)
        invalid_prompt = build_hair_transformation_prompt(prompt_style=PROMPT_STYLE_FLASH, prompt_set=99)
        self.assertEqual(default_prompt, invalid_prompt)

    def test_prompt_mentions_beard_reference_when_enabled(self):
        flash_prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_FLASH,
            use_composite_input=True,
            include_beard_reference=True,
            apply_beard_edit=True,
            beard_color_name="Dark Brown",
        )
        pro_prompt = build_hair_transformation_prompt(
            prompt_style=PROMPT_STYLE_PRO,
            use_composite_input=True,
            include_beard_reference=True,
            apply_beard_edit=True,
            beard_color_name="Dark Brown",
        )

        self.assertIn("right is beard reference", flash_prompt.lower())
        self.assertIn("use image 3 as beard reference", flash_prompt.lower())
        self.assertIn("set beard color to dark brown", flash_prompt.lower())
        self.assertIn("image 3 (right): the beard reference", pro_prompt.lower())
        self.assertIn("replace beard shape using image 3", pro_prompt.lower())
        self.assertIn("set beard color to dark brown", pro_prompt.lower())
