from django.test import SimpleTestCase

from .prompts import build_hair_transformation_prompt


class HairTransformationPromptTests(SimpleTestCase):
    def test_prompt_enforces_identity_and_hairline_constraints(self):
        prompt = build_hair_transformation_prompt()
        self.assertIn("keep identity and scene unchanged", prompt.lower())
        self.assertIn("natural hairline geometry unchanged", prompt.lower())
        self.assertIn("never invent a new hairline", prompt.lower())
        self.assertIn("do not leave the original hairstyle unchanged", prompt.lower())
        self.assertIn("style lock (highest priority)", prompt.lower())
        self.assertIn("99.99% hairstyle fidelity", prompt.lower())
        self.assertIn("exact specification, not inspiration", prompt.lower())
        self.assertIn("do not output an alternate haircut", prompt.lower())
        self.assertIn("strict reference-check", prompt.lower())

    def test_composite_prompt_mentions_left_right_panels(self):
        prompt = build_hair_transformation_prompt(use_composite_input=True)
        self.assertIn("two-panel image", prompt.lower())
        self.assertIn("left is selfie", prompt.lower())
        self.assertIn("right is hairstyle reference", prompt.lower())

    def test_prompt_mentions_beard_reference_when_enabled(self):
        prompt = build_hair_transformation_prompt(
            use_composite_input=True,
            include_beard_reference=True,
            apply_beard_edit=True,
            beard_color_name="Dark Brown",
        )
        self.assertIn("right is beard reference", prompt.lower())
        self.assertIn("set beard color to dark brown", prompt.lower())
