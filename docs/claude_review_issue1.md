# Reply to issue #1 (Claude could not post on the issue: token has no Issues permission)

## Claude's answers (checked against live output at `47a2201`, 23 Oct 2026)

Agree with the topic-first rule and the "fix the class, add a test" working rule. Two status corrections first:
- **Dead browser classifiers are already removed** (v0.33: `moduleMatch`, `moduleMatchCore`, `scientificRelevant`, `excluded`, `neural`, `cellbio`, `viewTierMatch`, and the four journal/keyword lists). What remains are *fallbacks* only (see Q4).
- The workflow now **finishes in-progress runs** instead of cancelling them (`cancel-in-progress: false`). Our parallel pushes were cancelling each other's runs mid-way.

### 1. Ranking: relevance must dominate
Measured on the 113 shown cards: semantic fit contributes **−2…+12 points**, recency **0…+30**, tier **−2…+10**. Recency currently outweighs relevance. Proposal: replace the additive score with **lexicographic tiers**:
1. eligibility (hard gates);
2. relevance tier from definition margin, calibrated per section from audit percentiles: *strong* ≥ 0.06, *moderate* 0.0–0.06, *weak* < 0 (weak shown only with a title-level topic hit);
3. within a tier: recency, then source quality, then mechanistic depth.

**Against sparsity: extend the window, never lower the bar.** If a section has fewer than 10 at ≥ moderate, fill from a longer lookback (e.g. 365 → 730 days) using the same thresholds, and label those cards "older".

### 2. Widening Extracellular / Trafficking without losing precision
Retrieval is where they starve; gates are fine.
- Split each broad query into **subtopic queries with their own `retmax`** (retromer/retriever/CCC; ESCRT; HOPS/CORVET; Rab-controlled sorting; axonal organelle transport; lysosomal exocytosis; secretory autophagy/unconventional secretion; glial EVs). One broad sort-by-date query lets a single busy subtopic crowd the rest out.
- Add **Europe PMC full-text search** for OA papers whose abstracts don't name the mechanism.
- Use citations only as a **discovery channel**: papers citing topic-landmark reviews or methods (OpenAlex). They then pass the same gates and ranking. No citation or author bonus.

### 3. Subtopic diversity / MMR without seed bias
Yes. Add `subtopics` (short plain-English sentences) under each section contract and embed them like `about`. Assign each paper to its nearest subtopic, then apply greedy MMR over paper embeddings (λ ≈ 0.7) after thresholding, with at most 3 per subtopic in the visible 10. Everything derives from written definitions; nothing comes from people or papers. Same approach for the Weekly Top 10, across sections.

### 4. Remaining duplicated browser logic
`targets()`, `models()`, `methods()`, `priority()` and `whyShown()` in `paperscope/index.html` still re-derive card fields from the abstract when server fields are missing. That's two sources of truth. Remove them and show "not analysed" instead. Also, section titles and descriptions are hard-coded in `PROFILE.modules`; the server should emit them from the section contract into `briefing.json`.

### 5. Where full text should run
It already runs after ranking, only on shown lists, capped at 260 per run. Missing: a **persistent cache** keyed by PMCID (an `actions/cache` or a `data/cache/fulltext.json` of extracted fields only, not the article text), so each paper is fetched once ever. Also a time budget per run. If over budget, the card is labelled abstract-only and that's recorded in `meta`.

### 6. Missing guards
- **Semantic scorer availability is silent.** If the model fails to load, ranking quietly falls back to rules. Record `semantic: on/off` in `meta.json`, show it in the UI, and fail the run if it is off two days running.
- **Pin versions**: `fastembed` is unpinned and the model cache key has no version. An upgrade could shift every score without a code change. (Also, `pip install requests fastembed numpy fastembed` lists fastembed twice.)
- Schema check of `briefing.json` before commit (required fields, types, primary ∩ secondary = ∅).
- **Canary**: run every regression negative through the *live* output, not just the gates. Any known-bad paper present fails the run.
- Staleness banner in the UI if `generated_at_utc` is older than 48 h.

### 7. Design flaws in the small-embedding approach
- bge-small is general-domain: weak on entity distinctions (JIP3 vs JIP4, PKA vs pKa, gene symbols). Keep **entities in rules and semantics for topic fit** only. Never let semantics admit a paper that the rules rejected.
- **bge is asymmetric**: the definitions should be embedded as queries (`query_embed`, or the documented instruction prefix) and papers as passages. Today both are embedded as passages, which compresses margins.
- Margins are **not comparable across sections**; thresholds must be per section, from audit percentiles.
- **Definitions are now code.** Wording changes shift rankings, so definition edits should run the regression set and report the margin shift.
- 512-token limit: title + abstract (truncated at 2000 chars) is fine; don't embed full text.

### 8. Reducing manual rule patching (no people bias)
- Keep **labelled examples as data**, not code: `tests/examples.json` with title, abstract, section and pass/fail, checked against both gates and semantic tier. New errors become one JSON line.
- Add an **uncertainty queue** to `audit.json`: papers where rules and semantics disagree (rule-pass but weak semantic, or strong semantic but rule-reject). The user reviews ~10 a week. Each verdict becomes an example or a definition edit. That is active learning on topics, not on authors.
- Feedback stays **private by default**: export file → user decides what becomes a public example. Nothing is posted automatically from the app, because the repo is public.

**Proposed split** to avoid collisions: I'll take Q6 guards + version pinning + the query-embedding fix, then the Q1 tiered ranking. ChatGPT could take Q2 subtopic queries + Q3 subtopic definitions/MMR. Both of us: re-read HEAD before every write, and post here before starting a block.
