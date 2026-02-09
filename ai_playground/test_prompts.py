from django.test import SimpleTestCase

from .prompts import build_hair_transformation_prompt


class HairTransformationPromptTests(SimpleTestCase):
    def test_prompt_enforces_identity_and_hairline_constraints(self):
        prompt = build_hair_transformation_prompt()
        self.assertIn("selfie is the identity anchor", prompt.lower())
        self.assertIn("natural hairline geometry unchanged", prompt.lower())
        self.assertIn("never invent a new hairline", prompt.lower())
        self.assertIn("do not keep the original hairstyle unchanged", prompt.lower())

    def test_composite_prompt_mentions_left_right_panels(self):
        prompt = build_hair_transformation_prompt(use_composite_input=True)
        self.assertIn("left panel is the visitor selfie", prompt.lower())
        self.assertIn("right panel is the haircut reference", prompt.lower())
