"""Unit tests for selfverify.metric_versions — M2.5 metric family versioning.

Zero-dependency: unittest only, runs via
    python -m unittest discover -s tests

Covers:
  - Version parsing, comparison, ordering, hashing
  - MetricFamily add/get metric
  - check_compatibility: same version, minor bump, breaking minor, major bump
  - get_migration_path for direct and cross-major jumps
  - compute_metric_fingerprint determinism and tamper detection
  - registry register/get/list/unregister
  - register_default_families seeds the three default families
"""
from __future__ import annotations

import unittest

from selfverify.metric_versions import (
    Version,
    MetricDefinition,
    MetricFamily,
    register_family,
    unregister_family,
    get_family,
    list_families,
    check_compatibility,
    get_migration_path,
    compute_metric_fingerprint,
    compute_family_fingerprint,
    register_default_families,
    _REGISTRY,
)


class TestVersion(unittest.TestCase):
    def test_str_round_trips(self):
        self.assertEqual(str(Version(1, 2, 3)), "1.2.3")
        self.assertEqual(str(Version(1)), "1.0.0")

    def test_parse_full(self):
        v = Version.parse("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))

    def test_parse_two_components(self):
        v = Version.parse("1.2")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 0))

    def test_parse_single_component(self):
        v = Version.parse("3")
        self.assertEqual((v.major, v.minor, v.patch), (3, 0, 0))

    def test_parse_invalid_raises(self):
        with self.assertRaises(ValueError):
            Version.parse("1.2.3.4")

    def test_negative_components_rejected(self):
        with self.assertRaises(ValueError):
            Version(-1, 0, 0)

    def test_ordering_major_dominates(self):
        self.assertLess(Version(1, 9, 9), Version(2, 0, 0))

    def test_ordering_minor_dominates(self):
        self.assertLess(Version(1, 2, 0), Version(1, 3, 0))

    def test_ordering_patch(self):
        self.assertLess(Version(1, 2, 3), Version(1, 2, 4))

    def test_equality(self):
        self.assertEqual(Version(1, 2, 3), Version(1, 2, 3))

    def test_hashable(self):
        # Version is used as a set/dict key in the migration path logic.
        s = {Version(1, 0, 0), Version(1, 0, 0), Version(2, 0, 0)}
        self.assertEqual(len(s), 2)

    def test_to_dict(self):
        self.assertEqual(Version(1, 2, 3).to_dict(),
                         {"major": 1, "minor": 2, "patch": 3})


class TestMetricFamily(unittest.TestCase):
    def test_add_and_get_metric(self):
        fam = MetricFamily(name="f", version=Version(1), description="d")
        fam.add_metric(MetricDefinition(name="m1", version=Version(1),
                                         description="d", formula="x"))
        m = fam.get_metric("m1")
        self.assertIsNotNone(m)
        self.assertEqual(m.name, "m1")

    def test_get_missing_metric_returns_none(self):
        fam = MetricFamily(name="f", version=Version(1), description="d")
        self.assertIsNone(fam.get_metric("nope"))

    def test_to_dict_includes_metrics_and_version_string(self):
        fam = MetricFamily(name="f", version=Version(1, 0, 0), description="d")
        fam.add_metric(MetricDefinition(name="m1", version=Version(1, 0, 0),
                                         description="d", formula="x"))
        d = fam.to_dict()
        self.assertEqual(d["name"], "f")
        self.assertEqual(d["version"], "1.0.0")
        self.assertEqual(len(d["metrics"]), 1)
        self.assertEqual(d["metrics"][0]["name"], "m1")


class TestRegistry(unittest.TestCase):
    def setUp(self):
        # Isolate: clear any default families the module-level import may have added.
        self._backup = dict(_REGISTRY)
        _REGISTRY.clear()

    def tearDown(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._backup)

    def test_register_and_get(self):
        fam = MetricFamily(name="fam_x", version=Version(1), description="d")
        register_family(fam)
        self.assertIs(get_family("fam_x"), fam)

    def test_list_families_is_sorted(self):
        register_family(MetricFamily(name="zeta", version=Version(1), description="d"))
        register_family(MetricFamily(name="alpha", version=Version(1), description="d"))
        self.assertEqual(list_families(), ["alpha", "zeta"])

    def test_unregister_returns_family_and_removes_it(self):
        fam = MetricFamily(name="temp", version=Version(1), description="d")
        register_family(fam)
        self.assertIs(unregister_family("temp"), fam)
        self.assertIsNone(get_family("temp"))

    def test_unregister_absent_returns_none(self):
        self.assertIsNone(unregister_family("nope"))


