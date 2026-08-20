import unittest

from migrate_pgvector_to_chroma import _metadata


class ChromaMigrationTests(unittest.TestCase):
    def test_metadata_replaces_none_and_preserves_scalars(self):
        self.assertEqual(
            _metadata(
                {
                    "section": None,
                    "chunk_index": 4,
                    "source": "local",
                    "verified": True,
                }
            ),
            {
                "section": "",
                "chunk_index": 4,
                "source": "local",
                "verified": True,
            },
        )

    def test_metadata_serializes_nested_values(self):
        result = _metadata({"dates": ["2026-07-01", "2027-06-30"]})
        self.assertEqual(result["dates"], '["2026-07-01", "2027-06-30"]')

    def test_non_dictionary_metadata_becomes_empty(self):
        self.assertEqual(_metadata(None), {})


if __name__ == "__main__":
    unittest.main()
