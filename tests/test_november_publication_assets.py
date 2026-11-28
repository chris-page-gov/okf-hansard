from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import publish_november
from build import BUILD_ARTIFACTS
from descriptor_policy import MAX_DESCRIPTOR_BYTES


class NovemberPublicationAssetsTests(unittest.TestCase):
    def site(self, root, *, omit=()):
        names = [name for name in publish_november.REQUIRED_NOVEMBER_ASSETS
                 if name not in {"checksums.json", *omit}]
        names.append("history/days/2026-11-24.json")
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("asset:" + name).encode()
            path.write_bytes(raw)
        graph = {"schema": "okf-explorer-large-corpus.v1", "kind": "okf-large-corpus",
                 "id": "urn:test", "version": "0.3.0", "snapshot": "hansard-sha256-test", "okf_version": "0.3"}
        graph_raw = json.dumps(graph, sort_keys=True).encode()
        (root / "graph/okf-explorer.json").write_bytes(graph_raw)
        core = {"okf_version": "0.3", "snapshot": "core-test"}
        core_raw = json.dumps(core, sort_keys=True).encode()
        (root / "okf-core.json").write_bytes(core_raw)
        (root / "core-walkthrough.json").write_text(json.dumps({
            "descriptor_sha256": publish_november.sha(core_raw)}), encoding="utf-8")
        coverage = {"semantic_graph": {"sha256": "yaml-test"}}
        (root / "coverage.json").write_text(json.dumps(coverage), encoding="utf-8")
        (root / "walkthrough.json").write_text(json.dumps({
            "descriptor_sha256": publish_november.sha(graph_raw),
            "expected_identity": {key: graph[key] for key in ("schema", "id", "version", "snapshot")}}),
            encoding="utf-8")
        catalogue = {}
        for name in names:
            raw = (root / name).read_bytes()
            catalogue[name] = {"bytes": len(raw), "sha256": publish_november.sha(raw)}
        (root / "checksums.json").write_text(json.dumps(catalogue), encoding="utf-8")
        for name in omit:
            (root / name).unlink(missing_ok=True)

    def release(self, path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "receipt.json").write_text(json.dumps({"artifacts": {
            "okf-bundle.json": {"sha256": "test"},
            "okf-bundle.yamlld": {"sha256": "yaml-test"}}}), encoding="utf-8")
        return path

    def builder_root(self, root):
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "site_generator.py").write_text("VERSION = 1\n", encoding="utf-8")
        return root

    def test_complete_site_requires_and_checks_every_entry_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.site(root)
            catalogue = publish_november.validate_november_site(root, "2026-11-24")
            self.assertIn("core-walkthrough.html", catalogue)
            self.assertIn("history/days/2026-11-24.json", catalogue)

    def test_incomplete_cached_site_missing_compact_and_walkthroughs_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.site(root, omit=("okf-core.json", "walkthrough.html", "core-walkthrough.html"))
            with self.assertRaisesRegex(ValueError, "okf-core.json.*walkthrough.html.*core-walkthrough.html"):
                publish_november.validate_november_site(root, "2026-11-24")

    def test_tampered_required_asset_is_rejected_before_publication_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.site(root)
            (root / "walkthrough.html").write_text("changed", encoding="utf-8")
            with mock.patch.object(publish_november, "pages_lock") as lock, \
                    mock.patch.object(publish_november, "git") as git:
                with self.assertRaisesRegex(ValueError, "walkthrough.html"):
                    publish_november.publish(root, Path(directory) / "checkout", "2026-11-24", {})
                lock.assert_not_called()
                git.assert_not_called()

    def test_oversized_descriptor_is_rejected_before_publication_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = root / "graph/okf-explorer.json"
            descriptor.parent.mkdir(parents=True)
            with descriptor.open("wb") as stream:
                stream.truncate(MAX_DESCRIPTOR_BYTES + 1)
            with mock.patch.object(publish_november, "pages_lock") as lock, \
                    mock.patch.object(publish_november, "git") as git:
                with self.assertRaisesRegex(ValueError, "pinned Reader limit"):
                    publish_november.publish(root, root / "checkout", "2026-11-24", {})
                lock.assert_not_called()
                git.assert_not_called()

    def test_valid_files_from_a_different_release_are_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            site.mkdir()
            self.site(site)
            release = self.release(root / "release")
            receipt = json.loads((release / "receipt.json").read_bytes())
            receipt["artifacts"]["okf-bundle.json"]["sha256"] = "different"
            (release / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different verified release"):
                publish_november.validate_november_site(site, "2026-11-24", release)

    def test_unlisted_site_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.site(root)
            (root / "stale.html").write_text("unlisted", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"unlisted=\['stale.html'\]"):
                publish_november.validate_november_site(root, "2026-11-24")

    def test_missing_prepared_cache_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.site(root)
            with self.assertRaisesRegex(ValueError, "no site cache identity"):
                publish_november.validate_november_site(root, "2026-11-24", expected_identity=None,
                                                        require_identity=True)

    def test_refresh_resumes_from_a_prepared_release(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            through = "2026-11-25"
            work = state / "publication-attempts" / through / "071500"
            release, days, site = work / "release", work / "days", work / "site"
            identity = {"fixture": True}
            current = {"format": publish_november.CORE_VERSION, "through": through, "days": str(days),
                       "release": str(release), "site": str(site), "site_identity": identity}
            pointer = state / "publication.json"
            publish_november.dump(pointer, {"through": "2026-11-24", "provisional": False})
            publish_november.dump(work / "prepared.json", current)
            publish_november.dump(days / f"{through}.json", {"publication_status": "observed"})
            release.mkdir()
            artifacts = {}
            for name in BUILD_ARTIFACTS:
                body = name.encode()
                (release / name).write_bytes(body)
                artifacts[name] = {"bytes": len(body), "sha256": publish_november.sha(body)}
            receipt = {"schema": "hansard-build-receipt.v1", "okf_version": publish_november.CORE_VERSION,
                       "week_contributions_by_day": {through: 1}, "artifacts": artifacts}
            catalogue = {"index.html": {"bytes": 10}}
            checkout = state / "pages-checkout"
            with mock.patch.object(publish_november, "datetime") as clock, \
                    mock.patch.object(publish_november, "prepare") as prepare, \
                    mock.patch.object(publish_november, "collect") as collect, \
                    mock.patch.object(publish_november, "validate_november_site", return_value=catalogue), \
                    mock.patch.object(publish_november, "publish", return_value={"commit": "verified"}) as publish, \
                    mock.patch.object(publish_november, "write_current_receipt",
                                      side_effect=lambda _, path, receipt: publish_november.dump(path, receipt)):
                clock.now.return_value = datetime(2026, 11, 26, tzinfo=publish_november.ZONE)
                bad_receipts = (
                    ({**receipt, "okf_version": "0.2"}, "incompatible schema or OKF version"),
                    ({**receipt, "artifacts": {}}, "missing required artefacts"),
                )
                for bad, diagnostic in bad_receipts:
                    publish_november.dump(release / "receipt.json", bad)
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        publish_november.run(state, checkout)
                publish_november.dump(release / "receipt.json", receipt)
                artifact = release / "okf-bundle.json"
                artifact.write_bytes(b"x" * artifact.stat().st_size)
                with self.assertRaisesRegex(ValueError, "Artefact integrity mismatch"):
                    publish_november.run(state, checkout)
                prepare.assert_not_called()
                collect.assert_not_called()
                publish.assert_not_called()
                artifact.write_bytes(artifact.name.encode())
                publish_november.dump(release / "backfill/manifest.json", {"exceptions": {}})
                publish_november.run(state, checkout)
            prepare.assert_not_called()
            publish.assert_called_once_with(site, checkout, through, catalogue, release, identity)
            self.assertEqual(publish_november.read(pointer), {**current, "commit": "verified", "provisional": False})

    def test_builder_source_change_invalidates_saved_cache_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            site.mkdir()
            self.site(site)
            release = self.release(root / "release")
            self.builder_root(root)
            identity = publish_november.site_cache_identity(site, release, "2026-11-24", root=root)
            (root / "scripts/site_generator.py").write_text("VERSION = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cache identity"):
                publish_november.validate_november_site(site, "2026-11-24", release, identity, root=root)

    def test_unchanged_site_cache_identity_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            site.mkdir()
            self.site(site)
            release = self.release(root / "release")
            self.builder_root(root)
            identity = publish_november.site_cache_identity(site, release, "2026-11-24", root=root)
            checked = publish_november.validate_november_site(
                site, "2026-11-24", release, identity, require_identity=True, root=root)
            self.assertEqual(len(checked), len(publish_november.REQUIRED_NOVEMBER_ASSETS))

    def test_profile_and_static_input_changes_invalidate_saved_identity(self):
        for relative in ("profile/vocabulary.yaml", "docs/pages/additional.css"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                site = root / "site"
                site.mkdir()
                self.site(site)
                release = self.release(root / "release")
                self.builder_root(root)
                changed = root / relative
                changed.parent.mkdir(parents=True, exist_ok=True)
                changed.write_text("original", encoding="utf-8")
                identity = publish_november.site_cache_identity(site, release, "2026-11-24", root=root)
                changed.write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "cache identity"):
                    publish_november.validate_november_site(site, "2026-11-24", release, identity, root=root)

    def test_asset_edit_with_recomputed_catalogue_invalidates_saved_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            site.mkdir()
            self.site(site)
            release = self.release(root / "release")
            self.builder_root(root)
            identity = publish_november.site_cache_identity(site, release, "2026-11-24", root=root)
            (site / "index.html").write_text("edited but recatalogued", encoding="utf-8")
            publish_november.checksums(site)
            with self.assertRaisesRegex(ValueError, "cache identity"):
                publish_november.validate_november_site(site, "2026-11-24", release, identity, root=root)


if __name__ == "__main__":
    unittest.main()
