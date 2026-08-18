import unittest

from user_memory import (
    extract_explicit_preferences, format_profile, memory_command,
    profile_context, validate_preferences,
)


class UserMemoryTests(unittest.TestCase):
    def test_memory_commands(self):
        self.assertEqual(memory_command("Please remember my tax profile"), "enable")
        self.assertEqual(memory_command("What do you remember about me?"), "view")
        self.assertEqual(memory_command("Forget my profile"), "delete")

    def test_extracts_only_explicit_profile_statements(self):
        preferences = extract_explicit_preferences(
            "I am non-resident. My taxpayer type is company. "
            "My preferred tax year is 2025-26. I usually calculate VAT. "
            "My business sector is hospitality."
        )
        self.assertEqual(preferences["residency"], "non-resident")
        self.assertEqual(preferences["taxpayer_type"], "company")
        self.assertEqual(preferences["preferred_tax_year"], "2025/26")
        self.assertEqual(preferences["frequent_tax"], "vat")
        self.assertEqual(preferences["business_sector"], "hospitality")
        self.assertEqual(extract_explicit_preferences("Does a company pay VAT?"), {})

    def test_rejects_unapproved_profile_values(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_preferences({"residency": "maybe"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_preferences({"unknown_field": "secret"})

    def test_profile_context_forbids_silent_tax_decisions(self):
        context = profile_context({"residency": "resident"})
        self.assertIn("confirm material facts", context)
        self.assertIn("Residency", format_profile({"residency": "resident"}))


if __name__ == "__main__":
    unittest.main()
