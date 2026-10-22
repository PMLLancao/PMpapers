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
session.headers.update({"User-Agent": f"PaperScope/0.30 ({email})"})
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
VISIBLE = {k:(10 if k=="signaling" else 5) for k in TITLES}
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
GLOBAL_EXCLUDE = [
    "traditional chinese medicine","chinese herbal medicine","herbal medicine",
    "ethnopharmacology","phytotherapy","acupuncture","homeopathy","ayurvedic",
    "aquaculture","plant disease","crop","veterinary","dog bite"
]
NONPREFERRED = ["drosophila","zebrafish","caenorhabditis","c. elegans","yeast","arabidopsis","sea cucumber","hamster"]
UNRELATED = ["kidney","renal","hepatic","liver","cardiac","myocard","skin disease","dermat","pulmonary fibrosis","bone disease","intestinal","gut microbi"]
NEURAL = ["neuron","neuronal","brain","axon","dendrite","microglia","astrocyte","glia","ipsc","organoid","hippocamp","cortex","motor neuron","neural progenitor","oligodendrocyte","synapse","synaptic"]
CELLBIO = ["hela","hek293","u2os","fibroblast","mef","raw 264.7","macrophage"]
KEYS = {
    "focus":["mapk8ip3","jip3","jip4"],
    "neurodevelopment":["neurodevelopment","intellectual disability","autism","rare disease","axon guidance","commissure","corpus callosum","cc2d1a","cc2d1b"],
    "organelle":["lysosome","lysosomal","endosome","endosomal","lysophagy","lysosomal damage","lysosomal membrane","lysosomal repair","lysosomal exocytosis"],
    "trafficking":["retromer","retriever","wash complex","commander","exocyst","escrt","hops","corvet","intracellular trafficking","membrane trafficking","axonal transport","organelle transport","rab7","rab10","rab12","rab36"],
    "cytoskeleton":["cytoskeleton","microtubule","actin","dynein","dynactin","kinesin","myosin","neuronal polarity","growth cone"],
    "ipsc":["ipsc","induced pluripotent stem cell","patient-derived"],
    "omics":["proteomics","phosphoproteomics","interactomics","lipidomics","metabolomics","rna-seq","rna sequencing","transcriptomics","single-cell","single cell","spatial transcriptomics","spatial omics","atac-seq","crispr screen"],
    "imaging":["microscopy","confocal","live-cell imaging","live cell imaging","super-resolution","sted","sim","palm","storm","flim","fret","electron microscopy","correlative microscopy","light-sheet","high-content imaging"],
    "analysis-tools":["imagej","fiji","napari","cellprofiler","qupath","segmentation","tracking","particle tracking","kymograph","neurite tracing","sholl","colocalization","puncta","image analysis","single-cell analysis","spatial transcriptomics analysis"],
    "signaling":["camp","cyclic amp","epac","pka","akap","akt","pi3k","mtor","cc2d1a","cc2d1b","rab7","rab10","rab12","rab36","rab gtpase","rhoa","rhob","rhoc","rac1","rac2","rac3","cdc42","rho gtpase","tmem55b","rilpl1","tbk1","sting","chmp4b","spag9"],
    "extracellular":["extracellular vesicle","exosome","lysosomal exocytosis","lysosomal secretion"],
    "neurodegeneration":["parkinson","lrrk2","amyotrophic lateral sclerosis","frontotemporal dementia","alzheimer","neurodegeneration"]
}

def norm(x):
    return re.sub(r"[^a-z0-9]+"," ",str(x or "").lower()).strip()

def exact(text, term):
    return re.search(r"(?<![A-Za-z0-9])"+re.escape(term)+r"(?![A-Za-z0-9])",text or "",re.I) is not None

def has(text, arr):
    t=(text or "").lower()
    return any(x.lower() in t for x in arr)

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
            pmid=art.findtext(".//PMID") or "";doi="";pmcid=""
            for aid in art.findall(".//ArticleId"):
                if aid.attrib.get("IdType")=="doi":doi=(aid.text or "").strip()
                if aid.attrib.get("IdType")=="pmc":pmcid=(aid.text or "").strip()
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
                "authors":", ".join(auth),"pmid":pmid,"pmcid":pmcid,"doi":doi,
                "review":rev,"publication_types":pts,"sections":[section],
                "matched_topics":[TITLES[section]],"retrieval_lanes":[lane],
                "sources":["PubMed"],"source_type":"paper",
                "url":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            })
    return out

