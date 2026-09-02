"""Proof that stack-watch judges correctly, and refuses to escalate on thin evidence.

The rules here are DATA, so most of the risk is not "does the check work" but "does a
badly-written or half-filled norm do something dangerous". Those are the cases below:
an absent tier, a misspelled tier, a broken exempt pattern, and a promotion gate asked
to approve a sample of two.

Names are invented — this file ships to a public mirror, and a fixture is the easiest
place for a real internal name to slip through.

Stdlib unittest, no network, no graph. Run: python3 -m unittest
"""
import unittest

import stack_watch as sw

NS = "https://example.invalid/ontology/"


def norm(**kw):
    base = dict(name="n1", label="L", check="path_present", target="CI.yml",
                tier=sw.TIER_ADVISE)
    base.update(kw)
    return sw.Norm(**base)


class TestNormQuery(unittest.TestCase):
    def test_is_one_line_with_prefixes(self):
        q = sw.norm_query(NS)
        self.assertNotIn("\n", q)
        self.assertIn("PREFIX rdfs:", q)
        self.assertIn(f"PREFIX a: <{NS}>", q)

    def test_is_distinct(self):
        self.assertIn("SELECT DISTINCT", sw.norm_query(NS))

    def test_only_check_and_target_are_required(self):
        # A norm missing its prose is still a norm; it must not vanish from the pass
        # because nobody wrote a comment.
        q = sw.norm_query(NS)
        self.assertIn("a:normCheck ?check", q)
        self.assertIn("OPTIONAL { ?n rdfs:comment ?comment }", q)
        self.assertIn("OPTIONAL { ?n a:enforcementTier ?tier }", q)


class TestNormsOf(unittest.TestCase):
    def test_reads_a_full_row(self):
        n = sw.norms_of([{"n": NS + "norm_ci", "label": "CI present",
                          "check": "path_present", "target": ".github",
                          "tier": "block", "source": "x-1"}])[0]
        self.assertEqual((n.name, n.tier, n.source), ("norm_ci", "block", "x-1"))
        self.assertTrue(n.enforcing)

    def test_ABSENT_tier_advises_it_does_not_block(self):
        # The dangerous default. A norm whose tier nobody set must not enforce.
        n = sw.norms_of([{"n": NS + "n", "check": "path_present", "target": "x"}])[0]
        self.assertEqual(n.tier, sw.TIER_ADVISE)
        self.assertFalse(n.enforcing)

    def test_MISSPELLED_tier_does_not_enforce(self):
        # `tier != advise` would make a typo start blocking work. Only the graph's
        # explicit enforce value enforces.
        self.assertFalse(norm(tier="blcok").enforcing)
        self.assertFalse(norm(tier="enforce").enforcing)
        self.assertTrue(norm(tier="block").enforcing)

    def test_rows_without_a_name_are_skipped(self):
        self.assertEqual(sw.norms_of([{"check": "path_present", "target": "x"}]), [])


class TestApplicability(unittest.TestCase):
    def test_no_exempt_applies_everywhere(self):
        self.assertTrue(norm().applies_to("alpha"))

    def test_exempt_regex_excludes(self):
        n = norm(exempt="^doc")
        self.assertFalse(n.applies_to("docs-site"))
        self.assertTrue(n.applies_to("alpha"))

    def test_a_BROKEN_exempt_pattern_raises_rather_than_widening(self):
        # Silently ignoring a bad pattern would apply the norm to repos its author
        # meant to exclude — a data typo becoming a wave of false findings.
        with self.assertRaises(sw.NormError):
            norm(exempt="[unclosed").applies_to("alpha")


class TestConsistency(unittest.TestCase):
    PATHS = {"alpha": [".github/workflows/ci.yml", "README.md"],
             "beta": ["README.md"]}

    def test_finds_the_repo_missing_the_file(self):
        d = sw.consistency([norm(target=".github/workflows/ci.yml")], self.PATHS)
        self.assertEqual([x.repo for x in d], ["beta"])

    def test_basename_match_counts(self):
        d = sw.consistency([norm(target="ci.yml")], self.PATHS)
        self.assertEqual([x.repo for x in d], ["beta"])

    def test_trailing_glob_matches_a_prefix(self):
        d = sw.consistency([norm(target=".github/*")], self.PATHS)
        self.assertEqual([x.repo for x in d], ["beta"])

    def test_path_absent_check_is_the_inverse(self):
        d = sw.consistency([norm(check="path_absent", target="README.md")], self.PATHS)
        self.assertEqual(sorted(x.repo for x in d), ["alpha", "beta"])

    def test_exempt_repo_produces_no_deviation(self):
        d = sw.consistency([norm(target="ci.yml", exempt="^beta$")], self.PATHS)
        self.assertEqual(d, [])

    def test_deviation_carries_its_norms_tier(self):
        d = sw.consistency([norm(target="ci.yml", tier="block")], self.PATHS)
        self.assertTrue(d[0].enforcing)


