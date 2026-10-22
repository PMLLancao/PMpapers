# PaperScope v0.31 — relevance gates (22 Oct 2026)

Scope: data/updater layer, per the handoff ("fix scientific curation at the updater, change UI only if necessary").
Output schema of `data/briefing.json` is unchanged, so the live PWA keeps working; one new optional field per section (`best`).

## Root causes fixed (each was producing a class of false positives, not one title)

| Problem seen in audit | Root cause | Fix |
|---|---|---|
| Doberman genomics in Trafficking | `retriever` matched the dog breed | Ambiguous complex names now require "complex" (retriever/WASH/Commander/HOPS complex); organism gate |
| Explosives, copper STM, dentures in Imaging | `has(b, ["method", ...])` is a substring test that matches "methods" in almost every abstract; "terrorist cells" satisfied "cells" | Imaging needs neural/profile biology, or a genuine imaging-method title plus a biological sample; non-optical/materials microscopy rejected |
| Plant, amoeba, avian, cyanobacteria, turtle papers | No organism/model requirement | Non-preferred organism in title → reject; in abstract without mammalian/human context → reject; otherwise demote |
| Skin extract, essential oils, flavonoids | Herbal exclusion was substring-only and abstract-only | Token-aware herbal vocabulary, Latin-binomial "-derived" pattern, phytochemical-in-title rule, journal-domain exclusion |
| Retractions, corrigenda, expressions of concern | Not filtered | Rejected by PubMed publication type and title pattern |
| GOAT-NET glioma, leukemia | Cancer rule needed both a tumour word and a therapy word | Cancer in title → reject unless organelle/trafficking is the subject |
| Functional-connectivity / diagnostic-codes / informed-consent papers | No notion of "clinical only" | Clinical/neuroimaging title with no molecular/cellular signal → reject in Neurodev, Neurodegeneration, iPSC; ethics/bibliometric titles rejected everywhere |
| Incidental AKT/mTOR/Rab mentions | Abstract count ≥2 was enough | Every section now requires centrality (title, or ≥2 abstract mentions); Signaling requires title or a target that dominates the abstract |
| Secondary flooded with chemistry/engineering journals | Every **uncurated** journal went into Secondary automatically | Uncurated journals need a title-level topic hit and a higher score floor |
| *Brain*, *J Neurosci*, *Current Biology*, *Bioinformatics* treated as uncurated; MDPI *Pharmaceuticals* not excluded | Tier matching compared PubMed full titles ("Brain : a journal of neurology", "(Basel, Switzerland)") to short names | Tier matching strips subtitles/places |
| JIP3/JIP4–kinesin-1 JBC paper misfiled as a preprint | PubMed lists the earlier bioRxiv DOI; the parser kept the last DOI seen | Journal DOI preferred; bioRxiv DOI stored as `preprint_doi`; DOI prefix alone no longer means "preprint" |
| RILPL1/TMEM55B shown twice (bioRxiv + Structure) | Dedup used exact title only | Near-identical preprint folded into the published paper (`preprint_url`) |
| medRxiv/bioRxiv records inside Research Focus | PubMed-indexed preprints were `source_type: paper` | Detected by journal/publication type and routed to Preprints |
| 24 Jul 2026 MAPK8IP3 variants preprint never retrieved | Preprint lane only looked back 30 days | Research Focus preprints use the 730-day focus backfill (**unverified against live Europe PMC**) |
| Substring leaks in context lists | `has()` substring: "hela"⊂"chelation", "liver"⊂"delivery", "renal"⊂"adrenal", "crop"⊂"necroptosis" (silently *rejecting* necroptosis papers) | One matcher everywhere: exact token + controlled plural, or explicit `prefix*` anchored at word start |
| `section_recent_days`, `max_results_per_query` in config ignored | Hard-coded in script | Now honoured |
| Paper found by one query never shown in the section its title is about | Sections = only the query that found it | Title-level cross-assignment (gated) |
| Future-dated issue records counted as "this week" | Negative ages clamped to 0 | Flagged `date_uncertain`, excluded from weekly |
| Old builds hidden behind service-worker cache | Cache-first for pages, old caches never deleted | Network-first, old caches deleted on activate, `skipWaiting` |

## New fields
`analysis_depth` ("abstract-only" until full-text enrichment exists), `full_text_available`, `date_uncertain`, `preprint_doi`, `preprint_url`, `sections[*].best` (Primary + strong Secondary, handoff priority 4; not yet wired in the UI), `audit.rejections_by_section` (counts and example titles per rejection reason — use it to spot over-rejection).

## Tests
- `python tests/test_gates.py` — 56 regression checks covering handoff §10/§11/§14 plus every bug above. Runs in the workflow **before** the updater; a failure blocks publishing.
- `python tests/qa_offline.py` — re-runs gates/ranking on the stored data with no network and prints the audit.

## Offline result on the 684 currently published papers
Weekly Top 10: oocyte Golgi, functional-connectivity autism, and other off-profile items removed. Imaging/Analysis Tools went from 30 junk Secondary items each to 1 genuine item each; Reviews 171 → 47 (removed: asthma/dust storms, wastewater virology, ICSI, creatine…).
Sparse sections are expected: the handoff prefers honest small sections over padding. Real retrieval will refill them once queries/sources improve.

## Still open (not done here)
Full-text enrichment (PMC/Europe PMC), review-specific card fields, UI toggle for `best`, broader imaging/tools retrieval queries, live verification of the Focus preprint backfill.
