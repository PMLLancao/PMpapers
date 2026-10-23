import os, json, re, time, html as htmlmod, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "search_config.json").read_text())
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

NOW = datetime.now(timezone.utc)
WEEK = int(CFG.get("weekly_days", 7))
RECENT = int(CFG.get("recent_days", 180))
FOCUS_BACKFILL = int(CFG.get("focus_backfill_days", 730))
REVIEW_DAYS = int(CFG.get("review_days", 1095))
PREPRINT_DAYS = int(CFG.get("preprint_days", 30))

session = requests.Session()
email = os.getenv("USER_EMAIL", "user@example.com")
api_key = os.getenv("NCBI_API_KEY")
session.headers.update({"User-Agent": f"PaperScope/0.32 ({email})"})
EUTIL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

TOPIC_SECTION = {
    "JIP3 / MAPK8IP3":"focus",
    "Neurodevelopment":"neurodevelopment",
    "Lysosome":"organelle",
    "Trafficking":"trafficking",
    "Cytoskeleton":"cytoskeleton",
    "iPSC":"ipsc",
    "Omics":"omics",
    "Imaging":"imaging",
    "Analysis Tools":"analysis-tools",
    "Signaling":"signaling",
    "Extracellular":"extracellular",
    "Neurodegeneration":"neurodegeneration"
}
TITLES = {
    "focus":"Your Research Focus",
    "neurodevelopment":"Neurodevelopmental Disorders & Rare Diseases",
    "organelle":"Lysosomes, Endosomes & Lysosomal Stress/Repair",
    "trafficking":"Intracellular Trafficking & Organelle Transport",
    "cytoskeleton":"Cytoskeleton in Neurons & Organelle Biology",
    "ipsc":"Human iPSC Neural Models",
    "omics":"Omics & Datasets",
    "imaging":"Microscopy & Imaging",
    "analysis-tools":"Analysis Software & Tools",
    "signaling":"Signaling, Small GTPases & Regulatory Proteins",
    "extracellular":"Extracellular Vesicles & Lysosomal Secretion",
    "neurodegeneration":"Neurodegeneration"
}
VISIBLE = {k:10 for k in TITLES}   # user request (22 Oct 2026): 10 per section
PRIMARY = CFG.get("primary_journals", CFG.get("top_journals", []))
SECONDARY = CFG.get("secondary_journals", [])
EXCLUDED = CFG.get("excluded_journals", [])

HIGH_REVIEW = [
    "Nature Reviews Neuroscience","Nature Reviews Molecular Cell Biology",
    "Nature Reviews Neurology","Annual Review of Neuroscience",
    "Annual Review of Cell and Developmental Biology","Trends in Neurosciences",
    "Trends in Cell Biology","Current Opinion in Neurobiology",
    "Current Opinion in Cell Biology","Neuron","Molecular Cell","Autophagy","Traffic",
    "Brain","Molecular Neurodegeneration"
]
def norm(x):
    return re.sub(r"[^a-z0-9]+"," ",str(x or "").lower()).strip()

def safe_get(url, params=None, timeout=60):
    err=None
    for attempt in range(3):
        try:
            r=session.get(url,params=params,timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            err=e
            time.sleep(1.5*(attempt+1))
    raise err

def pause():
    time.sleep(0.12 if api_key else 0.36)

def pubmed_search(term, retmax, reldate):
    p={"db":"pubmed","term":term,"retmax":retmax,"retmode":"json","sort":"pub date","reldate":reldate,"datetype":"pdat"}
    if api_key:p["api_key"]=api_key
    ids=safe_get(EUTIL+"esearch.fcgi",p).json().get("esearchresult",{}).get("idlist",[])
    pause()
    return ids

def month_num(v):
    if not v:return 1
    s=str(v).strip()
    if s.isdigit():return max(1,min(12,int(s)))
    names={m.lower():i for i,m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],1)}
    return names.get(s[:3].lower(),1)

def pub_date(art):
    for node in [art.find(".//Article/ArticleDate"),art.find(".//Journal/JournalIssue/PubDate"),art.find(".//DateCompleted")]:
        if node is None:continue
        y=node.findtext("Year")
        if y and y.isdigit():
            m=month_num(node.findtext("Month"))
            d=node.findtext("Day")
            d=int(d) if d and d.isdigit() else 1
            try:return datetime(int(y),m,d,tzinfo=timezone.utc).date().isoformat()
            except ValueError:pass
        med=node.findtext("MedlineDate") or ""
        ma=re.search(r"((?:19|20)\d{2})(?:\s+([A-Za-z]{3}))?(?:\s+(\d{1,2}))?",med)
        if ma:
            y=int(ma.group(1));m=month_num(ma.group(2));d=int(ma.group(3) or 1)
            try:return datetime(y,m,d,tzinfo=timezone.utc).date().isoformat()
            except ValueError:return f"{y:04d}-{m:02d}-01"
    return ""

def fetch_pubmed(ids, section, lane):
    if not ids:return []
    out=[]
    for start in range(0,len(ids),150):
        chunk=ids[start:start+150]
        p={"db":"pubmed","id":",".join(chunk),"retmode":"xml"}
        if api_key:p["api_key"]=api_key
        root=ET.fromstring(safe_get(EUTIL+"efetch.fcgi",p,90).text);pause()
        for art in root.findall(".//PubmedArticle"):
            te=art.find(".//ArticleTitle")
            title="".join(te.itertext()).strip() if te is not None else ""
            if not title:continue
            absx=[]
            for ab in art.findall(".//Abstract/AbstractText"):
                x="".join(ab.itertext()).strip()
                if x:absx.append(((ab.attrib.get("Label") or "")+": " if ab.attrib.get("Label") else "")+x)
            pmid=art.findtext(".//PMID") or "";pmcid=""
            dois=[(e.text or "").strip() for e in art.findall(".//ELocationID") if e.attrib.get("EIdType")=="doi"]
            for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
                if aid.attrib.get("IdType")=="doi":dois.append((aid.text or "").strip())
                if aid.attrib.get("IdType")=="pmc":pmcid=(aid.text or "").strip()
            dois=[d for d in dict.fromkeys(dois) if d]
            # PubMed sometimes lists the bioRxiv DOI of the earlier preprint; never let it
            # stand in for the journal DOI (that misfiled a JBC JIP3/JIP4 paper as a preprint).
            journal_dois=[d for d in dois if not d.startswith("10.1101/")]
            doi=(journal_dois or dois or [""])[0]
            preprint_doi=next((d for d in dois if d.startswith("10.1101/")),"")
            date=pub_date(art); year=int(date[:4]) if date[:4].isdigit() else 0
            auth=[]
            for a in art.findall(".//Author")[:10]:
                ln=a.findtext("LastName") or "";ini=a.findtext("Initials") or "";cn=a.findtext("CollectiveName") or ""
                n=(ln+" "+ini).strip() if ln else cn
                if n:auth.append(n)
            pts=[(pt.text or "").strip() for pt in art.findall(".//PublicationType") if pt.text]
            rev=any(x in {"Review","Systematic Review","Meta-Analysis"} for x in pts)
            out.append({
                "title":htmlmod.unescape(title),"abstract":" ".join(absx),
                "journal":art.findtext(".//Journal/Title") or "","date":date,"year":year,
                "authors":", ".join(auth),"pmid":pmid,"pmcid":pmcid,"doi":doi,"preprint_doi":preprint_doi,
                "review":rev,"publication_types":pts,"sections":[section],
                "matched_topics":[TITLES[section]],"retrieval_lanes":[lane],
                "sources":["PubMed"],"source_type":"paper",
                "url":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            })
    return out

# ---------------------------------------------------------------------------
# Relevance layer (v0.31)
#
# Matching syntax used by every term list below:
#   "lysosome"   exact token/phrase, plus a controlled plural for alphabetic
#                words of 5+ letters (lysosome, lysosomes). Never a substring.
#   "astrocyt*"  word-START prefix (astrocyte, astrocytes, astrocytic).
#                Never matches inside a word ("glia*" does not match "ganglia").
# Spaces in a phrase also match hyphens ("live cell" == "live-cell").
#
# Design rule from the handoff: prefer general gates over one-title blacklists.
# Each rule below exists because a whole class of false positives got through.
# ---------------------------------------------------------------------------
from functools import lru_cache

