"""Proof that repo-watch's deterministic half behaves, including when it must refuse.

skein convention: a check that has never returned every one of its outcomes is not a
check. So each refusal below is exercised on purpose, not just the happy path — an
unresolvable repo, an ambiguous one, a duplicate, and a cap that bites.

The names used here are invented. This file ships to a public mirror, and a test
fixture is the easiest place for a real internal name to slip through.

Stdlib unittest — no pytest, no network, no graph. Run: python3 -m unittest
"""
import unittest

import repo_watch as rw

NS = "https://example.invalid/ontology/"


def compact(*rows):
    """The query endpoint's default response shape."""
    return {"count": len(rows), "rows": list(rows)}


def w3c(*rows):
    """The W3C SPARQL-results shape, returned when Accept asks for it."""
    return {
        "head": {"vars": ["owner", "state", "remote"]},
        "results": {
            "bindings": [
                {k: {"type": "uri", "value": v} for k, v in r.items()} for r in rows
            ]
        },
    }


class TestResolveQuery(unittest.TestCase):
    def test_is_one_line(self):
        # A JSON string cannot carry literal newlines, so a multi-line query fails
        # with a JSON parse error that says nothing about SPARQL.
        self.assertNotIn("\n", rw.resolve_query("alpha", NS))

    def test_carries_prefixes(self):
        # Bare rdfs:/skos: is a hard parse error; the endpoint declares nothing.
        q = rw.resolve_query("alpha", NS)
        self.assertIn("PREFIX rdfs:", q)
        self.assertIn("PREFIX skos:", q)
        self.assertIn(f"PREFIX a: <{NS}>", q)

    def test_is_distinct(self):
        # Denormalised aliases mean a name matches both label and altLabel of one
        # entity; without DISTINCT that reads as ambiguity.
        self.assertIn("SELECT DISTINCT", rw.resolve_query("alpha", NS))

    def test_uses_no_property_path(self):
        # The path-free form is total against denormalised aliases and does not
        # depend on how the endpoint evaluates zero-or-more paths.
        self.assertNotIn("*", rw.resolve_query("alpha", NS))

    def test_state_and_remotes_are_optional(self):
        # A repo with an owner but no recorded state must still resolve.
        q = rw.resolve_query("alpha", NS)
        self.assertIn("OPTIONAL { ?e a:ownershipState ?state }", q)
        self.assertIn("OPTIONAL { ?e a:hasRemoteHost ?remote }", q)

    def test_refuses_quote_injection(self):
        for bad in ['al"pha', "back\\slash"]:
            with self.assertRaises(ValueError):
                rw.resolve_query(bad, NS)

    def test_refuses_empty(self):
        with self.assertRaises(ValueError):
            rw.resolve_query("   ", NS)


class TestRowsOf(unittest.TestCase):
    def test_reads_compact_shape(self):
        self.assertEqual(rw.rows_of(compact({"owner": "x"})), [{"owner": "x"}])

    def test_reads_w3c_shape(self):
        self.assertEqual(rw.rows_of(w3c({"owner": "x"})), [{"owner": "x"}])

    def test_empty_and_junk_are_no_rows_not_a_crash(self):
        for junk in [{}, {"rows": None}, [], None, {"results": {}}]:
            self.assertEqual(rw.rows_of(junk), [])


class TestResolution(unittest.TestCase):
    def test_resolves_owner_state_and_remotes(self):
        r = rw.resolution_of(
            "alpha",
            compact(
                {"owner": NS + "ada", "state": "RULED", "remote": "forge.invalid"},
                {"owner": NS + "ada", "state": "RULED", "remote": "mirror.invalid"},
            ),
        )
        self.assertEqual(r.owner, "ada")
        self.assertEqual(r.ownership_state, "RULED")
        self.assertEqual(r.remotes, ["forge.invalid", "mirror.invalid"])
        self.assertTrue(r.ruled)

    def test_duplicate_rows_are_one_owner(self):
        # The un-deduplicated store genuinely returns the same owner repeatedly.
        r = rw.resolution_of("alpha", compact(*[{"owner": NS + "ada"}] * 3))
        self.assertEqual(r.owner, "ada")

    def test_owner_without_state_still_resolves_but_is_not_ruled(self):
        r = rw.resolution_of("alpha", compact({"owner": NS + "ada"}))
        self.assertEqual(r.owner, "ada")
        self.assertFalse(r.ruled)

    def test_no_owner_refuses_and_names_the_prose_cause(self):
        # The entity can exist, be well-formed, and still carry its owner only as
        # prose in a comment — which is invisible to SPARQL and looks like absence.
        with self.assertRaises(rw.ResolutionError) as e:
            rw.resolution_of("alpha", compact({"remote": "forge.invalid"}))
        self.assertIn("prose", str(e.exception))

    def test_empty_response_refuses(self):
        with self.assertRaises(rw.ResolutionError):
            rw.resolution_of("alpha", compact())

    def test_two_owners_refuses_rather_than_picking(self):
        with self.assertRaises(rw.ResolutionError) as e:
            rw.resolution_of(
                "alpha", compact({"owner": NS + "ada"}, {"owner": NS + "bo"})
            )
        self.assertIn("2 owners", str(e.exception))


class TestLocalName(unittest.TestCase):
    def test_splits_slash_and_hash(self):
        self.assertEqual(rw.local_name("https://example.invalid/o/ada"), "ada")
        self.assertEqual(rw.local_name("https://example.invalid/o#ada"), "ada")

    def test_passes_through_a_bare_name(self):
        self.assertEqual(rw.local_name("ada"), "ada")

    def test_none_stays_none(self):
        self.assertIsNone(rw.local_name(None))
        self.assertIsNone(rw.local_name(""))


