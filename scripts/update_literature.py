import os, json, re, time, html as htmlmod, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / 'config' / 'search_config.json').read_text())
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)

session = requests.Session()
email = os.getenv('USER_EMAIL', 'user@example.com')
api_key = os.getenv('NCBI_API_KEY')
session.headers.update({'User-Agent': f"PMpapers/1.0 ({email})"})

BASE_EUTIL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EUROPE_PMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'


def norm_title(x):
    return re.sub(r'\W+', ' ', (x or '').lower()).strip()


def first_sentences(text, n=4):
    s = [i.strip() for i in re.split(r'(?<=[.!?])\s+', text or '') if i.strip()]
    return s[:n]


def pubmed_search(term, retmax):
    params = {'db': 'pubmed', 'term': term, 'retmax': retmax, 'retmode': 'json', 'sort': 'pub date'}
    if api_key:
        params['api_key'] = api_key
    r = session.get(BASE_EUTIL + 'esearch.fcgi', params=params, timeout=45)
    r.raise_for_status()
    return r.json().get('esearchresult', {}).get('idlist', [])


def pubmed_fetch(ids, topic):
    if not ids:
        return []
    params = {'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'xml'}
    if api_key:
        params['api_key'] = api_key
    r = session.get(BASE_EUTIL + 'efetch.fcgi', params=params, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out = []
    for art in root.findall('.//PubmedArticle'):
        title_el = art.find('.//ArticleTitle')
        title = ''.join(title_el.itertext()).strip() if title_el is not None else ''
        if not title:
            continue
        abstract_parts = []
        for ab in art.findall('.//Abstract/AbstractText'):
            txt = ''.join(ab.itertext()).strip()
            if txt:
                label = ab.attrib.get('Label')
                abstract_parts.append((label + ': ' if label else '') + txt)
        abstract = ' '.join(abstract_parts)
        journal = art.findtext('.//Journal/Title') or ''
        pmid = art.findtext('.//PMID') or ''
        doi = ''
        for aid in art.findall('.//ArticleId'):
            if aid.attrib.get('IdType') == 'doi':
                doi = (aid.text or '').strip()
                break
        pmcid = ''
        for aid in art.findall('.//ArticleId'):
            if aid.attrib.get('IdType') == 'pmc':
                pmcid = (aid.text or '').strip()
                break
        year = None
        for path in ['.//PubDate/Year', './/ArticleDate/Year']:
            y = art.findtext(path)
            if y and y.isdigit():
                year = int(y)
                break
        if year is None:
            md = art.findtext('.//PubDate/MedlineDate') or ''
            m = re.search(r'(19|20)\d{2}', md)
            if m:
                year = int(m.group(0))
        authors = []
        for a in art.findall('.//Author')[:6]:
            ln = a.findtext('LastName') or ''
            ini = a.findtext('Initials') or ''
            cn = a.findtext('CollectiveName') or ''
            name = (ln + ' ' + ini).strip() if ln else cn
            if name:
                authors.append(name)
        pubtypes = [pt.text for pt in art.findall('.//PublicationType') if pt.text]
        out.append({
            'title': htmlmod.unescape(title), 'abstract': abstract, 'journal': journal, 'year': year or 0,
            'authors': ', '.join(authors), 'pmid': pmid, 'doi': doi, 'pmcid': pmcid,
            'review': 'Review' in pubtypes or 'Systematic Review' in pubtypes,
            'matched_topics': [topic], 'sources': ['PubMed'], 'pubmed_url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else ''
        })
    return out


def europe_pmc_search(term, topic, page_size):
    params = {'query': term, 'format': 'json', 'pageSize': page_size, 'resultType': 'core', 'sort': 'DATE_DESC'}
    r = session.get(EUROPE_PMC, params=params, timeout=45)
    r.raise_for_status()
    data = r.json()
    out = []
    for item in data.get('resultList', {}).get('result', []):
        title = (item.get('title') or '').strip()
        if not title:
            continue
        out.append({
            'title': title,
            'abstract': item.get('abstractText') or '',
            'journal': item.get('journalTitle') or item.get('journalInfo', {}).get('journal', {}).get('title', ''),
            'year': int(item.get('pubYear') or 0),
            'authors': item.get('authorString') or '',
            'pmid': item.get('pmid') or '',
            'doi': item.get('doi') or '',
            'pmcid': item.get('pmcid') or '',
            'review': 'review' in ((item.get('title') or '') + ' ' + (item.get('abstractText') or '')).lower(),
            'matched_topics': [topic],
            'sources': ['Europe PMC'],
            'pubmed_url': f"https://pubmed.ncbi.nlm.nih.gov/{item.get('pmid')}/" if item.get('pmid') else (f"https://europepmc.org/article/MED/{item.get('pmid')}" if item.get('pmid') else 'https://europepmc.org')
        })
    return out


def classify_and_score(p):
    txt = f"{p['title']} {p['abstract']} {p['journal']} {' '.join(p.get('matched_topics', []))}".lower()
    topic = p.get('matched_topics', ['General'])[0]
    top = any(j.lower() == (p.get('journal') or '').lower() for j in config['top_journals']) or any(j.lower() in (p.get('journal') or '').lower() for j in config['top_journals'])
    review = p.get('review') or (' review' in txt)
    year = p.get('year') or 0
    score = 60
    if topic == 'JIP3 / MAPK8IP3': score += 18
    elif topic == 'Lysosome transport': score += 14
    elif topic == 'Dynein / autophagosome': score += 12
    elif topic == 'Endosome maturation': score += 10
    else: score += 8
    if top: score += 10
    if review: score += 6
    if year >= datetime.now().year - 1: score += 8
    elif year >= datetime.now().year - 5: score += 4
    sents = first_sentences(p.get('abstract') or '', 5)
    overview = sents[0] if sents else 'Abstract not available from the current retrieval.'
    did = sents[1:4] if len(sents) > 1 else ['Detailed abstract text is not available for this record yet.']
    main = sents[4] if len(sents) > 4 else (sents[-1] if sents else 'Main message requires fuller abstract or full-text summarization.')
    p.update({
        'topic': topic, 'top': top, 'review': review, 'score': min(score, 99),
        'type': 'Review' if review else 'Primary research',
        'overview': overview,
        'did': did,
        'main': main,
        'why': f"Matched topic bucket: {topic}. This paper was pulled automatically from the configured literature sources.",
        'limits': 'This explanation is generated from title/abstract metadata and should be refined further for final scientific interpretation.'
    })
    return p


def key_for(p):
    return p.get('pmid') or p.get('doi') or norm_title(p.get('title'))


pool = []
for q in config['queries']:
    ids = pubmed_search(q['pubmed'], config['max_results_per_query'])
    pool.extend(pubmed_fetch(ids, q['topic']))
    time.sleep(0.34)
    pool.extend(europe_pmc_search(q['europepmc'], q['topic'], max(10, config['max_results_per_query'] // 2)))
    time.sleep(0.34)

merged = {}
for p in pool:
    k = key_for(p)
    if not k:
        continue
    if k not in merged:
        merged[k] = p
    else:
        old = merged[k]
        old['sources'] = sorted(set(old.get('sources', [])) | set(p.get('sources', [])))
        old['matched_topics'] = sorted(set(old.get('matched_topics', [])) | set(p.get('matched_topics', [])))
        if len(p.get('abstract', '')) > len(old.get('abstract', '')):
            old['abstract'] = p.get('abstract', '')
        if not old.get('doi') and p.get('doi'):
            old['doi'] = p['doi']
        if not old.get('pmid') and p.get('pmid'):
            old['pmid'] = p['pmid']
        if not old.get('pmcid') and p.get('pmcid'):
            old['pmcid'] = p['pmcid']
        if not old.get('journal') and p.get('journal'):
            old['journal'] = p['journal']
        if not old.get('authors') and p.get('authors'):
            old['authors'] = p['authors']
        if p.get('year', 0) > old.get('year', 0):
            old['year'] = p['year']

papers = [classify_and_score(p) for p in merged.values()]
papers.sort(key=lambda x: (x['score'], x.get('year', 0), len(x.get('abstract', ''))), reverse=True)

now = datetime.now(timezone.utc)
weekly_cutoff = int(now.timestamp()) - config.get('weekly_days', 30) * 86400
weekly_count = 0
for p in papers:
    p['sources_label'] = ', '.join(p.get('sources', []))
    p['matched_topics_label'] = ', '.join(p.get('matched_topics', []))
    if p.get('year', 0) >= now.year - 5:
        weekly_count += 1

meta = {
    'project_name': config.get('project_name', 'PMpapers'),
    'last_updated_utc': now.isoformat(),
    'source_counts': {
        'PubMed_or_linked': sum('PubMed' in p.get('sources', []) for p in papers),
        'Europe_PMC_or_linked': sum('Europe PMC' in p.get('sources', []) for p in papers)
    },
    'total_papers': len(papers),
    'weekly_days': config.get('weekly_days', 30),
    'top_journals_count': sum(bool(p.get('top')) for p in papers),
    'reviews_count': sum(bool(p.get('review')) for p in papers)
}

(DATA_DIR / 'papers.json').write_text(json.dumps(papers, indent=2))
(DATA_DIR / 'meta.json').write_text(json.dumps(meta, indent=2))
print(f"Wrote {len(papers)} papers")
