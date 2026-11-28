import json
import tempfile
import unittest
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic

from build import CONTEXT
from okf_core import applicable_context, write_release_markdown


class ApplicableContextTests(unittest.TestCase):
    def test_production_context_preserves_type_and_inserted_nested_source_terms(self):
        fields = {
            "@id": "urn:okf:hansard:record:example",
            "@type": "hansard:Contribution",
            "title": "Example contribution",
            "details": {"display": "A nested JSON literal"},
            "resource": "https://example.test/record",
            "sources": [{"id": "record", "resource": "https://example.test/record"}],
        }
        reduced = applicable_context(fields, CONTEXT)
        self.assertIn("hansard", reduced)
        self.assertIn("resource", reduced)

        full_graph = Graph().parse(data=json.dumps({"@context": CONTEXT, **fields}), format="json-ld")
        reduced_graph = Graph().parse(data=json.dumps({"@context": reduced, **fields}), format="json-ld")
        self.assertTrue(isomorphic(full_graph, reduced_graph))

    def test_retains_only_used_terms_and_required_prefixes_without_changing_expansion(self):
        context = {
            "@version": 1.1, "@vocab": "https://example.test/field:",
            "dct": "http://purl.org/dc/terms/", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "prov": "http://www.w3.org/ns/prov#", "title": "dct:title",
            "source": {"@id": "rdf:subject", "@type": "@id"},
            "evidence": {"@id": "prov:hadPrimarySource", "@container": "@set"},
            "unrelated": {"@id": "dct:description", "@type": "@json"},
        }
        fields = {"title": "Example", "source": "https://example.test/source", "extension": {"x": 1}}
        reduced = applicable_context(fields, context)

        self.assertEqual(set(reduced), {"@version", "@vocab", "dct", "rdf", "prov", "title", "source"})
        self.assertEqual(reduced["title"], context["title"])
        self.assertEqual(reduced["source"], context["source"])
        self.assertEqual(reduced["@vocab"], context["@vocab"])
        full_graph = Graph().parse(data=json.dumps({"@context": context, **fields}), format="json-ld")
        reduced_graph = Graph().parse(data=json.dumps({"@context": reduced, **fields}), format="json-ld")
        self.assertTrue(isomorphic(full_graph, reduced_graph))

    def test_writer_uses_reduced_context_in_each_record(self):
        context = {"@version": 1.1, "@vocab": "https://example.test/field:",
                   "dct": "http://purl.org/dc/terms/", "title": "dct:title",
                   "unused": {"@id": "dct:description", "@type": "@json"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_markdown(root, {"debate/example.md": {
                "title": "Example", "date": "2006-04-18", "body": "Text"}},
                "2006-04-18", "2006-04-18", "Test", context)
            text = (root / "debate/example.md").read_text(encoding="utf-8")
            fields = json.loads(text.split("\n", 2)[1])
            self.assertEqual(fields["@context"], {
                "@version": 1.1, "@vocab": context["@vocab"], "dct": context["dct"],
                "title": context["title"]})


if __name__ == "__main__":
    unittest.main()
