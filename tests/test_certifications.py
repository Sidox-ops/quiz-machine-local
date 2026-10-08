from __future__ import annotations

import unittest

from backend.certifications import certification, public_certifications


class CertificationCatalogTests(unittest.TestCase):
    def test_exposes_the_supported_microsoft_ai_paths(self) -> None:
        catalog = public_certifications()

        self.assertEqual(
            [item["code"] for item in catalog],
            ["AI-901", "AI-103", "AI-200", "AI-300", "AI-500"],
        )
        for item in catalog:
            self.assertEqual(
                item["study_guide_url"].rsplit("/", maxsplit=1)[-1],
                item["code"].lower(),
            )
            self.assertTrue(item["domains"])

    def test_ai_500_uses_its_official_multi_agent_scope(self) -> None:
        selected = certification("ai-500")

        self.assertEqual(
            selected.title,
            "Designing and Implementing Multi-Agent AI Solutions",
        )
        self.assertIn("Architect multi-agent solutions", selected.domains)


if __name__ == "__main__":
    unittest.main()
