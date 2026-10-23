"""PaperScope relevance regression tests.

Every known false positive / false negative from the handoff (sections 10, 11, 14) and from
the 22 Oct 2026 audit is pinned here. Run before publishing any change to the updater:

    python tests/test_gates.py        (no dependencies beyond the updater itself)

The GitHub workflow runs this before the updater, so a failing test blocks a bad data push.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_literature as u

def P(title, abstract="", journal="Journal of Cell Biology", types=("Journal Article",), **kw):
    d = {"title": title, "abstract": abstract, "journal": journal,
         "publication_types": list(types), "date": u.NOW.date().isoformat()}
    d.update(kw)
    return d

PASS, FAIL = [], []
def check(name, cond):
    (PASS if cond else FAIL).append(name)

def rejects(p, sec): return not u.gate(p, sec)
def accepts(p, sec): return u.gate(p, sec)

# --- Token matching (handoff 14: cAMP / actin / PKA) -----------------------------------
check("cAMP does not match 'hippocampal'", not u.m("hippocampal neurons", ["camp"]))
check("cAMP matches 'cAMP signaling'", u.m("cAMP signaling", ["camp"]))
check("actin does not match 'actinomycin'", not u.m("treated with actinomycin D", ["actin"]))
check("actin does not match 'interaction'", not u.m("protein interaction", ["actin"]))
check("PKA token does not match 'pKa'-free text 'packaging'", not u.m("vesicle packaging", ["pka"]))
check("'hela' does not match 'chelation'", not u.m("iron chelation therapy", u.MAMMAL))
check("'liver' does not match 'delivery'", not u.m("drug delivery to neurons", u.UNRELATED_ORGAN))
check("'renal' does not match 'adrenal'", not u.m("adrenal gland", u.UNRELATED_ORGAN))
check("'crop' does not match 'necroptosis'", not u.m("necroptosis in microglia", u.NONMODEL))
check("'glia' does not match 'ganglia'", not u.m("basal ganglia circuits", ["glia"]))

# --- Research Focus ---------------------------------------------------------------------
jip3 = P("JIP3 regulates axonal lysosome transport in human iPSC neurons",
         "MAPK8IP3/JIP3 loss causes lysosome accumulation in axons.", "Journal of Cell Biology")
check("Focus: direct JIP3 paper passes", accepts(jip3, "focus"))
check("Focus: LRRK2-only paper fails", rejects(P("LRRK2 kinase activity and Rab10 in microglia",
      "LRRK2 phosphorylates Rab10 in microglia."), "focus"))
check("Focus: JIP4 without transport/lysosome context fails",
      rejects(P("JIP4 expression in breast tissue", "JIP4 mRNA levels were measured."), "focus"))
check("Focus: corrigendum fails", rejects(P(
      'Corrigendum to "DLK silencing attenuated neuron apoptosis through JIP3/MA2K7/JNK pathway"',
      "JIP3", "Neurobiology of disease", ("Published Erratum",)), "focus"))
check("Focus: direct JIP3 title outranks passing mention",
      u.score(jip3, "focus") > u.score(P("Dynactin in intellectual disability",
      "Dynactin binds many adaptors including JIP3.", "Journal of Cell Biology"), "focus"))
# PubMed record of a JBC paper carrying its bioRxiv DOI must not be treated as a preprint
check("Journal paper with bioRxiv DOI is not a preprint", not u.is_preprint(P(
      "Insights into how JIP3 and JIP4 adaptor proteins relieve the auto-inhibited form of the kinesin-1 motor",
      "JIP3 JIP4 kinesin", "The Journal of biological chemistry", doi="10.1101/2021.10.04.463034")))
check("medRxiv record is a preprint", u.is_preprint(P("MAPK8IP3 variants in OCD", "",
      "medRxiv : the preprint server for health sciences")))

check("Focus: cardiac paper citing JIP3/JNK in abstract fails", rejects(P(
      "Knockdown of Long Noncoding RNA IPCRL1 Mitigates Myocardial Ischemia/Reperfusion Injury",
      "IPCRL1 regulates cardiomyocyte apoptosis via the JIP3/JNK pathway in heart.", "Journal of inflammation research"), "focus"))
check("Focus: JIP3-titled cardiac paper fails", rejects(P(
      "Knockdown of Long Noncoding RNA IPCRL1 Mitigates Myocardial Ischemia/Reperfusion Injury via miR-185-3p/JIP3 Axis and JNK Pathway.",
      "Myocardial injury in cardiomyocytes.", "Journal of inflammation research"), "focus"))
check("Focus: JIP3-titled neuronal paper still passes", accepts(P(
      "JIP3 deficiency impairs axonal lysosome transport in human neurons", "JIP3 neurons", "Neuron"), "focus"))
check("Neurodevelopment: hospital communication study fails", rejects(P(
      "Why clinicians in acute hospitals may fail to engage in direct communication with people with intellectual disability",
      "Intellectual disability; brain; clinicians interviewed; children and adults.", "Journal of intellectual disability research"),
      "neurodevelopment"))

# --- Section false positives from the audit (handoff 10) -----------------------------------
check("Trafficking: Doberman genomics fails (retriever = dog breed)", rejects(P(
      "Genomic inbreeding and selection signatures analyses in the Doberman Pinscher breed.",
      "Genotypes from 3,226 Dobermans Dogs were analyzed; compared with Labrador Retriever breeds.",
      "PloS one"), "trafficking"))
check("Trafficking: plant ER-phagy fails", rejects(P(
      "RABC1 regulates ER-phagy to maintain ER homeostasis in plants.",
      "Membrane trafficking and ER-phagy in plants; Rab GTPases regulate autophagy.", "Autophagy"), "trafficking"))
check("Trafficking: amoeba cytoskeletal evolution fails", rejects(P(
      "Multiple evolutionary routes to cytoskeletal arborization revealed by the rhizarian amoeba Filoreta ramosa.",
      "Cytoskeletal arborization occurs in metazoan neurons and amoeboid lineages; membrane trafficking.",
      "Current biology : CB"), "trafficking"))
check("Organelle: skin-aging plant extract fails", rejects(P(
      "Plant-Derived Senolytic Ingredient, Camellia sinensis Root Extract, Ameliorates Skin Aging-Associated Phenotypes",
      "Lysosomal and senescence markers in human dermal fibroblasts; lysosome function.",
      "Experimental dermatology"), "organelle"))
check("Neurodevelopment: GOAT-NET glioma ML fails", rejects(P(
      "GOAT-NET model: Glioma-Oligodendro astrocytoma tumor network model based on few-shot learning",
      "Rare neurological diseases; brain tumor diagnosis; intellectual disability datasets.",
      "Experimental neurology"), "neurodevelopment"))
check("Neurodevelopment: functional-connectivity-only autism study fails", rejects(P(
      "Two clusters of brain regions with distinct age-related profiles of functional connectivity in autism spectrum disorder.",
      "Autism; resting-state fMRI in children with autism; brain connectivity.", "PNAS"), "neurodevelopment"))
check("Neurodevelopment: adult hypoperfusion (corpus callosum only) fails", rejects(P(
      "Sex-divergent neurovascular and cognitive effects of chronic cerebral hypoperfusion.",
      "Corpus callosum white matter damage in adult mice; corpus callosum myelin loss.", "Experimental neurology"),
      "neurodevelopment"))
check("Neurodevelopment: MYT1L disorder passes", accepts(P(
      "Neurobehavioral Profiles and Clinical Consequences of MYT1L-Related Neurodevelopmental Disorder",
      "Patients with MYT1L variants; intellectual disability and autism; brain development.",
      "American journal of medical genetics"), "neurodevelopment"))
check("Imaging: oocyte Golgi biology fails", rejects(P(
      "Golgi disassembly: a key process for autophagy-mediated regulation of oocyte spindle migration.",
      "Live-cell imaging and electron microscopy of mouse oocytes; cortical actin; Golgi.", "Autophagy"), "imaging"))
check("Imaging: explosives residue microscopy fails ('terrorist cells')", rejects(P(
      "Prevention of IED threats: detection of pre-blast explosive residues by confocal Raman microscopy",
      "Terrorist cells use explosives; confocal Raman microscopy method on textiles.", "Analytical methods"), "imaging"))
check("Imaging: STED-FLIM membrane probe method passes", accepts(P(
      "Subdiffraction fluorescence lifetime imaging with Flipper-TR.",
      "STED microscopy with FLIM for membrane tension; super-resolution imaging of lipid membranes.",
      "Methods and applications in fluorescence"), "imaging"))
check("Omics: avian iridescence fails", rejects(P("Modulation of avian iridescence via melanogenesis.",
      "RNA-seq and transcriptomics of bird feathers; single-cell transcriptomics of melanocytes.", "PNAS"), "omics"))
check("Omics: hamster torpor RNA-seq fails", rejects(P("Hamster torpor transcriptomics",
      "RNA-seq of hamster tissues during torpor; transcriptomics.", "PNAS"), "omics"))
check("Omics: marine cyanobacteria proteomics fails", rejects(P(
      "Temporal regulation of metabolic processes in the marine diazotroph Crocosphaera watsonii",
      "Proteomics of cyanobacteria; proteomic clustering.", "mSphere"), "omics"))
check("Analysis tools: remote sensing fails", rejects(P(
      "RSReason: Remote Sensing Reasoning Segmentation via Rotation-aware Large Vision-Language Model",
      "Segmentation software framework for satellite images.", "IEEE transactions on image processing"), "analysis-tools"))
check("Analysis tools: clinical TB tracking workflow fails", rejects(P(
      "A low-resource tracking workflow improves documentation of latent tuberculosis care",
      "Tracking workflow tool for patients.", "Journal of American college health"), "analysis-tools"))
check("Analysis tools: neuron image-analysis plugin passes", accepts(P(
      "NeuriteQuant: an open-source napari plugin for neurite tracing and Sholl analysis",
      "Software for segmentation of fluorescence microscopy images of neurons.", "Bioinformatics"), "analysis-tools"))
check("Signaling: retraction notice fails", rejects(P(
      "Statement of Retraction: Mechanism of erythropoietin-induced M2 microglia polarization via Akt/mTOR",
      "Akt mTOR microglia", "Bioengineered"), "signaling"))
check("Signaling: herbal journal fails", rejects(P(
      "Essential Oils Alleviate LPS-Induced Neuroinflammation by Repressing PI3K/Akt",
      "PI3K Akt microglia", "Phytotherapy research : PTR"), "signaling"))
check("Signaling: incidental AKT mention fails", rejects(P(
      "Hippocampal neurogenesis after exercise in mice",
      "Exercise increased neurogenesis in mice. Akt levels were also measured.", "Journal of Neuroscience"), "signaling"))
check("Signaling: cAMP-TFEB lysosome paper passes", accepts(P(
      "cAMP signaling promotes acute lysosome biogenesis through TFEB nuclear import-export dynamics.",
      "cAMP and PKA regulate TFEB in HeLa cells and neurons.", "Journal of cell science"), "signaling"))
check("Infection: xenophagy TBK1 paper still allowed in Signaling", accepts(P(
      "TBK1-mediated phosphorylation of WIPI2 links bacteria recognition to autophagosome formation in xenophagy.",
      "TBK1 phosphorylates WIPI2 in HeLa cells.", "Autophagy"), "signaling"))
check("Neurodegeneration: LRRK2 review not rejected as infection", u.global_reject(P(
      "Leucine-rich repeat kinase 2 (LRRK2): balancing cellular homeostasis, immunity to pathogens and Parkinson's disease",
      "LRRK2 in neurons and microglia; lysosomes.", "Annals of medicine")) == "")
check("Neurodegeneration: mechanistic LRRK2 lysosome paper passes", accepts(P(
      "LRRK2 kinase activity impairs lysosomal function in Parkinson's disease iPSC dopaminergic neurons",
      "LRRK2 lysosome Parkinson neurons", "Neuron"), "neurodegeneration"))
check("Neurodegeneration: diagnostic-codes study fails", rejects(P(
      "Geographic Variation in Diagnostic Codes Associated With Mild Cognitive Impairment and Alzheimer Disease",
      "Alzheimer disease codes in brain health records; microglia not studied.", "Neurology. Clinical practice"),
      "neurodegeneration"))
check("iPSC: requires neural context", rejects(P("iPSC-derived cardiomyocytes model arrhythmia",
      "Patient-derived iPSC cardiomyocytes.", "Stem cell reports"), "ipsc"))
check("iPSC: ethics paper fails", rejects(P(
      "What Does a Donor Need to Know? Content Analysis of Informed Consent Documents Used for Brain Organoid Research",
      "iPSC brain organoid consent", "AJOB neuroscience"), "ipsc"))
check("EV: non-neural generic EV fails", rejects(P("Exosomes in tumour metastasis",
      "Extracellular vesicle cargo in cancer cells.", "Journal of extracellular vesicles"), "extracellular"))
check("EV: plant-derived exosome-like vesicles fail", rejects(P(
      "Olive leaf-derived exosome-like vesicles attenuate neurotoxicity in an in vitro rotenone model",
      "Exosomes neurons", "Metabolic brain disease"), "extracellular"))
check("Global: MDPI journal excluded even with PubMed place suffix",
      u.tier("Pharmaceuticals (Basel, Switzerland)") == "Excluded")

# --- Journal tier normalisation ----------------------------------------------------------
check("Tier: 'Brain : a journal of neurology' is Primary", u.tier("Brain : a journal of neurology") == "Primary / trusted")
check("Tier: 'Current biology : CB' is Primary", u.tier("Current biology : CB") == "Primary / trusted")
check("Tier: J Neurosci long title is Primary",
      u.tier("The Journal of neuroscience : the official journal of the Society for Neuroscience") == "Primary / trusted")
check("Tier: 'Scientific reports' is Secondary", u.tier("Scientific reports") == "Secondary")

# --- Weekly / dates / dedup -------------------------------------------------------------
from datetime import timedelta
old = P("JIP3 in axons", "JIP3", date=(u.NOW - timedelta(days=30)).date().isoformat())
new = P("JIP3 in axons 2", "JIP3", date=(u.NOW - timedelta(days=2)).date().isoformat())
fut = P("JIP3 in axons 3", "JIP3", date=(u.NOW + timedelta(days=40)).date().isoformat())
check("Weekly: 30-day-old paper is not weekly", not u.enrich(dict(old))["weekly"])
check("Weekly: 2-day-old paper is weekly", u.enrich(dict(new))["weekly"])
check("Weekly: future issue date is not counted as this week", not u.enrich(dict(fut))["weekly"])
a = P("Structural basis for binding of RILPL1 to TMEM55B reveals a lysosomal platform for adaptor assembly through a conserved peptide motif.",
      "x", "Structure (London, England : 1993)", pmid="1", sections=["focus"])
b = P("Structural basis for binding of RILPL1 to TMEM55B reveals a lysosomal platform for adaptor assembly through a conserved TBM motif.",
      "x", "bioRxiv : the preprint server for biology", pmid="2", sections=["focus"], url="https://doi.org/10.1101/x")
folded = u.fold_preprints([u.enrich(a), u.enrich(b)])
check("Dedup: preprint folded into its published version", len(folded) == 1 and folded[0].get("preprint_url"))

# --- Primary / Secondary disjoint --------------------------------------------------------
items = [dict(P("t%d" % i), journal_tier=t, section_score=80) for i, t in
         enumerate(["Primary / trusted", "Secondary", "Uncurated", "Primary / trusted"])]
pri, sec = u.split_tiers(items)
check("Primary and Secondary are disjoint", not ({id(x) for x in pri} & {id(x) for x in sec}))

# --- Card analysis (handoff section 6) ---------------------------------------------------
u.FULLTEXT_ENABLED = False
c = u.analyse_card(u.enrich(P("PKA phosphorylates TFEB in hippocampal neurons",
      "PKA activity was measured in primary hippocampal neurons from knockout mice by live-cell imaging. PKA ...",
      "Journal of Cell Biology")), "signaling")
check("Card: PKA extracted as target", "PKA" in c["targets"])
check("Card: pKa (chemistry) is not PKA", "PKA" not in u.analyse_card(u.enrich(P(
      "Lysosomal pH probes", "The pKa of the probe was 4.5; the pKa shifted.", "Traffic")), "organelle")["targets"])
check("Card: models extracted (specific mouse beats generic)",
      "primary hippocampal neurons" in c["models"] and "mouse (in vivo)" not in c["models"])
check("Card: methods extracted", "live-cell imaging" in c["methods"])
check("Card: abstract-only label when no full text", c["analysis_depth"] == "abstract-only")
r = u.analyse_card(u.enrich(P("Lysosomes in neurodegeneration: a review", "Studies in mice and iPSC neurons...",
      "Trends in cell biology", ("Review",), review=True)), "organelle")
check("Card: reviews get evidence scope, not fake methods", r["methods"] == [] and r["models"] == [] and r["evidence_scope"])
check("Card: JIP3-titled focus paper is Must read",
      u.analyse_card(dict(u.enrich(P("JIP3 in axons", "JIP3")), section_id="focus", section_score=60), "focus")["decision"] == "Must read")

m2 = u.analyse_card(u.enrich(P("JIP3 binds kinesin", "Cells were stained with mouse anti-tubulin and rat anti-HA antibodies in HeLa cells.",
      "Journal of Cell Biology")), "focus")["models"]
check("Card: antibody host species are not models", "mouse (in vivo)" not in m2 and "rat" not in m2 and "HeLa" in m2)
check("Tools: diatom EM segmentation fails", rejects(P("A morphology-driven workflow to decipher 3D electron microscopy segmentation in diatoms",
      "Software workflow for segmentation of diatom cells imaged by electron microscopy.", "Cell reports methods"), "analysis-tools"))
check("Tools: corneal thickness tool fails", rejects(P("Automated quantification of central corneal epithelial thickness",
      "Software pipeline for OCT images of the cornea in patients.", "PloS one"), "analysis-tools"))

print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL: print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