class TestLeverage(unittest.TestCase):
    CONSUMERS = {"alpha": ["uses widgetlib for things"],
                 "beta": ["no mention here"],
                 "gamma": ["WidgetLib, capitalised differently"]}

    def test_finds_only_the_silent_consumer(self):
        self.assertEqual(sw.leverage_gaps("widgetlib", "alpha", self.CONSUMERS), ["beta"])

    def test_is_case_insensitive(self):
        # gamma mentions it with different capitalisation and is NOT a gap.
        self.assertNotIn("gamma", sw.leverage_gaps("widgetlib", "alpha", self.CONSUMERS))

    def test_the_producer_is_never_its_own_gap(self):
        self.assertNotIn("alpha", sw.leverage_gaps("widgetlib", "alpha", self.CONSUMERS))

    def test_empty_capability_finds_nothing(self):
        self.assertEqual(sw.leverage_gaps("", "alpha", self.CONSUMERS), [])


class TestDriftedTwins(unittest.TestCase):
    def test_identical_copies_are_NOT_reported(self):
        # A deliberately shared file is a convention, not a defect. Reporting every
        # duplicate would bury the drift in the list meant to reveal it.
        files = {"a": {"shared.md": "h1"}, "b": {"shared.md": "h1"}}
        self.assertEqual(sw.drifted_twins(files), [])

    def test_divergent_copies_ARE_reported(self):
        files = {"a": {"shared.md": "h1"}, "b": {"shared.md": "h2"}}
        self.assertEqual(sw.drifted_twins(files), [("shared.md", ["a", "b"])])

    def test_a_file_in_one_repo_only_is_not_a_twin(self):
        self.assertEqual(sw.drifted_twins({"a": {"solo.md": "h1"}}), [])

    def test_three_repos_two_hashes_still_drifts(self):
        files = {"a": {"s": "h1"}, "b": {"s": "h1"}, "c": {"s": "h2"}}
        self.assertEqual(sw.drifted_twins(files), [("s", ["a", "b", "c"])])


class TestFPLedger(unittest.TestCase):
    def test_unmeasured_is_None_NOT_zero(self):
        # The whole point: an unmeasured rate must not read as a perfect one.
        self.assertIsNone(sw.FPLedger().rate)
        self.assertIn("UNMEASURED", sw.FPLedger().line())

    def test_rate_is_computed_from_verdicts(self):
        led = sw.FPLedger()
        for i in range(3):
            led.record(f"c{i}", True)
        led.record("f0", False)
        self.assertAlmostEqual(led.rate, 0.25)
        self.assertIn("25%", led.line())


class TestPromotionGate(unittest.TestCase):
    def _ledger(self, confirmed, fp=0):
        led = sw.FPLedger()
        for i in range(confirmed):
            led.record(f"c{i}", True)
        for i in range(fp):
            led.record(f"f{i}", False)
        return led

    def test_refuses_when_nothing_was_measured(self):
        ok, why = sw.gate_promotion(sw.FPLedger())
        self.assertFalse(ok)
        self.assertIn("nothing has been measured", why)

    def test_refuses_a_SMALL_sample_of_zeros(self):
        # A quiet week is not a soak. This is the arm that stops a norm being
        # promoted to blocking on two lucky findings.
        ok, why = sw.gate_promotion(self._ledger(2))
        self.assertFalse(ok)
        self.assertIn("floor", why)

    def test_refuses_a_nonzero_rate(self):
        ok, why = sw.gate_promotion(self._ledger(9, fp=1))
        self.assertFalse(ok)
        self.assertIn("not zero", why)

    def test_ALLOWS_a_real_soak(self):
        ok, why = sw.gate_promotion(self._ledger(6))
        self.assertTrue(ok)
        self.assertIn("0 false positives", why)


class TestLenses(unittest.TestCase):
    def test_order(self):
        self.assertEqual(sw.LENSES, ("consistency", "leverage", "gaps"))


if __name__ == "__main__":
    unittest.main()