def _term_rx(term):
    t = term.strip()
    prefix = t.endswith("*")
    if prefix:
        t = t[:-1]
    body = re.escape(t).replace(r"\ ", r"[\s\-]+")
    if prefix:
        return r"(?<![A-Za-z0-9])" + body
    plural = r"(?:s|es)?" if re.fullmatch(r"[A-Za-z]{5,}", t) else ""
    return r"(?<![A-Za-z0-9])" + body + plural + r"(?![A-Za-z0-9])"

@lru_cache(maxsize=None)
def _rx(terms, case_sensitive=False):
    return re.compile("|".join(_term_rx(x) for x in terms), 0 if case_sensitive else re.I)

def m(text, terms):
    """True if any term (token/prefix-aware) occurs in text."""
    return bool(text) and _rx(tuple(terms)).search(text) is not None

def count(text, terms):
    return len(_rx(tuple(terms)).findall(text or "")) if text else 0

def acro(text, terms):
    """Case-sensitive match for acronyms that are also English words (PALM, STORM, SIM)."""
    return bool(text) and _rx(tuple(terms), True).search(text) is not None

# Backwards-compatible helpers (old code paths and tests use these names).
def exact(text, term): return m(text, [term])
def term_hit(text, term): return m(text, [term])
def hit_any(text, arr): return m(text, arr)
def has(text, arr): return m(text, arr)

# --- Context vocabularies ---------------------------------------------------
NEURAL = ["neuron*", "neural", "neurite*", "brain*", "axon*", "dendrit*", "microglia*",
          "astrocyt*", "glia", "glial", "oligodendrocyt*", "synap*", "hippocamp*", "cerebral cortex",
          "neocort*", "prefrontal", "cortical neuron*", "cortical organoid*", "cerebell*", "striat*", "spinal cord", "motor neuron*", "organoid*",
          "assembloid*", "ipsc*", "hipsc*", "nervous system", "cns", "neurodevelop*",
          "neurodegenerat*", "neurogenesis", "cognit*", "retina*", "dopaminergic"]
MAMMAL = ["human*", "patient*", "mouse", "mice", "murine", "rat", "rats", "primate*",
          "macaque*", "marmoset*", "mammal*", "ipsc*", "hipsc*", "induced pluripotent",
          "embryonic stem", "organoid*", "assembloid*", "hela", "hek293*", "hek 293", "u2os",
          "sh sy5y", "cos 7", "n2a", "neuro 2a", "pc12", "arpe 19", "fibroblast*", "cell line*",
          "knockout", "knock in", "transgenic"]
CELL_CONTEXT = MAMMAL + ["cell", "cells", "cellular", "tissue*", "in vivo", "live cell*", "living cell*"]
NONMODEL = ["plant", "plants", "arabidopsis", "rice", "maize", "tobacco", "tomato", "wheat",
            "crop", "crops", "yeast*", "saccharomyces", "pombe", "drosophila", "zebrafish",
            "c elegans", "caenorhabditis", "nematode*", "amoeba*", "amoeboid", "protist*",
            "trypanosom*", "plasmodium", "toxoplasma", "cyanobacteri*", "diazotroph*", "avian",
            "bird", "birds", "chicken*", "dog", "dogs", "canine", "breed", "breeds", "cattle",
            "bovine", "porcine", "pig", "pigs", "sheep", "sea cucumber*", "aquaculture",
            "hamster*", "veterinar*", "livestock", "turtle*", "reptil*", "amphibian*", "frog*",
            "xenopus", "lizard*", "snake*", "fish", "teleost*"]
PATHOGEN = ["virus*", "viral", "bacteri*", "infection*", "pathogen*", "xenophagy", "sars cov 2",
            "hiv", "hsv", "escherichia", "salmonella", "mycobacteri*", "tuberculosis"]
CANCER = ["cancer*", "carcinoma*", "tumor*", "tumour*", "glioma*", "glioblastoma*",
          "astrocytoma*", "oligodendroglioma*", "leukemi*", "leukaemi*", "lymphoma*",
          "melanoma*", "sarcoma*", "neoplas*", "metasta*", "oncogen*", "b all"]
UNRELATED_ORGAN = ["kidney*", "renal", "liver*", "hepat*", "cardiac", "cardiomyocyt*", "heart",
                   "myocard*", "skin", "dermal", "dermat*", "pancrea*", "intestin*", "gut",
                   "colitis", "bone", "osteo*", "cartilage", "lung*", "pulmonary", "endoderm*",
                   "dental", "denture*", "tooth", "teeth", "endotox*",
                   "oocyte*", "sperm*", "testis", "testic*", "ovar*", "uter*", "endometri*"]
HERBAL = ["herbal", "herb", "herbs", "traditional chinese medicine", "chinese medicine",
          "ethnopharmacolog*", "phytotherap*", "acupuncture", "homeopath*", "ayurved*",
          "essential oil*", "decoction*", "saponin*", "flavonoid*", "polysaccharide*",
          "plant derived", "root extract*", "leaf extract*", "seed extract*", "fruit extract*",
          "plant extract*", "senolytic ingredient*", "nutraceutical*", "leaf derived", "root derived",
          "herb derived", "exosome like nanovesicle*", "exosome like vesicle*"]
# Common phytochemicals: rejected only when they are the subject of the TITLE, so mechanistic
# papers that merely use one as a tool compound are unaffected.
PHYTOCHEMICAL = ["resveratrol", "curcumin", "quercetin", "baicalein", "baicalin", "berberine",
                 "ginsenoside*", "naringenin", "luteolin", "apigenin", "kaempferol", "icariin",
                 "astragaloside*", "ginkgo*", "imperatorin", "stigmasterol", "schaftoside"]
BINOMIAL_DERIVED_RX = re.compile(r"\b[A-Z][a-z]{3,} [a-z]{4,}[- ]derived\b")
# Product-curation exclusion by journal DOMAIN (generalizes the MDPI list):
EXCLUDED_JOURNAL_RX = re.compile(
    r"phyto|ethnopharm|complementary|alternative med|herbal|chinese medicine|\bfood\b|"
    r"nutri|veterinar|aquacult|agricultur|\bplant|dermatol|dental|dentistry|oral investig|"
    r"explosive|forensic|chemical physics|catalys|remote sensing|geosci|environmental science|"
    r"ecolog|marine|fisheries|poultry|animal science|virolog|microb|infect|parasit|"
    r"drug deliv|biomaterial|colloid|\bmaterials\b|\bnano|biosensor|bioelectron|ultrasonic", re.I)
PREPRINT_JOURNAL_RX = re.compile(r"biorxiv|medrxiv|arxiv|research square|preprints?\b|ssrn|chemrxiv", re.I)
NOTICE_TITLE_RX = re.compile(
    r"^\s*(corrigendum|correction|erratum|retraction|retracted|statement of retraction|"
    r"expression of concern|notice of|withdrawn|withdrawal)\b", re.I)
NOTICE_TYPES = {"Published Erratum", "Retraction of Publication", "Retracted Publication",
                "Expression of Concern", "Editorial", "Comment"}
# Clinical / neuroimaging / population work with no molecular or cellular question.
CLINICAL = ["mri", "fmri", "functional connectivity", "functional network*", "connectom*",
            "eeg", "morphometr*", "diagnos*", "prognos*", "predict*", "machine learning",
            "deep learning", "ensemble learning", "classification", "questionnaire*",
            "prevalence", "cohort", "survey*", "registry", "diagnostic codes", "nationwide",
            "retrospective", "randomized", "trial", "informed consent", "ethic*",
            "translational research", "geographic", "epidemiolog*", "post mortem mri",
            "bibliometric*", "knowledge structure", "emerging trends", "associations between",
            "clinician*", "hospital*", "caregiver*", "healthcare", "health care", "quality of life",
            "communication with", "service use", "nurs*"]
MOLECULAR = ["gene", "genes", "genetic*", "genom*", "variant*", "mutation*", "mutant*", "protein*",
             "cell", "cells", "cellular", "molecular", "mouse", "mice", "rat", "rats", "ipsc*",
             "organoid*", "lysosom*", "endosom*", "synap*", "transcript*", "proteom*",
             "microglia*", "astrocyt*", "neuron*", "axon*", "knockout", "pathway*", "kinase*"]
