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

check("Cytoskeleton: immune dendritic-cell actin paper fails", rejects(P(
      "Super-resolution imaging reveals altered actin architecture at CAR-T cell immune synapses",
      "Actin remodeling in human T cells and dendritic cells was imaged by STED microscopy.",
      "Journal of Cell Biology"), "cytoskeleton"))
check("Imaging: immune dendritic-cell microscopy without neural biology fails", rejects(P(
      "Septins regulate podosome dynamics in human immature dendritic cells",
      "Confocal live-cell microscopy of dendritic immune cells and actin-rich podosomes.",
      "Journal of Cell Science"), "imaging"))
check("Neurodevelopment: migraine corpus-callosum DTI fails", rejects(P(
      "Comprehensive evaluation of corpus callosum alterations in migraine using diffusion tensor imaging",
      "Adult migraine patients underwent MRI and DTI of the corpus callosum.",
      "Journal of clinical neuroscience"), "neurodevelopment"))

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

check("Cytoskeleton/Imaging: T-cell immune synapse with cortical actin is not neural", not u.neural_context(
      "Rearrangements of the cortical actin cytoskeleton in Jurkat T cells at the immune synapse; immunological synapse formation."))
check("Neural: real synapse with neurons still neural", u.neural_context("Synapse formation in hippocampal neurons."))
check("Cytoskeleton: CAR-T immune synapse imaging fails", rejects(P(
      "Super-resolution imaging reveals altered actin architecture at CAR-T cell immune synapses.",
      "CAR-T cell immune synapses; actin cytoskeleton; STED microscopy of T cells.", "Nature communications"), "cytoskeleton"))
check("Cytoskeleton: Aspergillus endosome motility fails", rejects(P(
      "Endosome motility controls light-responsive reproductive development and secondary metabolism",
      "In the filamentous fungus Aspergillus nidulans, early endosome motility along microtubules in hyphae requires dynein.",
      "PNAS"), "cytoskeleton"))
check("Trafficking: fungal Hook1 cargo paper fails", rejects(P(
      "Kinesin-3 and the cargo adaptor Hook1 regulate early endosome and peroxisome motility",
      "In Ustilago maydis hyphae, Hook1 links endosomes to dynein; similar mechanisms exist in neurons.",
      "Journal of Cell Biology"), "trafficking"))
check("Cytoskeleton: mammalian neuronal Hook1 paper still passes", accepts(P(
      "Hook1 regulates dynein-driven endosome transport in axons of mouse hippocampal neurons",
      "Hook1 dynein endosomes microtubules axons mice neurons.", "Journal of Cell Biology"), "cytoskeleton"))

check("Imaging: CAR-T immune-synapse application paper fails", rejects(P(
      "Super-resolution imaging reveals altered actin architecture at CAR-T cell immune synapses.",
      "CAR-T cell immune synapses; actin; STED microscopy of human T cells.", "Nature communications"), "imaging"))
check("Imaging: new nanoscopy method paper still passes", accepts(P(
      "Photonic waveguide chip-based nanoscopy for live-cell super-resolution imaging",
      "A chip-based nanoscopy method for live cell super-resolution microscopy of human cells.", "Nature methods"), "imaging"))
check("Imaging: application paper about neurons passes", accepts(P(
      "Expansion microscopy reveals nanoscale organization of the axon initial segment in neurons",
      "Expansion microscopy of mouse hippocampal neurons; axon initial segment.", "Neuron"), "imaging"))

check("Omics: octopus brain development fails", rejects(P("Dynamic roles of embryonic glial cells in octopus brain development",
      "Single-cell RNA-seq of octopus embryonic glia and neurons.", "Current biology : CB"), "omics"))
_mine = P("Identification of Succinylation-Related Transcriptional Signatures in Alzheimer's Disease: Integrated Bioinformatics",
          "We analysed GEO datasets (GSE5281) to find hub genes in Alzheimer brain; neurons; transcriptomics.", "Frontiers in aging neuroscience")
_real = P("Single-nucleus transcriptomics of Alzheimer's disease brain reveals microglial lysosomal states",
          "We generated snRNA-seq from 40 human brains; microglia; lysosome; transcriptomics.", "Frontiers in aging neuroscience")
check("Omics: dataset re-mining ranks below new-data study", u.score(_mine, "omics") < u.score(_real, "omics") - 8)