def tier(journal):
    j=norm(journal)
    if any(j==norm(x) for x in EXCLUDED):return "Excluded"
    if any(j==norm(x) for x in SECONDARY):return "Secondary"
    if any(j==norm(x) for x in PRIMARY):return "Primary / trusted"
    return "Uncurated"

def blob(p):
    return f"{p.get('title','')} {p.get('abstract','')}"

def global_reject(p):
    b=blob(p).lower()
    if any(x in b for x in GLOBAL_EXCLUDE):return True
    if tier(p.get("journal"))=="Excluded":return True
    if has(b,UNRELATED) and not has(b,NEURAL):return True
    if re.search(r"\b(cancer|carcinoma|tumou?r|glioblastoma)\b",b,re.I) and has(b,["therapy","metastasis","survival","prognosis","chemoresistance","tumor growth"]):return True
    return False

def signaling_central(p):
    title=p.get("title","");abstract=p.get("abstract","")
    for t in KEYS["signaling"]:
        if exact(title,t) or (len(t)>5 and t in title.lower()):return True
        if len(re.findall(r"(?<![A-Za-z0-9])"+re.escape(t)+r"(?![A-Za-z0-9])",abstract,re.I))>=2:return True
    return False

def gate(p, section):
    b=blob(p).lower()
    if global_reject(p):return False
    if section!="focus" and has(b,NONPREFERRED):return False
    neural=has(b,NEURAL); cellbio=has(b,CELLBIO)
    if section=="focus":
        return exact(b,"MAPK8IP3") or exact(b,"JIP3") or (exact(b,"JIP4") and has(b,["neuron","axon","lysosome","endosome","transport"]))
    if section=="neurodevelopment":return neural and has(b,KEYS[section])
    if section=="organelle":return (neural or cellbio) and has(b,KEYS[section])
    if section=="trafficking":return (neural or cellbio) and has(b,KEYS[section])
    if section=="cytoskeleton":return neural and has(b,KEYS[section])
    if section=="ipsc":return has(b,KEYS[section]) and has(b,["neuron","microglia","astrocyte","oligodendrocyte","glia","organoid","motor neuron","neural progenitor"])
    if section=="omics":
        method=has(b,KEYS[section]); relevant=neural or has(b,["lysosome","endosome","trafficking","cytoskeleton","neurodevelopment","neurodegeneration","jip3","mapk8ip3","lrrk2"])
        return method and relevant
    if section=="imaging":
        method=has(b,KEYS[section]); relevant=neural or has(b,["lysosome","endosome","trafficking","organelle","jip3","mapk8ip3"])
        methodpaper=has(b,["method","protocol","workflow","platform","technique"])
        return method and (relevant or methodpaper)
    if section=="analysis-tools":
        method=has(b,KEYS[section]); tool=has(b,["software","tool","plugin","package","workflow","pipeline","algorithm","framework","resource","benchmark"])
        return method and tool
    if section=="signaling":
        return signaling_central(p) and (neural or cellbio or has(b,["lysosome","endosome","trafficking","autophagy"]))
    if section=="extracellular":return neural and has(b,KEYS[section])
    if section=="neurodegeneration":
        return has(b,KEYS[section]) and neural and has(b,["lysosome","endosome","autophagy","trafficking","axon","cytoskeleton","microtubule","rab","rho","iron","ferroptosis","microglia","astrocyte","mitochond"])
    return False

def age_days(p):
    try:return max(0,(NOW.date()-datetime.fromisoformat(p.get("date","")).date()).days)
    except:return 99999

def centrality(p, section):
    t=p.get("title","");a=p.get("abstract","");n=0
    for term in KEYS[section]:
        if exact(t,term) or (len(term)>5 and term in t.lower()):n+=8
        elif exact(a,term) or (len(term)>5 and term in a.lower()):n+=2
    return min(24,n)