GENE_SYMBOL_RX = re.compile(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9-]{1,9}\b|\b[A-Z]{4,6}\b")
NON_GENE_CAPS = {"MRI", "FMRI", "EEG", "ASD", "ADHD", "AI", "CNS", "DNA", "RNA", "USA", "NDD",
                 "MCI", "OCD", "SPS", "PET", "CBCT", "BBB", "TBI", "IED", "QOL", "COVID", "SARS",
                 "MAPK", "DTI", "GWAS", "CT", "PD", "AD", "ALS", "FTD", "UK", "HIV", "LPS"}
# Treatment / pharmacology / toxicology framing: on-topic words, but rarely the mechanistic
# cell biology this profile wants. Demoted (not removed) so strong cases can still surface.
TREATMENT = ["alleviat*", "ameliorat*", "attenuat*", "mitigat*", "neuroprotect*", "therapeutic*",
             "treatment*", "therapy", "therapies", "nanoparticle*", "nanoplatform*", "neurotoxic*",
             "toxicity", "exposure", "deep brain stimulation", "exercise", "diet", "dietary",
             "supplement*", "drug*", "repurpos*", "engineered", "loaded"]
NON_RESEARCH_TITLE = ["informed consent", "ethic*", "bibliometric*", "knowledge structure",
                      "emerging trends", "content analysis", "policy", "perspective on"]
QUALITY_FLOOR = 62          # minimum section score for anything shown
UNCURATED_FLOOR = 70        # uncurated journals must clear a higher bar
THERAPEUTIC_EV_RX = re.compile(r"(mesenchymal|stem cell|msc)[\w\s-]*(exosome|vesicle)|"
                               r"(loaded|engineered|enriched)[\w\s-]*(exosome|vesicle)", re.I)
REVIEW_TYPES = {"Review", "Systematic Review", "Meta-Analysis", "Scoping Review"}

# --- Section vocabularies (controlled variants; no substrings) --------------
KEYS = {
    "focus": ["mapk8ip3", "jip3", "jip4"],
    "neurodevelopment": ["neurodevelopment", "neurodevelopmental", "intellectual disability",
                         "autism", "autistic", "rare disease", "rare genetic", "axon guidance",
                         "commissure*", "corpus callosum", "cc2d1a", "cc2d1b", "brain development",
                         "cortical development", "neuronal migration", "microcephaly",
                         "developmental delay", "fragile x", "developmental and epileptic"],
    "organelle": ["lysosome", "lysosomal", "endosome", "endosomal", "endolysosom*",
                  "lysophagy", "lysosomal damage", "lysosomal membrane", "lysosomal repair",
                  "lysosomal exocytosis", "autolysosom*", "cathepsin*", "tfeb"],
    "trafficking": ["retromer", "retriever complex", "wash complex", "commander complex",
                    "ccc complex", "exocyst", "escrt", "hops complex", "corvet",
                    "intracellular trafficking", "membrane trafficking", "vesicle trafficking",
                    "endosomal sorting", "endocytic recycling", "axonal transport",
                    "organelle transport", "vps35", "vps26", "snx27", "snx17", "rab7", "rab10",
                    "rab12", "rab36", "rab5", "rab11"],
    "cytoskeleton": ["cytoskeleton", "cytoskeletal", "microtubule", "actin", "f actin",
                     "dynein", "dynactin", "kinesin", "myosin", "neurofilament",
                     "neuronal polarity", "growth cone", "axon initial segment", "tubulin",
                     "spectrin", "ankyrin*"],
    "ipsc": ["ipsc", "ipscs", "hipsc", "hipscs", "induced pluripotent stem cell",
             "patient derived", "isogenic", "brain organoid", "cortical organoid",
             "forebrain organoid", "assembloid*"],
    "omics": ["proteomics", "proteomic", "phosphoproteomic*", "interactom*", "lipidomic*",
              "metabolomic*", "rna seq", "rna sequencing", "transcriptomic*", "single cell",
              "single nucleus", "snrna seq", "scrna seq", "spatial transcriptomics",
              "spatial omics", "spatial transcriptom*", "stereo seq", "visium", "merfish", "slide seq",
              "snrna seq", "scrna seq", "multiomic*", "multi omic*", "atac seq", "multiome", "crispr screen*"],
    "imaging": ["microscopy", "microscope*", "confocal", "live cell imaging", "super resolution",
                "fluorescence lifetime", "electron microscopy", "cryo et", "cryo em", "cryo electron", "correlative",
                "light sheet", "expansion microscopy", "high content imaging", "two photon",
                "intravital", "nanoscopy"],
    "analysis-tools": ["imagej", "fiji", "napari", "cellprofiler", "qupath", "ilastik",
                       "cellpose", "stardist", "segmentation", "particle tracking",
                       "kymograph*", "neurite tracing", "sholl", "colocalization", "puncta",
                       "image analysis", "single cell analysis", "spatial transcriptomics analysis"],
    "signaling": ["camp", "cyclic amp", "epac", "pka", "akap*", "akt", "pi3k", "mtor",
                  "mtorc1", "cc2d1a", "cc2d1b", "rab7", "rab10", "rab12", "rab36", "rab gtpase*",
                  "rhoa", "rhob", "rhoc", "rac1", "rac2", "rac3", "cdc42", "rho gtpase*",
                  "tmem55b", "rilpl1", "tbk1", "sting", "chmp4b", "spag9"],
    "extracellular": ["extracellular vesicle", "exosome", "ectosome", "microvesicle",
                      "lysosomal exocytosis", "lysosome exocytosis", "lysosomal secretion",
                      "secretory lysosome", "secretory autophagy", "unconventional secretion"],
    "neurodegeneration": ["parkinson*", "lrrk2", "amyotrophic lateral sclerosis", "als",
                          "frontotemporal", "ftd", "alzheimer*", "neurodegenerat*",
                          "huntington*", "tauopath*", "synucleinopath*", "lewy"],
}
IMAGING_ACRO = ["STED", "SIM", "PALM", "STORM", "dSTORM", "FLIM", "FRET", "CLEM", "MINFLUX", "SMLM", "TIRF"]
SOFTWARE = ["software", "plugin*", "package*", "toolbox*", "toolkit*", "open source", "pipeline*",
            "workflow*", "algorithm*", "python", "r package", "github", "web server", "web app*",
            "graphical user interface", "gui", "benchmark*", "napari", "imagej", "fiji",
            "cellprofiler", "qupath", "ilastik", "cellpose", "stardist", "database", "atlas",
            "resource"]
BIO_DATA = ["pose estimation", "behavioral video*", "behavioural video*", "cell", "cells", "cellular", "neuron*", "microscop*", "fluorescen*", "histolog*",
            "immunofluorescen*", "tissue section*", "single cell", "proteom*", "transcriptom*",
            "rna seq", "organoid*", "live imaging", "time lapse", "puncta", "organelle*",
            "lysosom*", "mitochondri*", "synap*", "axon*", "dendrit*"]
NON_BIO_TOOLS = ["remote sensing", "satellite", "ct", "cbct", "mri", "radiograph*", "radiolog*",
                 "x ray", "ultrasound", "electronic health record*", "documentation", "catalyst*",
                 "electrochemical", "cyanobacterial bloom", "dixon", "mandibular", "odontogenic",
                 "vision language", "stroke patients", "tuberculosis"]
IMAGING_METHOD_TITLE = ["method*", "probe*", "sensor*", "biosensor*", "reporter*", "technique*",
                        "approach*", "platform*", "microscop*", "resolution", "imaging",
                        "nanoscopy", "label*"]
PROFILE_BIOLOGY = sorted(set(KEYS["organelle"] + KEYS["trafficking"] + KEYS["cytoskeleton"] +
                             KEYS["neurodegeneration"] + KEYS["focus"] + KEYS["signaling"] +
                             KEYS["neurodevelopment"] + ["autophag*", "mitochondri*", "organelle*",
                                                         "golgi", "endoplasmic reticulum"]))
LIVE_BIO = ["live cell*", "living cell*", "cultured cell*", "in cellulo", "cell membrane*",
            "plasma membrane", "membrane tension", "membrane*", "lipid*", "organelle*", "in vivo",
            "tissue*", "mammalian"]
RESOURCE_TITLE = ["atlas", "resource", "database", "dataset*", "reference map*", "browser", "explorer"]
DEGEN_MECHANISM = ["lysosom*", "endosom*", "autophag*", "trafficking", "axon*", "cytoskelet*",
                   "microtubule*", "rab gtpase*", "rab7", "rab8a", "rab10", "rab12", "rab29",
                   "rab32", "rhoa", "rac1", "cdc42", "rho gtpase*", "iron", "ferroptosis", "microglia*",
                   "astrocyt*", "mitochondri*", "synap*", "proteostasis", "aggregat*",
                   "lrrk2", "vps35", "gba*", "tau", "synuclein", "tdp 43", "c9orf72"]