# --- Ranking behaviour: intervention vs mechanism subject (issue #1, ranking block) ----------
for _t in ["Hydrogen sulfide ameliorates cognitive dysfunction by activating PI3K/AKT",
           "BCG vaccination mitigates tau pathology and restores cognitive function in PS19 mice",
           "Mitochondria-enriched BMSC exosomes restore microglia-neuron cross-talk via PINK1",
           "Neuroprotective Effect of Intranasal Breast Milk-Derived Exosomes in a Neonatal Rat Model",
           "Treadmill exercise rescues cognitive deficits by repairing axonal mitochondrial transport"]:
    check("Intervention subject detected: " + _t[:40], u.intervention_title(_t))
for _t in ["A protective role for APP in nuclear waste clearance via lysosomal exocytosis",
           "WoundPy: an improved automatized method for in vitro cell motility",
           "TGF-β Inhibition Attenuates Tau Accumulation in iPSC neurons",
           "Astrocyte SMN Restoration and Forskolin Treatment Improve SMA Synaptic Pathology",
           "LRRK2 kinase activity restores lysosomal pH in microglia",
           "VPS35 deficiency impairs retromer sorting in neurons"]:
    check("Mechanism subject NOT flagged: " + _t[:40], not u.intervention_title(_t))
_mech = P("LRRK2 inhibition restores lysosomal function in Parkinson's iPSC neurons", "LRRK2 lysosome neurons", "Neuron")
_cmpd = P("Ebselen restores lysosomal function in Parkinson's iPSC neurons", "lysosome neurons", "Neuron")
check("Ranking: compound-subject paper ranks below mechanism-subject paper", u.score(_cmpd, "organelle") < u.score(_mech, "organelle") - 10)
check("Gate: axonemal dynein arm assembly fails Cytoskeleton", rejects(P(
      "DNAAF19-RUVBL1/2 complex recruits multiple adaptors to promote dynein arm assembly.",
      "Axonemal dynein arms in motile cilia; dynein; microtubules; mice.", "Nature communications"), "cytoskeleton"))
check("Gate: imaging-genetics replication fails Neurodevelopment", rejects(P(
      "Validating gene-brain-behavior associations in autism: A replication study.",
      "Autism; brain MRI; genes; children.", "Biological psychiatry"), "neurodevelopment"))
check("Gate: clinical ultrasound fails Imaging", rejects(P(
      "Value of Multimodal Ultrasound Imaging With Super-Resolution in the Differential Diagnosis of Thyroid Nodules",
      "Ultrasound super-resolution in patients.", "Ultrasound in medicine & biology"), "imaging"))
check("Gate: single-cell IMAGING is not omics", rejects(P(
      "Integrated two-photon and photoacoustic microscopy for single-cell neurometabolic imaging",
      "Two-photon microscopy of single-cell metabolism in mouse brain neurons.", "Nature methods"), "omics"))

check("Omics: single-cell methylation method still passes", accepts(P(
      "Integration of polygenic risk with single cell methylation data using met-scDRS.",
      "Single-cell methylation of human brain neurons; polygenic risk; cell types.", "Bioinformatics"), "omics"))
check("Omics: single-cell barcoding sequencing still passes", accepts(P(
      "POINTseq: Cell-type-specific barcoding reveals single-cell projection architecture of the mouse brain",
      "Barcoding and sequencing of mouse neurons projections.", "Nature neuroscience"), "omics"))

# --- Publish guard -------------------------------------------------------------------------
import tempfile, json as _json
_d = Path(tempfile.mkdtemp()); _orig = u.DATA; u.DATA = _d
(_d / "meta.json").write_text(_json.dumps({"total_papers": 400, "section_counts": {k: {"primary": 5, "secondary": 2} for k in "abc"}}))
try:
    u.publish_guard({"total_papers": 30, "section_counts": {k: {"primary": 0, "secondary": 0} for k in "abc"}}); _blocked = False
except SystemExit: _blocked = True
check("Publish guard blocks a collapsed run", _blocked)
try:
    u.publish_guard({"total_papers": 380, "section_counts": {k: {"primary": 4, "secondary": 2} for k in "abc"}}); _ok = True
except SystemExit: _ok = False
check("Publish guard allows a normal run", _ok)
u.DATA = _orig
check("Topic definitions exist for every section", all(k in u.CFG.get("topic_definitions", {}) for k in u.TITLES))

print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL: print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