class TestCheckCompatibility(unittest.TestCase):
    def setUp(self):
        self._backup = dict(_REGISTRY)
        _REGISTRY.clear()

    def tearDown(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._backup)

    def test_unregistered_family_is_incompatible(self):
        r = check_compatibility("ghost", "1.0.0", "1.1.0")
        self.assertFalse(r.compatible)
        self.assertEqual(r.compatibility_level, "none")

    def test_same_version_is_fully_compatible(self):
        fam = MetricFamily(name="fam", version=Version(1), description="d")
        register_family(fam)
        r = check_compatibility("fam", "1.0.0", "1.0.0")
        self.assertTrue(r.compatible)
        self.assertEqual(r.compatibility_level, "full")

    def test_backward_minor_bump_is_fully_compatible(self):
        fam = MetricFamily(name="fam", version=Version(1), description="d",
                            compatibility={"1.1.0": "new feature; no break"})
        register_family(fam)
        r = check_compatibility("fam", "1.0.0", "1.1.0")
        self.assertTrue(r.compatible)
        self.assertEqual(r.compatibility_level, "full")

    def test_breaking_minor_bump_reports_partial(self):
        fam = MetricFamily(
            name="fam", version=Version(1), description="d",
            compatibility={"1.1.0": "BREAKING: renamed API"},
            migrations={"1.1.0": "run the migration script"},
        )
        register_family(fam)
        r = check_compatibility("fam", "1.0.0", "1.1.0")
        self.assertFalse(r.compatible)
        self.assertEqual(r.compatibility_level, "partial")
        self.assertTrue(r.migration_required)
        self.assertEqual(r.migration_notes, "run the migration script")

    def test_major_bump_reports_none(self):
        fam = MetricFamily(name="fam", version=Version(2), description="d",
                            compatibility={"2.0.0": "major overhaul"})
        register_family(fam)
        r = check_compatibility("fam", "1.0.0", "2.0.0")
        self.assertFalse(r.compatible)
        self.assertEqual(r.compatibility_level, "none")

    def test_backward_direction_is_incompatible(self):
        fam = MetricFamily(name="fam", version=Version(2), description="d",
                            compatibility={"2.0.0": "downgrade"})
        register_family(fam)
        r = check_compatibility("fam", "2.0.0", "1.0.0")
        self.assertFalse(r.compatible)


class TestMigrationPath(unittest.TestCase):
    def setUp(self):
        self._backup = dict(_REGISTRY)
        _REGISTRY.clear()

    def tearDown(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._backup)

    def test_direct_path_for_same_major(self):
        fam = MetricFamily(name="fam", version=Version(1), description="d",
                            compatibility={"1.0.0": "base", "1.1.0": "minor",
                                            "1.2.0": "minor"})
        register_family(fam)
        path = get_migration_path("fam", "1.0.0", "1.2.0")
        self.assertEqual(path, ["1.0.0", "1.2.0"])

    def test_unregistered_family_returns_empty(self):
        self.assertEqual(get_migration_path("ghost", "1.0.0", "2.0.0"), [])


class TestFingerprints(unittest.TestCase):
    def test_metric_fingerprint_is_deterministic(self):
        m1 = MetricDefinition(name="drop_magnitude", version=Version(1, 0, 0),
                               description="d", formula="(a - b) / a")
        m2 = MetricDefinition(name="drop_magnitude", version=Version(1, 0, 0),
                               description="d", formula="(a - b) / a")
        self.assertEqual(compute_metric_fingerprint(m1), compute_metric_fingerprint(m2))

    def test_metric_fingerprint_detects_formula_change(self):
        m1 = MetricDefinition(name="m", version=Version(1, 0, 0),
                               description="d", formula="x")
        m2 = MetricDefinition(name="m", version=Version(1, 0, 0),
                               description="d", formula="y")
        self.assertNotEqual(compute_metric_fingerprint(m1), compute_metric_fingerprint(m2))

    def test_metric_fingerprint_ignores_dependencies_order(self):
        # dependencies are sorted before hashing → order-insensitive
        m1 = MetricDefinition(name="m", version=Version(1), description="d",
                               formula="x", dependencies=["a", "b"])
        m2 = MetricDefinition(name="m", version=Version(1), description="d",
                               formula="x", dependencies=["b", "a"])
        self.assertEqual(compute_metric_fingerprint(m1), compute_metric_fingerprint(m2))

    def test_family_fingerprint_changes_when_metrics_change(self):
        fam1 = MetricFamily(name="f", version=Version(1), description="d")
        fam1.add_metric(MetricDefinition(name="m", version=Version(1),
                                          description="d", formula="x"))
        fam2 = MetricFamily(name="f", version=Version(1), description="d")
        fam2.add_metric(MetricDefinition(name="m", version=Version(1),
                                          description="d", formula="y"))
        self.assertNotEqual(compute_family_fingerprint(fam1), compute_family_fingerprint(fam2))


class TestRegisterDefaultFamilies(unittest.TestCase):
    def test_three_default_families_are_registered(self):
        # Clear and re-register to be order-independent.
        _REGISTRY.clear()
        register_default_families()
        names = set(list_families())
        for expected in ("robustness", "recovery", "controllability"):
            self.assertIn(expected, names)

    def test_default_families_have_real_metrics(self):
        _REGISTRY.clear()
        register_default_families()
        fam = get_family("recovery")
        self.assertIsNotNone(fam)
        names = {m.name for m in fam.metrics}
        self.assertIn("recovery_AUC", names)
        self.assertIn("t_half", names)


if __name__ == "__main__":
    unittest.main()