def blob(p):
    return f"{p.get('title','')} {p.get('abstract','')}"

DEVELOPMENTAL = ["neurodevelop*", "developing", "embryo*", "fetal", "foetal", "prenatal", "postnatal",
                 "perinatal", "congenital", "de novo", "syndrome*", "autis*", "intellectual disability",
                 "child*", "infant*", "pediatric", "paediatric", "juvenile", "early life"]

def first_sentences(x, n=8):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", x or "") if s.strip()][:n]

def journal_variants(journal):
    """PubMed full titles carry subtitles/places: 'Brain : a journal of neurology',
    'Bioinformatics (Oxford, England)', 'Current biology : CB'. Compare the short form too."""
    j = journal or ""
    short = re.sub(r"\s*\([^)]*\)", "", j.split(" : ")[0]).strip()
    return {norm(j), norm(short), norm(re.sub(r"^the\s+", "", short, flags=re.I))}

_TIER_SETS = None
def tier(journal):
    global _TIER_SETS
    if _TIER_SETS is None:
        mk = lambda L: set().union(*[journal_variants(x) for x in L]) if L else set()
        _TIER_SETS = (mk(EXCLUDED), mk(SECONDARY), mk(PRIMARY))
    v = journal_variants(journal)
    if v & _TIER_SETS[0]: return "Excluded"
    if v & _TIER_SETS[1]: return "Secondary"
    if v & _TIER_SETS[2]: return "Primary / trusted"
    return "Uncurated"

def is_preprint(p):
    return (p.get("source_type") == "preprint" or "Preprint" in (p.get("publication_types") or [])
            or bool(PREPRINT_JOURNAL_RX.search(p.get("journal") or ""))
            or (str(p.get("doi") or "").startswith("10.1101/") and not (p.get("journal") or "").strip()))

def is_notice(p):
    return bool(NOTICE_TITLE_RX.search(p.get("title") or "")) or \
        bool(NOTICE_TYPES & set(p.get("publication_types") or []))

def gene_symbol_in(title):
    return any(s not in NON_GENE_CAPS for s in GENE_SYMBOL_RX.findall(title or ""))

def title_hit(p, sec):
    return m(p.get("title", ""), KEYS[sec])

def central(p, sec):
    """A topic is central if it is in the title or mentioned at least twice in the abstract."""
    if sec == "imaging":
        t = p.get("title", ""); a = p.get("abstract", "")
        return title_hit(p, sec) or acro(t, IMAGING_ACRO) or \
            count(a, KEYS[sec]) + len(_rx(tuple(IMAGING_ACRO), True).findall(a)) >= 2
    return title_hit(p, sec) or count(p.get("abstract", ""), KEYS[sec]) >= 2

def clinical_only(p):
    t = p.get("title", "")
    return m(t, CLINICAL) and not (m(t, MOLECULAR) or gene_symbol_in(t))

def global_reject(p):
    """Rules that apply to every section, with the reason (useful for the audit)."""
    t = p.get("title", ""); b = blob(p); j = p.get("journal") or ""
    if is_notice(p): return "notice/correction/retraction"
    if m(t, NON_RESEARCH_TITLE): return "ethics/bibliometric/policy"
    if tier(j) == "Excluded" or EXCLUDED_JOURNAL_RX.search(j): return "excluded journal/domain"
    if m(b, HERBAL) or BINOMIAL_DERIVED_RX.search(t) or m(t, PHYTOCHEMICAL): return "herbal/natural-product"
    # Only papers ABOUT JIP3/MAPK8IP3 (in the title) skip the organism/organ/cancer rules;
    # a passing abstract mention (e.g. a cardiac injury paper citing JIP3/JNK) does not.
    if m(t, KEYS["focus"]):
        # Even a JIP3-titled paper is off-profile if it is about an unrelated organ (heart, kidney...).
        neuro_t = m(t, NEURAL + KEYS["neurodegeneration"] + KEYS["neurodevelopment"])
        return "unrelated organ (title)" if (m(t, UNRELATED_ORGAN + ["ischemia reperfusion"]) and not neuro_t) else ""
    if m(t, NONMODEL): return "non-preferred organism (title)"
    if m(b, NONMODEL) and not m(b, MAMMAL): return "non-preferred organism, no mammalian context"
    if m(t, CANCER) and not m(t, KEYS["organelle"] + KEYS["trafficking"]): return "cancer focus"
    if m(b, CANCER) and m(b, ["therapy", "metastasis", "survival", "prognosis", "chemoresistance",
                              "tumor growth", "tumour growth"]) and not m(t, NEURAL): return "cancer therapy"
    neuro_title = m(t, NEURAL + KEYS["neurodegeneration"] + KEYS["neurodevelopment"])
    if m(t, PATHOGEN) and not (neuro_title or m(t, KEYS["signaling"])): return "pathogen/infection focus"
    if m(t, UNRELATED_ORGAN) and not neuro_title: return "unrelated organ (title)"
    if m(b, UNRELATED_ORGAN) and not m(b, NEURAL): return "unrelated organ, no neural context"
    return ""

def gate_reason(p, section):
    """Return '' if the paper belongs in `section`, else the reason it was rejected."""
    r = global_reject(p)
    if r: return r
    t = p.get("title", ""); a = p.get("abstract", ""); b = blob(p)
    neural = m(b, NEURAL); mammal = m(b, MAMMAL); cellctx = m(b, CELL_CONTEXT)
    if section == "focus":
        if m(b, ["mapk8ip3", "jip3"]): return ""
        if m(b, ["jip4"]) and m(b, ["neuron*", "axon*", "lysosom*", "endosom*", "transport"]): return ""
        return "no direct JIP3/MAPK8IP3 (or relevant JIP4)"
    if not central(p, section): return "topic not central"
    if section in ("neurodevelopment", "neurodegeneration", "ipsc") and clinical_only(p):
        return "clinical/neuroimaging only, no molecular question"
    if section == "neurodevelopment":
        if not neural: return "no neural context"
        # corpus callosum / commissure mentions in adult injury papers are not neurodevelopment
        return "" if (title_hit(p, section) or m(b, DEVELOPMENTAL)) else "no developmental/disease context"
    if section in ("organelle", "trafficking"):
        return "" if (neural or mammal) else "no neural/mammalian context"
    if section == "cytoskeleton":
        return "" if neural else "no neural context"
    if section == "ipsc":
        return "" if m(b, ["neuron*", "microglia*", "astrocyt*", "oligodendrocyt*", "glia*",
                           "organoid*", "assembloid*", "motor neuron*", "neural progenitor*",
                           "neural stem"]) else "iPSC without neural context"
    if section == "omics":
        if not (mammal or neural): return "no mammalian/human or neural context"
        if m(t, ["diagnos*", "biomarker*", "prognos*", "machine learning"]) and not m(b, PROFILE_BIOLOGY):
            return "diagnostic/biomarker omics, off-profile biology"
        relevant = neural or m(b, PROFILE_BIOLOGY) or m(t, RESOURCE_TITLE)
        return "" if relevant else "omics used, biology off-profile"
    if section == "imaging":
        # "cells" alone is not enough ("terrorist cells" let an explosives paper in)
        if m(t, ["atomic force", "scanning tunneling", "scanning electrochemical", "raman"]) and not neural:
            return "non-optical/materials microscopy"
        method_paper = (m(t, KEYS["imaging"]) or acro(t, IMAGING_ACRO)) and m(t, IMAGING_METHOD_TITLE)
        bio_sample = neural or mammal or m(b, PROFILE_BIOLOGY) or (method_paper and m(b, LIVE_BIO))
        if not bio_sample: return "no biological/cellular context"
        relevant = neural or central(p, "organelle") or central(p, "trafficking") or central(p, "focus")
        return "" if (relevant or method_paper) else "imaging used, biology off-profile"
    if section == "analysis-tools":
        if m(b, NON_BIO_TOOLS) and not m(b, ["microscop*", "fluorescen*", "neuron*", "proteom*",
                                              "single cell", "organoid*"]):
            return "clinical/non-biological tool"
        if not m(b, SOFTWARE): return "no software/tool signal"
        return "" if m(b, BIO_DATA) else "tool not for cell/molecular data"
    if section == "signaling":
        # targets must be central: in the title, or the subject of the whole abstract
        if not (title_hit(p, section) or count(a, KEYS[section]) >= 4 and m(" ".join(first_sentences(a, 2)), KEYS[section])):
            return "signaling target only incidental"
        return "" if (neural or mammal or m(b, ["lysosom*", "endosom*", "trafficking", "autophag*"])) \
            else "no relevant context"
    if section == "extracellular":
        ev = m(b, ["extracellular vesicle", "exosome", "ectosome", "microvesicle"])
        lysosec = m(b, KEYS["extracellular"][4:])
        return "" if ((ev and neural) or lysosec) else "EV without neural context"
    if section == "neurodegeneration":
        if not neural: return "no neural context"
        return "" if m(b, DEGEN_MECHANISM) else "no mechanistic intersection"
    return "unknown section"

