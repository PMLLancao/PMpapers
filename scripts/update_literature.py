import os, json, re, time, html as htmlmod, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / 'config' / 'search_config.json').read_text())
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)

session = requests.Session()
email = os.getenv('USER_EMAIL', 'user@example.com')
api_key = os.getenv('NCBI_API_KEY')
session.headers.update({'User-Agent': f"PMpapers/2.1 ({email})"})

BASE_EUTIL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EUROPE_PMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
ARXIV_API = 'https://export.arxiv.org/api/query'
GOOGLE_NEWS_RSS = 'https://news.google.com/rss/search?q='
BIORXIV_RSS = 'https://www.biorxiv.org/rss.xml'
NS = {'atom': 'http://www.w3.org/2005/Atom'}


def norm_text(x):
    return re.sub(r'\s+', ' ', (x or '')).strip()


def norm_title(x):
    return re.sub(r'\W+', ' ', (x or '').lower()).strip()


def first_sentences(text, n=8):
    s = [i.strip() for i in re.split(r'(?<=[.!?])\s+', text or '') if i.strip()]
    return s[:n]


def key_for(p):
    return p.get('pmid') or p.get('doi') or p.get('url') or norm_title(p.get('title'))


def contains_query_terms(text, raw_query):
    text = (text or '').lower()
    toks = re.findall(r'[A-Za-z0-9\-]{4,}', raw_query)
    toks = [t.lower() for t in toks if t.lower() not in {'and', 'with', 'from', 'that', 'this', 'or', 'neuron'}]
    if not toks:
        return True
    return sum(t in text for t in toks[:8]) >= 1


def safe_get(url, params=None, timeout=45):
    last_err = None
    for _ in range(3):
        try:
            r = session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_err = e
            time.sleep(2)
    raise last_err


def pubmed_search(term, retmax):
    params = {'db': 'pubmed', 'term': term, 'retmax': retmax, 'retmode': 'json', 'sort': 'pub date'}
    if api_key:
        params['api_key'] = api_key
    r = safe_get(BASE_EUTIL + 'esearch.fcgi', params=params, timeout=45)
    return r.json().get('esearchresult', {}).get('idlist', [])


