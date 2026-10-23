# CLAUDE.md — PaperScope Working Contract

This repository is an active collaboration between Pablo, Claude, and ChatGPT. This file preserves the user's goals and development rules so future sessions do not have to reconstruct them from chat history.

## Product goal
PaperScope is not only a personalized literature dashboard for one scientist. The long-term goal is a **general scientific intelligence product** that any researcher can configure for any scientific field or combination of topics.

The core value proposition is **time saved**: PaperScope should reduce the need to manually browse PubMed, bioRxiv, journal sites, methods papers and tool/resource pages by turning a large stream of literature into a compact, relevant, trustworthy briefing.

The system should support:
- multiple editable topic profiles;
- arbitrary scientific disciplines, not only neuroscience/cell biology;
- topic definitions that can be created/edited without changing core code;
- reusable ranking/QA logic that is field-agnostic;
- separate scientific modules when concepts are genuinely different rather than forcing unrelated content into one section;
- clear provenance and transparent reasons why each paper was shown;
- installable PWA behavior now and a future cross-platform app path;
- free access for users whenever possible, with no required paid subscription for the basic beta;
- install/download behavior that works across Mac, Windows, Android, iPhone and iPad through the web/PWA path, without locking the product to one platform.

The current neuroscience/JIP3 configuration is the first high-quality reference profile and test bed, not the permanent limit of the product.

PaperScope is not a PubMed clone. It should save a working scientist time by producing a reliable weekly/daily briefing: what matters, why it matters, what model/manipulation/methods/results/limitations were used, and where full text/code/data are available.
The benchmark is about 5 minutes in PaperScope replacing 30–60 minutes of browsing PubMed, bioRxiv and journals.
The current product is a GitHub Pages PWA, but backend outputs should remain reusable by a future cross-platform app.

## Non-negotiable relevance rule: topic-first, never people-first
Do not rank papers higher because they resemble the user's own papers, collaborators, familiar labs, citation neighborhoods, famous authors, or highly cited work.
Do not use seed-paper similarity as the main relevance model.
Allowed signals: explicit topic retrieval; semantic similarity to plain-English topic definitions; positive/negative scientific context; mechanistic/model relevance; recency; source quality; and diversity across scientific subtopics.
Citations/references may be used as a candidate-discovery channel, but never as an author/lab popularity bonus.

## Scientific section intent
Focus: strict MAPK8IP3/JIP3; JIP4 only when directly relevant to neuronal/axonal transport, lysosome/endosome biology, or close JIP3 mechanisms.
Neurodevelopment: mechanistic neurodevelopmental disorders, ID/autism/rare genetic brain disease, brain development, neuronal migration, axon guidance, commissures/corpus callosum. Generic clinical imaging or adult injury should not pass.
Lysosome/Endosome: lysosome/endosome biology, damage/repair, lysophagy, endolysosomal maturation, TFEB, lysosomal membrane biology and storage disorders. Strong mechanistic cell biology is acceptable even outside neurons when genuinely relevant.
Trafficking: retromer, retriever, WASH, CCC/Commander, exocyst, ESCRT, HOPS/CORVET, Rab-mediated sorting, axonal/organelle transport and motor-driven cargo movement.
Cytoskeleton: neuronal/organelle microtubules, actin, neurofilaments, dynein/dynactin, kinesins, myosins, neuronal polarity, growth cones and AIS. Immune dendritic cells are not neuronal dendrites.
iPSC: human iPSC-derived neural models only: neurons, microglia, astrocytes, oligodendrocytes, motor neurons, neural progenitors, organoids/assembloids, patient-derived/isogenic systems.
Omics: proteomics/phosphoproteomics/interactomics/lipidomics/metabolomics/RNA-seq/single-cell/spatial/ATAC/CRISPR screens that answer relevant biology or provide reusable relevant datasets. A paper does not qualify merely because it used an omics method.
Imaging: microscopy/imaging of neurons, glia, organelles, lysosomes, trafficking, or genuinely reusable cell-imaging methods. Avoid generic materials, chemistry, radiology and unrelated imaging.
Analysis Tools: actual software/plugins/pipelines/workflows/algorithms/resources for biological image or cell-data analysis. Ordinary biology papers that merely used analysis do not qualify.
Signaling: cAMP/EPAC/PKA/AKAP, AKT/PI3K/mTOR, CC2D1A/B, Rab/Rho families, TMEM55B, RILPL1, TBK1/STING, CHMP4B/SPAG9 and related regulators when the signaling question is central and relevant to neural/lysosomal/trafficking/autophagy biology. Generic compound-via-AKT papers should be deprioritized/rejected.
Extracellular/Lysosomal secretion: neuronal/glial EVs/exosomes/microvesicles plus lysosomal exocytosis, secretory lysosomes, secretory autophagy and unconventional secretion. Mechanistic lysosomal secretion can be non-neural when strongly relevant. Avoid generic EV therapy products and plant vesicles.
Neurodegeneration: mechanistic Parkinson/LRRK2, ALS/FTD, Alzheimer and related work, especially lysosome/endosome/autophagy, trafficking, axonal transport, glia, cytoskeleton, small GTPases, ferroptosis and iPSC/neural intersections.
Keep Reviews, Preprints, Weekly Top 10 and Interactive Resources distinct.