def gate(p, section):
    return gate_reason(p, section) == ""

# Kept for compatibility with older callers.
def signaling_central(p): return central(p, "signaling")

def strong_for_uncurated(p, sec):
    """Uncurated journals need a title-level topic hit to be shown at all."""
    if sec == "focus": return m(p.get("title", ""), KEYS["focus"])
    if sec == "imaging": return title_hit(p, sec) or acro(p.get("title", ""), IMAGING_ACRO)
    if sec == "analysis-tools": return m(p.get("title", ""), SOFTWARE + KEYS[sec])
    return title_hit(p, sec)

def age_days(p):
    """Days since publication. Future-dated records (issue dates ahead of today) return -1."""
    try:
        d = (NOW.date() - datetime.fromisoformat(p.get("date", "")).date()).days
        return d if d >= 0 else -1
    except Exception:
        return 99999

def centrality(p, section):
    t = p.get("title", ""); a = p.get("abstract", "")
    n = 8 * len(set(x.lower() for x in _rx(tuple(KEYS[section])).findall(t)))
    n += 2 * min(6, count(a, KEYS[section]))
    return min(24, n)

def score(p, section, review=False):
    age = age_days(p); s = 40 + centrality(p, section)
    if section == "focus":
        t = p.get("title", "")
        if m(t, ["mapk8ip3", "jip3"]): s += 30          # direct JIP3 work leads the section
        elif m(t, ["jip4"]): s += 18
        elif count(p.get("abstract", ""), KEYS["focus"]) <= 1: s -= 10   # single passing mention
        else: s += 8
    if age < 0: s += 4                                  # date uncertain: no recency boost
    elif age <= 7: s += 30
    elif age <= 30: s += 22
    elif age <= 90: s += 14
    elif age <= 180: s += 7
    elif age <= 365: s += 2
    else: s -= min(15, ((age - 365) // 180) * 2)
    t = tier(p.get("journal"))
    if t == "Primary / trusted": s += 10
    elif t == "Secondary": s += 3
    else: s -= 2
    b = blob(p)
    if m(b, NONMODEL): s -= 10                           # deprioritized model organisms
    if section != "focus" and m(p.get("title", ""), TREATMENT):
        s -= 12                                         # "compound X alleviates Y via pathway Z"
    if section == "extracellular" and THERAPEUTIC_EV_RX.search(b): s -= 10
    if review:
        if any(norm(p.get("journal")) == norm(x) for x in HIGH_REVIEW): s += 16
        if 0 <= age <= 180: s += 8
    return int(s)

def first_sentences(x, n=8):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", x or "") if s.strip()][:n]

def enrich(p):
    ss = first_sentences(p.get("abstract"), 8)
    p["overview"] = ss[0] if ss else "Abstract not available from the current source."
    result = next((s for s in ss[1:] if re.search(r"\b(we found|we show|we demonstrate|results|revealed|increased|decreased|impair|promot|required|drives|regulates)\b", s, re.I)), None)
    p["main"] = (ss[-1] if p.get("review") and ss else result or (ss[-1] if ss else "Open the paper for details."))
    if is_preprint(p): p["source_type"] = "preprint"
    # Reviews that PubMed has not (yet) typed as Review: "...: A review", "A narrative review of..."
    if re.search(r"(?:[:.]\s*|^)(?:an?\s+)?(?:systematic|narrative|scoping|critical|comprehensive|mini)?\s*review\b",
                 p.get("title", ""), re.I):
        p["review"] = True
    p["journal_tier"] = tier(p.get("journal"))
    p["age_days"] = age_days(p)
    p["date_uncertain"] = p["age_days"] < 0
    p["weekly"] = 0 <= p["age_days"] <= WEEK
    # Honest labelling until full-text enrichment exists (handoff section 6).
    p["analysis_depth"] = "abstract-only" if p.get("abstract") else "title-only"
    p["full_text_available"] = bool(p.get("pmcid"))
    p["sources_label"] = ", ".join(p.get("sources", [])); p["matched_topics_label"] = ", ".join(p.get("matched_topics", []))
    return p

def pkey(p):
    return p.get("pmid") or p.get("doi") or norm(p.get("title"))

def merge(store, p):
    k = pkey(p)
    if not k: return
    if k not in store: store[k] = p; return
    o = store[k]
    for f in ["sections", "matched_topics", "retrieval_lanes", "sources"]:
        o[f] = list(dict.fromkeys(o.get(f, []) + p.get(f, [])))
    if len(p.get("abstract", "")) > len(o.get("abstract", "")): o["abstract"] = p["abstract"]
    for f in ["doi", "pmid", "pmcid", "journal", "authors", "url", "date"]:
        if not o.get(f) and p.get(f): o[f] = p[f]
    o["review"] = o.get("review") or p.get("review")

def _similar(a, b):
    from difflib import SequenceMatcher
    a, b = norm(a), norm(b)
    return a == b or (min(len(a), len(b)) > 40 and SequenceMatcher(None, a, b).ratio() >= 0.88)

def fold_preprints(allp):
    """A preprint that has since been published is shown once, as the journal paper,
    with the preprint kept as a link. Prevents the RILPL1/TMEM55B double entry."""
    pubs = [p for p in allp if not is_preprint(p)]
    keep = []
    for p in allp:
        if is_preprint(p):
            twin = next((q for q in pubs if _similar(q.get("title"), p.get("title"))), None)
            if twin:
                twin["preprint_url"] = p.get("url") or (("https://doi.org/" + p["doi"]) if p.get("doi") else "")
                twin["sections"] = list(dict.fromkeys(twin.get("sections", []) + p.get("sections", [])))
                continue
        keep.append(p)
    return keep

REJECTIONS = {}

def note_rejection(sec, p, reason):
    r = REJECTIONS.setdefault(sec, {})
    e = r.setdefault(reason, {"count": 0, "examples": []})
    e["count"] += 1
    if len(e["examples"]) < 3: e["examples"].append(p.get("title", "")[:140])

def admit(store, p, sec):
    reason = gate_reason(p, sec)
    if reason: note_rejection(sec, p, reason)
    else: merge(store, p)

def section_days(sec):
    if sec == "focus": return FOCUS_BACKFILL
    return int((CFG.get("section_recent_days") or {}).get(sec, RECENT))

PER_QUERY = int(CFG.get("max_results_per_query", 45))

def retrieve_research():
    store = {}
    # extra_queries: narrower, high-precision searches for sections where the broad query is
    # crowded out by off-topic recent papers (Imaging, Analysis Tools, Extracellular).
    for q in CFG["queries"] + CFG.get("extra_queries", []):
        sec = TOPIC_SECTION.get(q["topic"])
        if not sec: continue
        ids = list(dict.fromkeys(pubmed_search(q["pubmed"], PER_QUERY, WEEK) +
                                 pubmed_search(q["pubmed"], PER_QUERY * 2, section_days(sec))))
        for p in fetch_pubmed(ids, sec, "weekly+recent"):
            if p.get("review"): continue
            admit(store, p, sec)
    return store

def retrieve_reviews():
    store = {}
    for q in CFG["queries"]:
        sec = TOPIC_SECTION.get(q["topic"])
        if not sec: continue
        term = f"({q['pubmed']}) AND (review[Publication Type] OR systematic review[Publication Type] OR meta-analysis[Publication Type])"
        ids = pubmed_search(term, 28, REVIEW_DAYS)
        for p in fetch_pubmed(ids, sec, "independent-review"):
            p["review"] = True
            admit(store, p, sec)
    return store

def retrieve_preprints():
    store = {}
    end = NOW.date().isoformat()
    for q in CFG["queries"]:
        sec = TOPIC_SECTION.get(q["topic"])
        if not sec: continue
        # Research Focus is narrow, so its preprints use the same long backfill as its papers
        # (the 24 Jul 2026 pathogenic MAPK8IP3 variants preprint fell outside a 30-day window).
        days = FOCUS_BACKFILL if sec == "focus" else PREPRINT_DAYS
        start = (NOW - timedelta(days=days)).date().isoformat()
        # Europe PMC indexes bioRxiv/medRxiv preprints and lets us enforce dates.
        query = f'SRC:PPR AND FIRST_PDATE:[{start} TO {end}] AND ({q["europepmc"]})'
        params = {"query": query, "format": "json", "pageSize": 30, "resultType": "core", "sort": "FIRST_PDATE_D desc"}
        try: data = safe_get(EPMC, params).json()
        except Exception as e:
            print("preprint search skipped", sec, e); continue
        for it in data.get("resultList", {}).get("result", []):
            d = (it.get("firstPublicationDate") or it.get("firstIndexDate") or "")[:10]
            clean = lambda x: re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", x or ""))).strip()
            p = {"title": clean(it.get("title")), "abstract": clean(it.get("abstractText")),
                 "journal": it.get("journalTitle") or "bioRxiv / preprint", "date": d,
                 "year": int(d[:4]) if d[:4].isdigit() else 0, "authors": it.get("authorString") or "",
                 "pmid": it.get("pmid") or "", "pmcid": it.get("pmcid") or "", "doi": it.get("doi") or "",
                 "review": False, "sections": [sec], "matched_topics": [TITLES[sec]], "retrieval_lanes": ["preprint"],
                 "sources": ["Europe PMC preprint"], "source_type": "preprint", "publication_types": ["Preprint"],
                 "url": ("https://doi.org/" + it["doi"]) if it.get("doi") else "https://europepmc.org/"}
            if p["title"]: admit(store, p, sec)
        pause()
    return store

def dedupe(items):
    seen = set(); out = []
    for p in items:
        k = norm(p.get("title"))
        if k and k not in seen: seen.add(k); out.append(p)
    return out

def ranked(allp, sec, review=False, preprint=False):
    out = []
    for p in allp:
        if sec not in p.get("sections", []): continue
        if bool(p.get("review")) != bool(review): continue
        if is_preprint(p) != bool(preprint): continue
        if not gate(p, sec): continue
        if not preprint and tier(p.get("journal")) == "Uncurated" and not strong_for_uncurated(p, sec): continue
        q = dict(p); q["section_id"] = sec; q["section_score"] = score(q, sec, review)
        if not preprint and sec != "focus":
            unc = tier(p.get("journal")) == "Uncurated"
            # Reviews use a 3-year window, so age alone must not push curated reviews out.
            floor = (60 if unc else 0) if review else (UNCURATED_FLOOR if unc else QUALITY_FLOOR)
            if q["section_score"] < floor: continue
        out.append(q)
    out.sort(key=lambda x: (x["section_score"], x.get("date", "")), reverse=True)
    return dedupe(out)

def split_tiers(items):
    pri = []; sec = []
    for p in items:
        if p["journal_tier"] == "Primary / trusted": pri.append(p)
        elif p["journal_tier"] in {"Secondary", "Uncurated"}: sec.append(p)
    return pri, sec

def best_mix(pri, seco, n=30):
    """Default 'Best' view (handoff priority 4): one ranked list mixing Primary and
    Secondary so a section can show 10 good papers when Primary alone is sparse.
    Secondary items carry a small handicap so Primary wins ties. Both already passed
    the section gates and quality floors; nothing weaker is added to reach 10."""
    pool = [(p["section_score"], p) for p in pri] + [(p["section_score"] - 6, p) for p in seco]
    pool.sort(key=lambda x: (x[0], x[1].get("date", "")), reverse=True)
    return [p for _, p in pool][:n]

def weekly_top10(section_lists):
    c = []
    for sec, items in section_lists.items():
        for p in items:
            if p.get("weekly"):
                q = dict(p); q["weekly_section"] = sec
                q["weekly_score"] = q["section_score"] + (8 if q["journal_tier"] == "Primary / trusted" else 2 if q["journal_tier"] == "Secondary" else 0)
                c.append(q)
    c.sort(key=lambda x: (x["weekly_score"], x.get("date", "")), reverse=True)
    out = []; seen = set(); sc = {}; jc = {}
    for p in c:
        k = norm(p["title"]); sec = p["weekly_section"]; j = norm(p.get("journal"))
        if k in seen or sc.get(sec, 0) >= 2 or jc.get(j, 0) >= 2: continue
        out.append(p); seen.add(k); sc[sec] = sc.get(sec, 0) + 1; jc[j] = jc.get(j, 0) + 1
        if len(out) == 10: break
    if len(out) < 10:
        for p in c:
            k = norm(p["title"])
            if k in seen: continue
            out.append(p); seen.add(k)
            if len(out) == 10: break
    return out[:10]

def _brief(p, extra=()):
    d = {"title": p.get("title"), "date": p.get("date"), "journal": p.get("journal")}
    for f in extra: d[f] = p.get(f)
    return d

# ---------------------------------------------------------------------------
# Card analysis (v0.32): computed in the updater so the app shows real fields.
# Open-access papers (PMC id) are read in full from Europe PMC: Methods for models
# and methods, Results/Discussion for limitations, and the whole text for code/data
# links. Everything else is labelled "abstract-only". Nothing is inferred beyond text.
# ---------------------------------------------------------------------------
FULLTEXT_ENABLED = os.environ.get("PAPERSCOPE_FULLTEXT", "1") == "1"
FULLTEXT_MAX = int(os.environ.get("PAPERSCOPE_FULLTEXT_MAX", "260"))
EPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
_FT_CACHE = {}

# (label, terms) — curated profile targets. Case-sensitive entries guard words like PKA/pKa.
TARGETS = [
    ("MAPK8IP3/JIP3", ["mapk8ip3", "jip3"]), ("JIP4/SPAG9", ["jip4", "spag9"]),
    ("KIF5/kinesin-1", ["kif5a", "kif5b", "kif5c", "kinesin 1"]), ("KIF1A", ["kif1a"]),
    ("KLC1", ["klc1"]), ("Dynein", ["dynein", "dync1h1"]), ("Dynactin", ["dynactin", "dctn1"]),
    ("LRRK2", ["lrrk2"]), ("VPS35/retromer", ["vps35", "retromer"]),
    ("RAB7", ["rab7", "rab7a"]), ("RAB10", ["rab10"]), ("RAB12", ["rab12"]), ("RAB29", ["rab29"]),
    ("RAB36", ["rab36"]), ("RAB GTPases", ["rab gtpase*"]), ("RHOA", ["rhoa"]), ("RAC1", ["rac1"]),
    ("CDC42", ["cdc42"]), ("TMEM55B", ["tmem55b"]), ("RILPL1", ["rilpl1"]), ("CC2D1A", ["cc2d1a"]),
    ("CC2D1B", ["cc2d1b"]), ("TBK1", ["tbk1"]), ("STING", ["sting", "cgas"]), ("CHMP4B/ESCRT", ["chmp4b", "escrt"]),
    ("TFEB", ["tfeb"]), ("mTORC1/mTOR", ["mtorc1", "mtor"]), ("AKT/PI3K", ["akt", "pi3k"]),
    ("cAMP/EPAC", ["camp", "cyclic amp", "epac", "epac1", "epac2"]), ("AKAP", ["akap*"]),
    ("LAMP1", ["lamp1"]), ("Cathepsins", ["cathepsin*"]), ("GBA1", ["gba", "gba1", "glucocerebrosidase"]),
    ("TDP-43", ["tdp 43", "tardbp"]), ("Tau", ["tau", "mapt"]), ("α-synuclein", ["synuclein", "snca"]),
    ("APOE", ["apoe", "apoe4"]), ("C9orf72", ["c9orf72"]), ("TREM2", ["trem2"]), ("Neurofilament", ["neurofilament*"]),
    ("Ankyrin-G", ["ankyrin g", "ankyrin-g", "ank3"]), ("Galectin-3", ["galectin 3", "lgals3"]),
]
TARGETS_CS = [("PKA", ["PKA", "protein kinase A"])]

MODELS = [
    ("human iPSC-derived neurons", ["ipsc derived neuron*", "hipsc derived neuron*", "induced neuron*", "i3neuron*"]),
    ("human iPSC-derived microglia", ["ipsc derived microglia*", "hipsc derived microglia*"]),
    ("human iPSC-derived astrocytes", ["ipsc derived astrocyt*", "hipsc derived astrocyt*"]),
    ("human iPSC-derived cells", ["ipsc*", "hipsc*", "induced pluripotent"]),
    ("brain organoids / assembloids", ["organoid*", "assembloid*"]),
    ("primary hippocampal neurons", ["primary hippocampal neuron*", "hippocampal neuron culture*", "cultured hippocampal neuron*"]),
    ("primary cortical neurons", ["primary cortical neuron*", "cultured cortical neuron*"]),
    ("primary neurons (other)", ["primary neuron*", "dorsal root ganglion neuron*", "drg neuron*", "motor neuron culture*"]),
    ("knock-in mouse", ["knock in mice", "knock in mouse", "knockin mice", "knockin mouse"]),
    ("knockout / conditional mouse", ["knockout mice", "knockout mouse", "conditional knockout", "cko mice", "null mice", "deficient mice"]),
    ("transgenic mouse", ["transgenic mice", "transgenic mouse"]),
    ("mouse (in vivo)", ["mice", "mouse"]), ("rat", ["rat", "rats"]),
    ("zebrafish", ["zebrafish"]), ("Drosophila", ["drosophila"]), ("C. elegans", ["c elegans", "caenorhabditis"]),
    ("yeast", ["yeast*", "saccharomyces"]), ("non-human primate", ["macaque*", "marmoset*", "non human primate*"]),
    ("HeLa", ["hela"]), ("HEK293", ["hek293*", "hek 293"]), ("U2OS", ["u2os"]), ("SH-SY5Y", ["sh sy5y"]),
    ("COS-7", ["cos 7"]), ("N2a", ["n2a", "neuro 2a"]), ("ARPE-19", ["arpe 19"]),
    ("patient fibroblasts", ["patient fibroblast*", "patient derived fibroblast*"]),
    ("human post-mortem brain", ["post mortem", "postmortem", "autopsy"]),
    ("patients / clinical cohort", ["patients", "cohort", "probands", "families"]),
    ("purified proteins / in vitro reconstitution", ["purified protein*", "in vitro reconstitution", "reconstituted in vitro", "recombinant protein*"]),
]
METHODS = [
    ("live-cell imaging", ["live cell imaging", "live imaging", "time lapse"]),
    ("super-resolution microscopy", ["super resolution", "sted", "storm", "palm", "sim microscopy", "minflux", "expansion microscopy"]),
    ("confocal microscopy", ["confocal"]), ("electron microscopy", ["electron microscopy", "tem", "sem", "focused ion beam"]),
    ("cryo-EM / cryo-ET", ["cryo em", "cryo et", "cryo electron"]), ("CLEM", ["correlative light"]),
    ("light-sheet imaging", ["light sheet"]), ("two-photon imaging", ["two photon"]),
    ("kymograph / axonal transport assay", ["kymograph*", "axonal transport"]),
    ("proteomics / mass spectrometry", ["proteomic*", "mass spectrometry", "lc ms", "tmt"]),
    ("phosphoproteomics", ["phosphoproteomic*"]), ("interactomics / proximity labelling", ["interactom*", "bioid", "turboid", "apex2", "proximity labeling", "proximity labelling"]),
    ("co-immunoprecipitation", ["co immunoprecipitation", "coimmunoprecipitation", "co ip", "immunoprecipitation"]),
    ("lipidomics / metabolomics", ["lipidomic*", "metabolomic*"]),
    ("bulk RNA-seq", ["rna seq", "rna sequencing"]), ("single-cell / single-nucleus RNA-seq", ["scrna seq", "snrna seq", "single cell rna", "single nucleus rna", "single cell transcriptom*", "single nucleus transcriptom*"]),
    ("spatial transcriptomics", ["spatial transcriptom*", "visium", "merfish", "stereo seq"]),
    ("ATAC-seq / chromatin profiling", ["atac seq", "chip seq", "cut tag", "cut&tag"]),
    ("exome / genome sequencing", ["exome sequencing", "whole exome", "whole genome sequencing", "wes", "wgs"]),
    ("GWAS / genetic association", ["gwas", "genome wide association"]),
    ("CRISPR editing / screens", ["crispr*"]), ("siRNA / shRNA knockdown", ["sirna", "shrna", "knockdown"]),
    ("western blot", ["western blot*", "immunoblot*"]), ("immunofluorescence / IHC", ["immunofluorescen*", "immunohistochem*", "immunostain*"]),
    ("electrophysiology", ["patch clamp", "electrophysiolog*", "multielectrode", "mea recording*"]),
    ("calcium imaging", ["calcium imaging", "gcamp"]), ("behavioural testing", ["behavioral test*", "behavioural test*", "morris water maze", "rotarod", "open field", "fear conditioning"]),
    ("structural biology (X-ray/AlphaFold/NMR)", ["crystal structure", "x ray crystallograph*", "alphafold", "nmr"]),
    ("single-molecule / optical trap", ["single molecule", "optical trap*", "in vitro motility"]),
    ("MRI / neuroimaging", ["mri", "fmri", "diffusion tensor"]), ("machine learning / modelling", ["machine learning", "deep learning", "computational model*"]),
]
LINK_RX = re.compile(r"https?://(?:www\.)?(github\.com|gitlab\.com|zenodo\.org|figshare\.com|osf\.io|addgene\.org|"
                     r"bitbucket\.org|huggingface\.co|codeocean\.com|dandiarchive\.org|ebi\.ac\.uk/pride|"
                     r"proteomexchange\.org|ncbi\.nlm\.nih\.gov/geo)[^\s<>\")\],;]*", re.I)
ACCESSION_RX = re.compile(r"\b(GSE\d{4,}|PXD\d{5,}|E-MTAB-\d+|SRP\d{5,}|PRJNA\d{5,})\b")
LIMIT_RX = re.compile(r"[^.]*\b(limitation|limited by|caveat|we cannot exclude|remains to be determined|"
                      r"future studies|did not assess|was not assessed|small sample)\b[^.]*\.", re.I)

def _labels(text, table, case_terms=()):
    out = []
    for label, terms in table:
        if m(text, terms): out.append(label)
    for label, terms in case_terms:
        if _rx(tuple(terms), True).search(text or ""): out.append(label)
    return out

def central_targets(p, extra_text=""):
    """Targets in the title first, then those mentioned at least twice in abstract (+ full text)."""
    t = p.get("title", ""); body = (p.get("abstract", "") + " " + extra_text)
    title_hits = _labels(t, TARGETS, TARGETS_CS)
    body_hits = [lab for lab, terms in TARGETS if lab not in title_hits and count(body, terms) >= 2]
    body_hits += [lab for lab, terms in TARGETS_CS if lab not in title_hits and
                  len(_rx(tuple(terms), True).findall(body)) >= 2]
    return (title_hits + body_hits)[:6]

def _prune_models(ms):
    # Keep the most specific label: drop generic "mouse (in vivo)" if a specific mouse model is present, etc.
    if any(x in ms for x in ("knock-in mouse", "knockout / conditional mouse", "transgenic mouse")):
        ms = [x for x in ms if x != "mouse (in vivo)"]
    if any(x.startswith("human iPSC-derived") for x in ms):
        ms = [x for x in ms if x != "human iPSC-derived cells"]
    if any(x.startswith("primary ") and x != "primary neurons (other)" for x in ms):
        ms = [x for x in ms if x != "primary neurons (other)"]
    return ms

def _sec_text(root, rx):
    out = []
    for sec in root.iter("sec"):
        title = "".join(sec.findtext("title") or "")
        if re.search(rx, (sec.get("sec-type") or "") + " " + title, re.I):
            out.append(" ".join(sec.itertext()))
    return " ".join(out)

def fetch_fulltext(pmcid):
    """Europe PMC open-access full text -> dict of section texts. None if not available."""
    if not pmcid or not FULLTEXT_ENABLED: return None
    if pmcid in _FT_CACHE: return _FT_CACHE[pmcid]
    if len(_FT_CACHE) >= FULLTEXT_MAX: return None
    res = None
    try:
        r = session.get(EPMC_REST + pmcid + "/fullTextXML", timeout=40)
        if r.status_code == 200 and r.text.lstrip().startswith("<"):
            root = ET.fromstring(r.content)
            body = root.find(".//body")
            whole = " ".join(root.itertext())
            res = {"methods": _sec_text(root, r"method|materials|experimental procedures|star\W*methods"),
                   "results": _sec_text(root, r"^\s*results|results and discussion"),
                   "discussion": _sec_text(root, r"discussion|limitation"),
                   "figures": len(root.findall(".//fig")),
                   "has_body": body is not None, "all": whole}
    except Exception as e:
        print("full text skipped", pmcid, e)
    _FT_CACHE[pmcid] = res
    time.sleep(0.15)
    return res

def decision(p):
    s = p.get("section_score", 0)
    if p.get("section_id") == "focus" and m(p.get("title", ""), ["mapk8ip3", "jip3"]): return "Must read"
    if s >= 100: return "Must read"
    if s >= 82: return "Worth reading"
    return "Scan"

def analyse_card(p, sec):
    """Fill the card fields the app shows. Mutates and returns p."""
    ft = fetch_fulltext(p.get("pmcid")) if p.get("pmcid") else None
    full = bool(ft and ft.get("has_body"))
    methods_text = (ft or {}).get("methods", "") if full else ""
    study_text = methods_text or blob(p)
    tg = central_targets(p, (ft or {}).get("results", "") if full else "")
    if p.get("review"):
        p["models"] = []; p["methods"] = []
        scope = _prune_models(_labels(blob(p), MODELS))
        p["evidence_scope"] = scope[:6]
        p["review_topics"] = tg
    else:
        p["models"] = _prune_models(_labels(study_text, MODELS))[:6]
        p["methods"] = _labels(study_text, METHODS)[:8]
    p["targets"] = tg
    if full:
        p["analysis_depth"] = "full text (open access)"
        whole = ft.get("all", "")
        links = list(dict.fromkeys(mm.group(0).rstrip(".") for mm in LINK_RX.finditer(whole)))[:6]
        p["code_data_links"] = links
        p["data_accessions"] = list(dict.fromkeys(ACCESSION_RX.findall(whole)))[:6]
        lim = [mm.group(0).strip() for mm in LIMIT_RX.finditer(ft.get("discussion", ""))][:2]
        p["limitations"] = [x[:300] for x in lim]
        p["figure_count"] = ft.get("figures", 0)
    else:
        p["analysis_depth"] = "abstract-only" if p.get("abstract") else "title-only"
        p.setdefault("code_data_links", []); p.setdefault("data_accessions", []); p.setdefault("limitations", [])
    if p.get("pmcid"): p["pmc_url"] = "https://pmc.ncbi.nlm.nih.gov/articles/" + p["pmcid"] + "/"
    if p.get("preprint_doi") and not p.get("preprint_url"): p["preprint_url"] = "https://doi.org/" + p["preprint_doi"]
    p["decision"] = decision(p)
    why = [f"section: {TITLES.get(sec, sec)}"]
    if sec in KEYS and title_hit(p, sec): why.append("topic is in the title")
    if tg: why.append("central targets: " + ", ".join(tg[:4]))
    if p.get("models"): why.append("model: " + ", ".join(p["models"][:2]))
    why.append("source: " + p.get("journal_tier", tier(p.get("journal"))))
    if p.get("weekly"): why.append("published this week")
    p["why_shown"] = " · ".join(why)
    return p

def build_outputs(allp):
    allp = fold_preprints([enrich(p) for p in allp])
    # A paper found by one query also belongs to any other section its TITLE is about
    # (e.g. an axon-initial-segment paper found by the imaging query -> Cytoskeleton).
    for p in allp:
        for sec in TITLES:
            if sec not in p.get("sections", []) and m(p.get("title", ""), KEYS[sec]) and gate(p, sec):
                p["sections"] = p.get("sections", []) + [sec]
                p["matched_topics"] = p.get("matched_topics", []) + [TITLES[sec]]
    sections = {}; weekly_source = {}
    for sec in TITLES:
        items = ranked(allp, sec); weekly_source[sec] = items
        items = [p for p in items if p["age_days"] <= section_days(sec)]
        pri, seco = split_tiers(items)
        sections[sec] = {"id": sec, "title": TITLES[sec], "visible_count": VISIBLE[sec],
                         "weekly_count": sum(p["weekly"] for p in items),
                         "primary": pri[:30], "secondary": seco[:30], "best": best_mix(pri, seco)}
    rv = []
    for sec in TITLES: rv.extend(ranked(allp, sec, review=True))
    rv = dedupe(sorted(rv, key=lambda x: (x["section_score"], x.get("date", "")), reverse=True))
    rpri, rsec = split_tiers(rv)
    pp = []
    for sec in TITLES: pp.extend(ranked(allp, sec, preprint=True))
    pp = dedupe(sorted(pp, key=lambda x: (x["section_score"], x.get("date", "")), reverse=True))
    top10 = weekly_top10(weekly_source)
    # Card analysis (targets/models/methods/full text/decision/why) for everything the app can show.
    for sec, x in sections.items():
        for lst in (x["primary"], x["secondary"], x["best"]):
            for q in lst: analyse_card(q, sec)
    for q in top10: analyse_card(q, q.get("weekly_section") or q.get("section_id"))
    for q in rpri[:40] + rsec[:40] + pp[:50]: analyse_card(q, q.get("section_id"))
    counts = {s: {"primary": len(sections[s]["primary"]), "secondary": len(sections[s]["secondary"]),
                  "weekly": sections[s]["weekly_count"]} for s in sections}
    briefing = {"version": "0.32-cards-10-per-section", "generated_at_utc": NOW.isoformat(),
                "weekly_days": WEEK, "weekly_start": (NOW - timedelta(days=WEEK)).date().isoformat(),
                "weekly_end": NOW.date().isoformat(), "top10_weekly": top10, "sections": sections,
                "reviews": {"window_days": REVIEW_DAYS, "primary": rpri[:40], "secondary": rsec[:40]},
                "preprints": {"window_days": PREPRINT_DAYS, "papers": pp[:50]},
                "meta": {"total_unique_papers": len(allp), "weekly_highlight_count": len(top10),
                         "review_count": len(rv), "preprint_count": len(pp), "section_counts": counts}}
    legacy = sorted([p for p in allp if not is_preprint(p)], key=lambda x: x.get("date", ""), reverse=True)
    meta = {"project_name": "PaperScope", "last_updated_utc": NOW.isoformat(), "weekly_days": WEEK,
            "total_papers": len(allp), "weekly_highlight_count": len(top10), "reviews_count": len(rv),
            "preprints_count": len(pp), "section_counts": counts}
    audit = {"generated_at_utc": NOW.isoformat(),
             "weekly_top10": [dict(_brief(p), section=p.get("weekly_section")) for p in top10],
             "sections": {},
             "reviews": {"primary_count": len(rpri), "secondary_count": len(rsec), "top_primary": [_brief(p) for p in rpri[:10]]},
             "preprints": {"count": len(pp), "top": [_brief(p, ("sections",)) for p in pp[:12]]},
             "rejections_by_section": REJECTIONS}
    for sec in TITLES:
        x = sections[sec]
        audit["sections"][sec] = {"title": TITLES[sec], "primary_count": len(x["primary"]),
                                  "secondary_count": len(x["secondary"]), "weekly_count": x["weekly_count"],
                                  "top_primary": [_brief(p) for p in x["primary"][:8]],
                                  "top_secondary": [_brief(p) for p in x["secondary"][:8]]}
    return briefing, legacy, meta, audit

def main():
    print("PaperScope: recent peer-reviewed research")
    research = retrieve_research()
    print("PaperScope: independent review retrieval")
    reviews = retrieve_reviews()
    print("PaperScope: recent preprints")
    preprints = retrieve_preprints()
    merged = {}
    for st in [research, reviews, preprints]:
        for p in st.values(): merge(merged, p)
    briefing, legacy, meta, audit = build_outputs(list(merged.values()))
    (DATA / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    (DATA / "briefing.json").write_text(json.dumps(briefing, indent=2, ensure_ascii=False))
    (DATA / "papers.json").write_text(json.dumps(legacy, indent=2, ensure_ascii=False))
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"Wrote {meta['total_papers']} unique papers; {meta['weekly_highlight_count']} weekly highlights; "
          f"{meta['reviews_count']} reviews; {meta['preprints_count']} preprints")

if __name__ == "__main__":
    main()