def pubmed_fetch(ids, topic):
    if not ids:
        return []
    params = {'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'xml'}
    if api_key:
        params['api_key'] = api_key
    r = safe_get(BASE_EUTIL + 'efetch.fcgi', params=params, timeout=60)
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
        year = 0
        for path in ['.//PubDate/Year', './/ArticleDate/Year']:
            y = art.findtext(path)
            if y and y.isdigit():
                year = int(y)
                break
        if not year:
            md = art.findtext('.//PubDate/MedlineDate') or ''
            m = re.search(r'(19|20)\d{2}', md)
            if m:
                year = int(m.group(0))
        authors = []
        for a in art.findall('.//Author')[:8]:
            ln = a.findtext('LastName') or ''
            ini = a.findtext('Initials') or ''
            cn = a.findtext('CollectiveName') or ''
            name = (ln + ' ' + ini).strip() if ln else cn
            if name:
                authors.append(name)
        pubtypes = [pt.text for pt in art.findall('.//PublicationType') if pt.text]
        out.append({
            'title': htmlmod.unescape(title),
            'abstract': abstract,
            'journal': journal,
            'year': year,
            'authors': ', '.join(authors),
            'pmid': pmid,
            'doi': doi,
            'review': 'Review' in pubtypes or 'Systematic Review' in pubtypes,
            'matched_topics': [topic],
            'sources': ['PubMed'],
            'source_type': 'paper',
            'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else 'https://pubmed.ncbi.nlm.nih.gov/'
        })
    return out


def europe_pmc_search(term, topic, page_size):
    params = {'query': term, 'format': 'json', 'pageSize': page_size, 'resultType': 'core', 'sort': 'DATE_DESC'}
    r = safe_get(EUROPE_PMC, params=params, timeout=45)
    data = r.json()
    out = []
    for item in data.get('resultList', {}).get('result', []):
        title = norm_text(item.get('title'))
        if not title:
            continue
        pmid = item.get('pmid') or ''
        url = f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else 'https://europepmc.org'
        out.append({
            'title': title,
            'abstract': item.get('abstractText') or '',
            'journal': item.get('journalTitle') or item.get('journalInfo', {}).get('journal', {}).get('title', ''),
            'year': int(item.get('pubYear') or 0),
            'authors': item.get('authorString') or '',
            'pmid': pmid,
            'doi': item.get('doi') or '',
            'review': 'review' in ((item.get('title') or '') + ' ' + (item.get('abstractText') or '')).lower(),
            'matched_topics': [topic],
            'sources': ['Europe PMC'],
            'source_type': 'paper',
            'url': url
        })
    return out


def google_news_search(term, topic, limit=8):
    q = quote_plus(term)
    url = GOOGLE_NEWS_RSS + q + '&hl=en-US&gl=US&ceid=US:en'
    r = safe_get(url, timeout=45)
    root = ET.fromstring(r.text)
    out = []
    items = root.findall('.//item')[:limit]
    year = datetime.now(timezone.utc).year
    for item in items:
        title = norm_text(item.findtext('title') or '')
        desc = htmlmod.unescape(item.findtext('description') or '')
        link = item.findtext('link') or 'https://news.google.com/'
        source = ''
        src_el = item.find('source')
        if src_el is not None and src_el.text:
            source = src_el.text.strip()
        if not contains_query_terms(title + ' ' + desc, term):
            continue
        out.append({
            'title': title,
            'abstract': re.sub(r'<[^>]+>', ' ', desc),
            'journal': source or 'Google News',
            'year': year,
            'authors': source or 'News source',
            'pmid': '',
            'doi': '',
            'review': False,
            'matched_topics': [topic],
            'sources': ['Google News'],
            'source_type': 'news',
            'url': link
        })
    return out


def biorxiv_search(term, topic, limit=8):
    r = safe_get(BIORXIV_RSS, timeout=45)
    root = ET.fromstring(r.text)
    out = []
    for item in root.findall('.//item'):
        title = norm_text(item.findtext('title') or '')
        desc = htmlmod.unescape(item.findtext('description') or '')
        link = item.findtext('link') or 'https://www.biorxiv.org/'
        pub = item.findtext('pubDate') or ''
        year_match = re.search(r'(20\d{2})', pub)
        year = int(year_match.group(1)) if year_match else datetime.now(timezone.utc).year
        blob = (title + ' ' + desc).lower()
        if not contains_query_terms(blob, term):
            continue
        out.append({
            'title': title,
            'abstract': re.sub(r'<[^>]+>', ' ', desc),
            'journal': 'bioRxiv',
            'year': year,
            'authors': 'bioRxiv preprint',
            'pmid': '',
            'doi': '',
            'review': 'review' in blob,
            'matched_topics': [topic],
            'sources': ['bioRxiv'],
            'source_type': 'preprint',
            'url': link
        })
        if len(out) >= limit:
            break
    return out


def arxiv_search(term, topic, limit=8):
    query = f'(cat:q-bio.NC) AND all:"{term}"'
    params = {'search_query': query, 'start': 0, 'max_results': limit, 'sortBy': 'submittedDate', 'sortOrder': 'descending'}
    r = safe_get(ARXIV_API, params=params, timeout=45)
    root = ET.fromstring(r.text)
    out = []
    for entry in root.findall('atom:entry', NS):
        title = norm_text(entry.findtext('atom:title', default='', namespaces=NS))
        summary = norm_text(entry.findtext('atom:summary', default='', namespaces=NS))
        link = entry.findtext('atom:id', default='https://arxiv.org', namespaces=NS)
        published = entry.findtext('atom:published', default='', namespaces=NS)
        year_match = re.search(r'(20\d{2})', published)
        year = int(year_match.group(1)) if year_match else datetime.now(timezone.utc).year
        authors = ', '.join(norm_text(a.findtext('atom:name', default='', namespaces=NS)) for a in entry.findall('atom:author', NS))
        if not contains_query_terms(title + ' ' + summary, term):
            continue
        out.append({
            'title': title,
            'abstract': summary,
            'journal': 'arXiv q-bio.NC',
            'year': year,
            'authors': authors,
            'pmid': '',
            'doi': '',
            'review': 'review' in (title + ' ' + summary).lower(),
            'matched_topics': [topic],
            'sources': ['arXiv'],
            'source_type': 'preprint',
            'url': link
        })
    return out


def try_source(label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"Skipping {label}: {e}")
        return []


def classify_and_score(p):
    txt = f"{p.get('title','')} {p.get('abstract','')} {p.get('journal','')} {' '.join(p.get('matched_topics', []))}".lower()
    primary_topic = p.get('matched_topics', ['General'])[0]
    top = any(j.lower() == (p.get('journal') or '').lower() for j in config.get('top_journals', [])) or any(j.lower() in (p.get('journal') or '').lower() for j in config.get('top_journals', []))
    review = p.get('review') or (' review' in txt)
    year = p.get('year') or 0
    score = 60
    if primary_topic == 'JIP3 / MAPK8IP3':
        score += 18
    elif primary_topic == 'Lysosome transport':
        score += 14
    elif primary_topic == 'Dynein / autophagosome':
        score += 12
    elif primary_topic == 'Endosome maturation':
        score += 10
    else:
        score += 8
    if top:
        score += 10
    if review:
        score += 6
    if year >= datetime.now().year - 1:
        score += 8
    elif year >= datetime.now().year - 5:
        score += 4
    if 'Google News' in p.get('sources', []):
        score -= 6
    sents = first_sentences(p.get('abstract') or '', 8)
    overview = sents[0] if sents else 'Summary not available from the current record.'
    did = sents[1:5] if len(sents) > 1 else ['Detailed abstract text is not available for this record yet.']
    main = sents[5] if len(sents) > 5 else (sents[-1] if sents else 'Main message requires fuller source text.')
    context = sents[6] if len(sents) > 6 else (sents[-1] if sents else 'Context not available from the current metadata.')
    p.update({
        'topic': primary_topic,
        'top': top,
        'review': review,
        'score': max(min(score, 99), 1),
        'type': 'Review' if review else ('News / signal' if p.get('source_type') == 'news' else 'Primary research'),
        'overview': overview,
        'did': did,
        'main': main,
        'context': context,
        'why': f"Matched topics: {', '.join(p.get('matched_topics', []))}. Sources: {', '.join(p.get('sources', []))}.",
        'limits': 'This explanation is generated from titles, abstracts, feeds, or snippets and may need manual verification before deep interpretation.'
    })
    return p


pool = []
max_results = int(config.get('max_results_per_query', 20))
for q in config['queries']:
    ids = try_source('PubMed search', pubmed_search, q['pubmed'], max_results)
    pool.extend(try_source('PubMed fetch', pubmed_fetch, ids, q['topic']))
    time.sleep(0.34)
    pool.extend(try_source('Europe PMC', europe_pmc_search, q['europepmc'], q['topic'], max(10, max_results // 2)))
    time.sleep(0.34)
    pool.extend(try_source('Google News', google_news_search, q['topic'], q['topic'], 8))
    time.sleep(0.34)
    pool.extend(try_source('arXiv', arxiv_search, q['topic'], q['topic'], 8))
    time.sleep(0.34)
    pool.extend(try_source('bioRxiv', biorxiv_search, q['topic'], q['topic'], 8))
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
        old['matched_topics'] = list(dict.fromkeys(old.get('matched_topics', []) + p.get('matched_topics', [])))
        if len(p.get('abstract', '')) > len(old.get('abstract', '')):
            old['abstract'] = p.get('abstract', '')
        for field in ['doi', 'pmid', 'journal', 'authors', 'url']:
            if not old.get(field) and p.get(field):
                old[field] = p[field]
        if p.get('year', 0) > old.get('year', 0):
            old['year'] = p['year']

papers = [classify_and_score(p) for p in merged.values()]
papers.sort(key=lambda x: (x['score'], x.get('year', 0), len(x.get('abstract', ''))), reverse=True)

now = datetime.now(timezone.utc)
for p in papers:
    p['sources_label'] = ', '.join(p.get('sources', []))
    p['matched_topics_label'] = ', '.join(p.get('matched_topics', []))

meta = {
    'project_name': config.get('project_name', 'PMpapers'),
    'last_updated_utc': now.isoformat(),
    'configured_topics': [q['topic'] for q in config['queries']],
    'total_papers': len(papers),
    'weekly_days': config.get('weekly_days', 30),
    'source_counts': {
        'PubMed': sum('PubMed' in p.get('sources', []) for p in papers),
        'Europe PMC': sum('Europe PMC' in p.get('sources', []) for p in papers),
        'Google News': sum('Google News' in p.get('sources', []) for p in papers),
        'bioRxiv': sum('bioRxiv' in p.get('sources', []) for p in papers),
        'arXiv': sum('arXiv' in p.get('sources', []) for p in papers)
    },
    'top_journals_count': sum(bool(p.get('top')) for p in papers),
    'reviews_count': sum(bool(p.get('review')) for p in papers)
}

(DATA_DIR / 'papers.json').write_text(json.dumps(papers, indent=2))
(DATA_DIR / 'meta.json').write_text(json.dumps(meta, indent=2))
print(f"Wrote {len(papers)} papers")