## Reviews are not primary papers
Do not show meaningless empty Targets/Models/Methods fields for reviews.
Use review-appropriate fields: Key targets/pathways, Evidence covered, and Review scope.

## Full-text analysis standard
When OA/PMC full text is available, parse Methods, Results and Discussion/Limitations and extract models, manipulations, methods, targets/pathways, main result, conclusion, limitations and useful code/data/supplement links.
When full text is unavailable, use abstract-level analysis and label it clearly as abstract-only.
Enrich visible/top papers first to keep the daily job fast.

## Relevance architecture
Use this conceptual order: broad candidate retrieval -> hard eligibility/context gates -> semantic fit to the written section definition -> mechanistic/model relevance -> recency -> source quality -> subtopic diversity.
Do not force weak or old papers into a section merely to fill a quota.
Semantic embeddings should compare papers to section definitions, not seed papers.
MMR/diversity is welcome if it operates on topic/subtopic vectors and not author/lab identity.

## Feedback philosophy
When the user reports a bad paper: identify the class of error, fix the general rule, add a regression test, inspect adjacent sections for the same class, and re-run output QA.
Known regression classes include: cAMP vs hippocampal; actin vs interaction; immune dendritic cells vs neuronal dendrites; retriever dog breed vs Retriever complex; omics admitted merely because RNA-seq/proteomics was used; microscopy admitted merely because imaging was used; adult clinical corpus-callosum/MRI papers in Neurodevelopment; plant/amoeba/veterinary leaks; JIP3 incidental mentions in Focus; incidental AKT/PI3K/mTOR endpoints in Signaling.

## QA
A section is not validated because its query looks reasonable. Validate actual output.
After meaningful retrieval/ranking changes: run regression tests; inspect data/audit.json; inspect top Primary/Secondary papers in every section; inspect Weekly Top 10, Reviews and Preprints; check freshness, duplicates, Primary/Secondary overlap, semantic scorer availability, and catastrophic count drops.
The publish guard should fail closed and preserve the previous healthy feed on source failure.

## Frontend/backend source of truth
data/briefing.json should be authoritative for prepared queues.
Avoid duplicated scientific classification/ranking in browser JavaScript. Remove obsolete frontend classifiers once backend queues cover the behavior.
The frontend should mainly render prepared data, local search/filtering, save/like/dislike/report, provenance, analysis depth, links and PWA behavior.
No secrets or private tokens in browser code.

## User development preferences
Preserve the last working baseline and avoid regressions.
Do not make the user debug.
Inspect and test before asking the user to test.
Solve root causes/classes of errors rather than patching screenshots one by one.
Scientific relevance beats impact factor.
Five strong recent papers are better than ten weak fillers.
Signaling may show up to ten because it is intentionally broader.
Exact dates matter; Weekly Top 10 must genuinely reflect the week.
Preprints must be current and relevant; Reviews must be independently retrieved and high quality.
Prefer zero/low-cost beta infrastructure and avoid unnecessary complexity.
Think about how each fix affects the website and future app, not only the immediate symptom.

## Claude + ChatGPT collaboration
Use GitHub Issue #1 as the shared design/QA thread: https://github.com/PMLLancao/PMpapers/issues/1
Before meaningful architectural changes: read latest issue comments and commits; re-fetch the current file SHA before writing; do not overwrite newer work; explain the class of problem being solved; add/adjust regression tests; note tradeoffs or unresolved risks in Issue #1.
If another assistant changed the same file, integrate the newer behavior instead of replacing it wholesale.
The goal is convergence, not competition.

Repository: https://github.com/PMLLancao/PMpapers
PaperScope PWA: https://pmllancao.github.io/PMpapers/paperscope/
Shared architecture issue: https://github.com/PMLLancao/PMpapers/issues/1

If this file conflicts with a newer explicit instruction from the user, the newer user instruction wins.