def score(p, section, review=False):
    age=age_days(p);s=40+centrality(p,section)
    if section=="focus":s+=18
    if age<=7:s+=30
    elif age<=30:s+=22
    elif age<=90:s+=14
    elif age<=180:s+=7
    elif age<=365:s+=2
    else:s-=min(15,((age-365)//180)*2)
    t=tier(p.get("journal"))
    if t=="Primary / trusted":s+=10
    elif t=="Secondary":s+=3
    else:s-=2
    if review:
        if any(norm(p.get("journal"))==norm(x) for x in HIGH_REVIEW):s+=16
        if age<=180:s+=8
    return int(s)

def first_sentences(x,n=8):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+",x or "") if s.strip()][:n]

def enrich(p):
    ss=first_sentences(p.get("abstract"),8)
    p["overview"]=ss[0] if ss else "Abstract not available from the current source."
    result=next((s for s in ss[1:] if re.search(r"\b(we found|we show|we demonstrate|results|revealed|increased|decreased|impair|promot|required|drives|regulates)\b",s,re.I)),None)
    p["main"]=(ss[-1] if p.get("review") and ss else result or (ss[-1] if ss else "Open the paper for details."))
    p["journal_tier"]=tier(p.get("journal"));p["age_days"]=age_days(p);p["weekly"]=p["age_days"]<=WEEK
    p["sources_label"]=", ".join(p.get("sources",[]));p["matched_topics_label"]=", ".join(p.get("matched_topics",[]))
    return p

def pkey(p):
    return p.get("pmid") or p.get("doi") or norm(p.get("title"))

def merge(store,p):
    k=pkey(p)
    if not k:return
    if k not in store:store[k]=p;return
    o=store[k]
    for f in ["sections","matched_topics","retrieval_lanes","sources"]:
        o[f]=list(dict.fromkeys(o.get(f,[])+p.get(f,[])))
    if len(p.get("abstract",""))>len(o.get("abstract","")):o["abstract"]=p["abstract"]
    for f in ["doi","pmid","pmcid","journal","authors","url","date"]:
        if not o.get(f) and p.get(f):o[f]=p[f]
    o["review"]=o.get("review") or p.get("review")

def retrieve_research():
    store={}
    for q in CFG["queries"]:
        sec=TOPIC_SECTION.get(q["topic"])
        if not sec:continue
        days=FOCUS_BACKFILL if sec=="focus" else RECENT
        ids=list(dict.fromkeys(pubmed_search(q["pubmed"],35,WEEK)+pubmed_search(q["pubmed"],70,days)))
        for p in fetch_pubmed(ids,sec,"weekly+recent"):
            if not p.get("review") and gate(p,sec):merge(store,p)
    return store

def retrieve_reviews():
    store={}
    for q in CFG["queries"]:
        sec=TOPIC_SECTION.get(q["topic"])
        if not sec:continue
        term=f"({q['pubmed']}) AND (review[Publication Type] OR systematic review[Publication Type] OR meta-analysis[Publication Type])"
        ids=pubmed_search(term,28,REVIEW_DAYS)
        for p in fetch_pubmed(ids,sec,"independent-review"):
            p["review"]=True
            if gate(p,sec):merge(store,p)
    return store

def retrieve_preprints():
    store={}
    start=(NOW-timedelta(days=PREPRINT_DAYS)).date().isoformat();end=NOW.date().isoformat()
    for q in CFG["queries"]:
        sec=TOPIC_SECTION.get(q["topic"])
        if not sec:continue
        # Europe PMC indexes bioRxiv/medRxiv preprints and lets us enforce dates.
        query=f'SRC:PPR AND FIRST_PDATE:[{start} TO {end}] AND ({q["europepmc"]})'
        params={"query":query,"format":"json","pageSize":30,"resultType":"core","sort":"FIRST_PDATE_D desc"}
        try:data=safe_get(EPMC,params).json()
        except Exception as e:
            print("preprint search skipped",sec,e);continue
        for it in data.get("resultList",{}).get("result",[]):
            d=(it.get("firstPublicationDate") or it.get("firstIndexDate") or "")[:10]
            p={"title":it.get("title") or "","abstract":it.get("abstractText") or "",
               "journal":it.get("journalTitle") or "bioRxiv / preprint","date":d,
               "year":int(d[:4]) if d[:4].isdigit() else 0,"authors":it.get("authorString") or "",
               "pmid":it.get("pmid") or "","pmcid":it.get("pmcid") or "","doi":it.get("doi") or "",
               "review":False,"sections":[sec],"matched_topics":[TITLES[sec]],"retrieval_lanes":["preprint"],
               "sources":["Europe PMC preprint"],"source_type":"preprint",
               "url":("https://doi.org/"+it["doi"]) if it.get("doi") else "https://europepmc.org/"}
            if p["title"] and gate(p,sec):merge(store,p)
        pause()
    return store

def dedupe(items):
    seen=set();out=[]
    for p in items:
        k=norm(p.get("title"))
        if k and k not in seen:seen.add(k);out.append(p)
    return out

def ranked(allp, sec, review=False, preprint=False):
    out=[]
    for p in allp:
        if sec not in p.get("sections",[]):continue
        if bool(p.get("review"))!=bool(review):continue
        if (p.get("source_type")=="preprint")!=bool(preprint):continue
        if not gate(p,sec):continue
        q=dict(p);q["section_id"]=sec;q["section_score"]=score(q,sec,review);out.append(q)
    out.sort(key=lambda x:(x["section_score"],x.get("date","")),reverse=True)
    return dedupe(out)

def split_tiers(items):
    pri=[];sec=[]
    for p in items:
        if p["journal_tier"]=="Primary / trusted":pri.append(p)
        elif p["journal_tier"] in {"Secondary","Uncurated"}:sec.append(p)
    return pri,sec

def weekly_top10(section_lists):
    c=[]
    for sec,items in section_lists.items():
        for p in items:
            if p.get("weekly"):
                q=dict(p);q["weekly_section"]=sec;q["weekly_score"]=q["section_score"]+(8 if q["journal_tier"]=="Primary / trusted" else 2 if q["journal_tier"]=="Secondary" else 0);c.append(q)
    c.sort(key=lambda x:(x["weekly_score"],x.get("date","")),reverse=True)
    out=[];seen=set();sc={};jc={}
    for p in c:
        k=norm(p["title"]);sec=p["weekly_section"];j=norm(p.get("journal"))
        if k in seen or sc.get(sec,0)>=2 or jc.get(j,0)>=2:continue
        out.append(p);seen.add(k);sc[sec]=sc.get(sec,0)+1;jc[j]=jc.get(j,0)+1
        if len(out)==10:break
    if len(out)<10:
        for p in c:
            k=norm(p["title"])
            if k in seen:continue
            out.append(p);seen.add(k)
            if len(out)==10:break
    return out[:10]

def main():
    print("PaperScope: recent peer-reviewed research")
    research=retrieve_research()
    print("PaperScope: independent review retrieval")
    reviews=retrieve_reviews()
    print("PaperScope: recent preprints")
    preprints=retrieve_preprints()
    merged={}
    for st in [research,reviews,preprints]:
        for p in st.values():merge(merged,p)
    allp=[enrich(p) for p in merged.values()]
    sections={};weekly_source={}
    for sec in TITLES:
        items=ranked(allp,sec);weekly_source[sec]=items
        maxage=FOCUS_BACKFILL if sec=="focus" else RECENT
        items=[p for p in items if p["age_days"]<=maxage]
        pri,seco=split_tiers(items)
        sections[sec]={"id":sec,"title":TITLES[sec],"visible_count":VISIBLE[sec],
                       "weekly_count":sum(p["weekly"] for p in items),
                       "primary":pri[:30],"secondary":seco[:30]}
    rv=[]
    for sec in TITLES:rv.extend(ranked(allp,sec,review=True))
    rv=dedupe(sorted(rv,key=lambda x:(x["section_score"],x.get("date","")),reverse=True))
    rpri,rsec=split_tiers(rv)
    pp=[]
    for sec in TITLES:pp.extend(ranked(allp,sec,preprint=True))
    pp=dedupe(sorted(pp,key=lambda x:(x["section_score"],x.get("date","")),reverse=True))
    top10=weekly_top10(weekly_source)
    briefing={"version":"0.30-weekly-structured","generated_at_utc":NOW.isoformat(),
              "weekly_days":WEEK,"weekly_start":(NOW-timedelta(days=WEEK)).date().isoformat(),
              "weekly_end":NOW.date().isoformat(),"top10_weekly":top10,"sections":sections,
              "reviews":{"window_days":REVIEW_DAYS,"primary":rpri[:40],"secondary":rsec[:40]},
              "preprints":{"window_days":PREPRINT_DAYS,"papers":pp[:50]},
              "meta":{"total_unique_papers":len(allp),"weekly_highlight_count":len(top10),
                      "review_count":len(rv),"preprint_count":len(pp),
                      "section_counts":{s:{"primary":len(sections[s]["primary"]),"secondary":len(sections[s]["secondary"]),"weekly":sections[s]["weekly_count"]} for s in sections}}}
    legacy=sorted([p for p in allp if p.get("source_type")!="preprint"],key=lambda x:x.get("date",""),reverse=True)
    meta={"project_name":"PaperScope","last_updated_utc":NOW.isoformat(),"weekly_days":WEEK,
          "total_papers":len(allp),"weekly_highlight_count":len(top10),"reviews_count":len(rv),
          "preprints_count":len(pp),"section_counts":briefing["meta"]["section_counts"]}
    (DATA/"briefing.json").write_text(json.dumps(briefing,indent=2,ensure_ascii=False))
    (DATA/"papers.json").write_text(json.dumps(legacy,indent=2,ensure_ascii=False))
    (DATA/"meta.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False))
    print(f"Wrote {len(allp)} unique papers; {len(top10)} weekly highlights; {len(rv)} reviews; {len(pp)} preprints")

if __name__=="__main__":
    main()