class TestTokens(unittest.TestCase):
    def test_drops_stop_words_and_short_words(self):
        # "the", "is" and "of" go as stop-words; "out" stays, because it carries
        # meaning in plenty of titles and the expensive direction of this error is
        # dropping signal, not keeping noise.
        self.assertEqual(rw.tokens("the readme is out of date"), {"readme", "out", "date"})

    def test_drops_bead_ids(self):
        # Two findings citing the same source bead are not the same finding.
        self.assertNotIn("abcd-1x2y", rw.tokens("abcd-1x2y: readme drift"))

    def test_is_case_insensitive(self):
        self.assertEqual(rw.tokens("README Drift"), rw.tokens("readme drift"))


class TestDedupe(unittest.TestCase):
    CORPUS = [
        {"id": "x-1", "title": "README claims negation is rejected after it shipped"},
        {"id": "x-2", "title": "Signing banner says nothing built while v1 is live"},
        {"id": "x-3", "title": "Track pull request 99: release v0.3.28", "status": "closed"},
    ]

    def test_near_identical_title_is_a_duplicate(self):
        hit = rw.find_duplicate(
            "README still claims negation is rejected after it shipped", self.CORPUS
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "x-1")

    def test_unrelated_title_is_not_a_duplicate(self):
        self.assertIsNone(
            rw.find_duplicate("Container disk usage crosses its threshold", self.CORPUS)
        )

    def test_closed_beads_still_count_as_duplicates(self):
        # A gap fixed last week must not be re-minted this week.
        hit = rw.find_duplicate("Track pull request 99: release v0.3.28", self.CORPUS)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["status"], "closed")

    def test_corpus_entries_without_titles_are_survivable(self):
        self.assertIsNone(rw.find_duplicate("anything at all here", [{"id": "x"}, {}]))

    def test_empty_corpus_means_nothing_is_a_duplicate(self):
        self.assertIsNone(rw.find_duplicate("README drift", []))


class TestPartitionMints(unittest.TestCase):
    CORPUS = [{"id": "x-1", "title": "README claims negation is rejected"}]

    def test_splits_new_from_duplicate(self):
        mint, dupes, held = rw.partition_mints(
            ["README claims negation is rejected", "Disk threshold crossed on the host"],
            self.CORPUS,
        )
        self.assertEqual(mint, ["Disk threshold crossed on the host"])
        self.assertEqual(len(dupes), 1)
        self.assertEqual(held, [])

    def test_dedupe_runs_before_the_cap(self):
        # The failure this pins: if the cap were applied first, duplicates would eat
        # the budget and the pass would report "capped" while minting nothing new.
        candidates = ["README claims negation is rejected", "Genuinely new finding here"]
        mint, dupes, held = rw.partition_mints(candidates, self.CORPUS, cap=1)
        self.assertEqual(mint, ["Genuinely new finding here"])
        self.assertEqual(len(dupes), 1)
        self.assertEqual(held, [])

    def test_overflow_is_held_and_named_not_dropped(self):
        candidates = [f"Distinct finding number {n} about widgets" for n in range(5)]
        mint, _, held = rw.partition_mints(candidates, [], cap=2)
        self.assertEqual(len(mint), 2)
        self.assertEqual(len(held), 3)
        self.assertEqual(mint + held, candidates)

    def test_zero_cap_mints_nothing_but_still_reports(self):
        mint, _, held = rw.partition_mints(["Some finding about widgets"], [], cap=0)
        self.assertEqual(mint, [])
        self.assertEqual(len(held), 1)

    def test_negative_cap_refuses(self):
        with self.assertRaises(ValueError):
            rw.partition_mints([], [], cap=-1)


class TestAnchor(unittest.TestCase):
    def test_bootstrap_reads_no_range(self):
        # A first pass has no delta; claiming one restates the repo as findings.
        self.assertIsNone(rw.code_range(rw.Anchor("alpha"), "abc12345"))

    def test_unchanged_head_reads_no_range(self):
        self.assertIsNone(rw.code_range(rw.Anchor("alpha", sha="abc12345"), "abc12345"))

    def test_moved_head_reads_the_delta(self):
        self.assertEqual(
            rw.code_range(rw.Anchor("alpha", sha="aaa"), "bbb"), "aaa..bbb"
        )

    def test_run_name_is_deterministic_and_carries_the_sha(self):
        a = rw.run_name("alpha", "abc12345def", "20260830T0900Z")
        self.assertEqual(a, rw.run_name("alpha", "abc12345def", "20260830T0900Z"))
        self.assertEqual(a, "watch-alpha-abc12345-20260830T0900Z")

    def test_run_name_separates_two_passes_over_different_heads(self):
        self.assertNotEqual(
            rw.run_name("alpha", "aaaaaaaa", "t"), rw.run_name("alpha", "bbbbbbbb", "t")
        )

    def test_run_name_sanitises_awkward_repo_names(self):
        self.assertEqual(
            rw.run_name("Group/Repo.Name", "abc12345", "t"),
            "watch-group-repo-name-abc12345-t",
        )

    def test_run_name_refuses_an_unusable_repo_name(self):
        with self.assertRaises(ValueError):
            rw.run_name("///", "abc12345", "t")


class TestLenses(unittest.TestCase):
    def test_order_is_plans_beads_docs_code(self):
        # The order is the contract: every later lens can cite an earlier one.
        self.assertEqual(rw.LENSES, ("plans", "beads", "docs", "code"))


if __name__ == "__main__":
    unittest.main()
