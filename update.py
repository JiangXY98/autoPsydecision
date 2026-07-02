from datetime import datetime, timezone, timedelta
import json
import requests
import os
import re
import pathlib
from openai import OpenAI

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_PER_KEYWORD_LIMIT = 10
OPENALEX_MAX_ARTICLES = 30
MAX_FUTURE_PUBLICATION_DAYS = 365

OPENALEX_QUERIES = {
    "dishonesty": [
        "dishonesty",
        "cheating",
        "deception",
        "honesty",
        "ethical decision making",
        "moral decision making",
        "moral identity",
        "self-concept maintenance",
        "reputation management",
    ],
    "decision_process": [
        "drift diffusion model",
        "HDDM",
        "evidence accumulation",
        "sequential sampling model",
        "computational psychiatry",
        "computational modeling",
        "reinforcement learning",
    ],
    "cognitive_control": [
        "cognitive control",
        "response inhibition",
        "conflict monitoring",
        "expected value of control",
    ],
    "consumer_decision": [
        "consumer decision making",
        "consumer behavior",
        "value-based decision making",
        "intertemporal choice",
        "delay discounting",
        "loss aversion",
        "risk preference",
    ],
    "additional_decision_topics": [
        "decision conflict",
        "choice architecture",
        "moral behavior",
        "honest behavior",
    ],
}

RELEVANCE_RULES = {
    "dishonesty": {
        "core": [
            "dishonesty",
            "cheating",
            "deception",
            "honesty",
            "honest behavior",
            "moral identity",
            "self concept maintenance",
            "reputation management",
        ],
        "domain": [
            "decision making",
            "choice",
            "behavior",
            "behaviour",
            "experiment",
            "participant",
            "psychology",
            "relationship",
            "consumer",
            "economic game",
            "social norm",
        ],
        "exclude": [
            "legal profession",
            "legal studies",
            "religious education",
            "islamic",
            "maqasid",
            "marriage",
            "wives rights",
            "anti corruption",
            "professional misconduct",
        ],
    },
    "decision_process": {
        "core": [
            "drift diffusion",
            "hddm",
            "evidence accumulation",
            "sequential sampling",
            "reinforcement learning",
            "computational psychiatry",
            "computational modeling",
            "computational modelling",
        ],
        "domain": [
            "choice",
            "behavior",
            "behaviour",
            "cognitive",
            "psychology",
            "psychiatry",
            "neural",
            "brain",
            "reward",
            "participant",
            "human",
        ],
        "exclude": [
            "lyapunov",
            "barrier function",
            "barrier functions",
            "robotics",
            "autonomous vehicle",
            "control systems",
        ],
    },
    "cognitive_control": {
        "core": [
            "cognitive control",
            "executive control",
            "self control",
            "response inhibition",
            "conflict monitoring",
            "expected value of control",
        ],
        "domain": [
            "decision",
            "choice",
            "behavior",
            "behaviour",
            "attention",
            "task",
            "inhibition",
            "conflict",
            "neural",
            "brain",
            "participant",
            "human",
        ],
    },
    "consumer_decision": {
        "core": [
            "consumer decision",
            "consumer behavior",
            "consumer behaviour",
            "value based decision",
            "value based choice",
            "intertemporal choice",
            "delay discounting",
            "loss aversion",
            "risk preference",
        ],
        "domain": [
            "consumer",
            "purchase",
            "choice",
            "decision",
            "preference",
            "behavior",
            "behaviour",
            "reward",
            "participant",
            "human",
        ],
    },
    "additional_decision_topics": {
        "core": [
            "decision conflict",
            "choice architecture",
            "moral behavior",
            "moral behaviour",
            "honest behavior",
        ],
        "domain": [
            "decision",
            "choice",
            "behavior",
            "behaviour",
            "experiment",
            "psychology",
            "social",
            "moral",
            "participant",
            "human",
        ],
    },
}

STRONG_TITLE_TERMS = {
    "dishonesty": [
        "dishonesty",
        "cheating",
        "deception",
        "prosocial lying",
    ],
    "decision_process": [
        "drift diffusion",
        "hddm",
        "evidence accumulation",
        "sequential sampling",
        "computational psychiatry",
    ],
    "cognitive_control": [
        "cognitive control",
        "executive control",
        "response inhibition",
        "conflict monitoring",
        "expected value of control",
    ],
    "consumer_decision": [
        "consumer decision",
        "consumer behavior",
        "intertemporal choice",
        "delay discounting",
        "loss aversion",
        "risk preference",
    ],
    "additional_decision_topics": [
        "decision conflict",
        "choice architecture",
        "moral behavior",
        "honest behavior",
    ],
}

access_token = os.getenv('GITHUB_TOKEN')
deepseekapikey = os.getenv('DEEPSEEK_API_KEY')
openalex_api_key = os.getenv('OPENALEX_API_KEY')

client = OpenAI(
    api_key=deepseekapikey,
    base_url="https://api.deepseek.com/v1"
)

JSON_PROMPT = """
You are a senior researcher in decision neuroscience and computational psychology.

You will be given the TITLE and ABSTRACT of a peer-reviewed journal article.

Evaluate conservatively based ONLY on the provided text.
Do not speculate or invent information not explicitly stated.

=== Scoring Guidelines ===

1. Research Quality Score (0–100)
Evaluate based on:
- Conceptual novelty
- Methodological rigor (design, modeling, statistics, sample; preregistration if mentioned)
- Data reliability (human data, clarity of sample, robustness indicators)

2. Potential Impact Score (0–100)
Evaluate based on:
- Relevance to self-control and attention in decision-making (e.g., reinforcement learning, deception, social norms)
- Potential to influence future research directions or theory
- Clarity of implications within the field

Do NOT assume media attention or policy uptake unless explicitly stated.

=== Tagging Rules ===

Select up to 3 topic tags from the ENUM list below that best describe the article.
Return an empty list if none apply.

TOPIC_TAGS_ENUM (choose only from these exact strings):
[
  "self_control",
  "inhibitory_control",
  "impulsivity",
  "attention",
  "salience",
  "value_based_choice",
  "reinforcement_learning",
  "belief_learning",
  "sequential_sampling",
  "deception_dishonesty",
  "moral_decision",
  "social_norms",
  "prosocial_choice",
  "economic_games",
  "effort_decision",
  "delay_discounting",
  "clinical_neuro",
  "neuroimaging_neurophys"
]

Also select any method tags mentioned explicitly in the text (0–5 tags).
METHOD_TAGS_ENUM (choose only from these exact strings):
[
  "ddm",
  "hddm",
  "ssm_eam", 
  "rl_modeling",
  "bayesian_modeling",
  "computational_modeling_general",
  "eye_tracking",
  "eeg",
  "fnirs",
  "fmri"
]

=== Output Format (STRICT JSON ONLY) ===

Return a valid JSON object only (no extra text):

{
  "research_quality_score": <integer 0-100>,
  "research_reasoning": "<2–3 concise sentences>",
  "potential_impact_score": <integer 0-100>,
  "impact_reasoning": "<2–3 concise sentences>",
  "topic_tags": ["<up to 3 from TOPIC_TAGS_ENUM>"],
  "method_tags": ["<0 to 5 from METHOD_TAGS_ENUM>"]
}
"""

def strip_html(x: str) -> str:
    return re.sub(r"<[^>]+>", " ", x or "").strip()

def normalize_for_match(x: str) -> str:
    x = strip_html(x).lower()
    x = re.sub(r"[-_/]", " ", x)
    x = re.sub(r"[^a-z0-9\s]", " ", x)
    return re.sub(r"\s+", " ", x).strip()

def matched_terms(text: str, terms):
    return [term for term in terms if normalize_for_match(term) in text]

def has_enough_text_for_filter(query_name: str, title: str, abstract: str):
    abstract_words = normalize_for_match(abstract).split()
    if len(abstract_words) >= 30:
        return True

    title_text = normalize_for_match(title)
    return bool(matched_terms(title_text, STRONG_TITLE_TERMS.get(query_name, [])))

def relevance_matches(query_name: str, title: str, abstract: str):
    rule = RELEVANCE_RULES.get(query_name)
    if not rule:
        return []

    if not has_enough_text_for_filter(query_name, title, abstract):
        return []

    text = normalize_for_match(f"{title} {abstract}")
    if matched_terms(text, rule.get("exclude", [])):
        return []

    core_matches = matched_terms(text, rule["core"])
    domain_matches = matched_terms(text, rule["domain"])

    if core_matches and domain_matches:
        return sorted(set(core_matches + domain_matches))

    return []

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for position in positions:
            words.append((position, word))

    return " ".join(word for _, word in sorted(words))

def extract_authors(authorships, max_authors=8):
    authors = []
    for authorship in authorships or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name and name not in authors:
            authors.append(name)

    if len(authors) > max_authors:
        return authors[:max_authors] + ["et al."]
    return authors

def extract_openalex_keywords(topics, max_keywords=6):
    keywords = []
    for topic in topics or []:
        name = topic.get("display_name")
        if name and name not in keywords:
            keywords.append(name)
    return keywords[:max_keywords]

def parse_openalex_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

def publication_date_is_reasonable(publication_date):
    parsed = parse_openalex_date(publication_date)
    if not parsed:
        return True
    latest_allowed = datetime.now(timezone.utc).date() + timedelta(days=MAX_FUTURE_PUBLICATION_DAYS)
    return parsed <= latest_allowed

def safe_json_loads(s: str):
    s = (s or "").strip()
    s = s.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start:end+1])
        raise
        
def extract_scores_and_reasons(title: str, abstract: str):
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": "You are a careful and conservative academic reviewer."},
            {
                "role": "user",
                "content": (
                    f"{JSON_PROMPT}\n\n"
                    f"=== Article to Evaluate ===\n"
                    f"TITLE:\n{title}\n\n"
                    f"ABSTRACT:\n{abstract}\n"
                ),
            },
        ],
        max_tokens=900,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    generated = response.choices[0].message.content.strip()

    # Defaults (robust fallback)
    research_score = "N/A"
    reasoning_research = "N/A"
    impact_score = "N/A"
    reasoning_impact = "N/A"
    topic_tags = []
    method_tags = []

    try:
        obj = safe_json_loads(generated)
        rq = obj.get("research_quality_score")
        pi = obj.get("potential_impact_score")
        if rq is not None:
            research_score = int(float(rq))
        if pi is not None:
            impact_score = int(float(pi))
        reasoning_research = str(obj.get("research_reasoning", "")).strip() or "N/A"
        reasoning_impact = str(obj.get("impact_reasoning", "")).strip() or "N/A"
        topic_tags = obj.get("topic_tags", []) or []
        method_tags = obj.get("method_tags", []) or []
    except Exception:
        print(f"Failed to parse model output for: {title}")
        print(generated[:500])

    return research_score, reasoning_research, impact_score, reasoning_impact, topic_tags, method_tags

def openalex_request(params):
    if not openalex_api_key:
        raise RuntimeError("OPENALEX_API_KEY is not set")

    params = dict(params)
    params["api_key"] = openalex_api_key
    response = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def add_openalex_work(articles_by_key, work, query_name, keyword):
    openalex_id = work.get("id") or ""
    doi = work.get("doi") or ""
    if not doi:
        return
    dedupe_key = doi.lower()

    title = work.get("title") or work.get("display_name") or "N/A"
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    local_matches = relevance_matches(query_name, title, abstract)
    if not local_matches:
        return

    source = ((work.get("primary_location") or {}).get("source") or {})
    journal = source.get("display_name") or "N/A"
    source_type = source.get("type") or "N/A"
    publication_date = work.get("publication_date") or "N/A"

    if source_type != "journal":
        return

    if journal.lower().startswith("frontiers in "):
        return

    if not publication_date_is_reasonable(publication_date):
        return

    article = articles_by_key.setdefault(dedupe_key, {
        "title": title,
        "authors": extract_authors(work.get("authorships")),
        "abstract": abstract,
        "keywords": extract_openalex_keywords(work.get("topics")),
        "doi": doi or "N/A",
        "journal": journal,
        "source_type": source_type,
        "created_date": work.get("created_date") or "N/A",
        "publication_date": publication_date,
        "openalex_id": openalex_id,
        "source_queries": [],
        "matched_relevance_terms": [],
    })
    source_label = f"keyword:{query_name}: {keyword}"
    if source_label not in article["source_queries"]:
        article["source_queries"].append(source_label)
    for term in local_matches:
        if term not in article["matched_relevance_terms"]:
            article["matched_relevance_terms"].append(term)

def get_openalex_articles():
    articles_by_key = {}
    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    date_filter_field = "from_created_date"
    sort_field = "created_date"
    fallback_notice_printed = False
    select = ",".join([
        "id",
        "doi",
        "title",
        "display_name",
        "created_date",
        "publication_date",
        "primary_location",
        "authorships",
        "topics",
        "abstract_inverted_index",
    ])

    for query_name, keywords in OPENALEX_QUERIES.items():
        for keyword in keywords:
            params = {
                "search": keyword,
                "filter": f"{date_filter_field}:{from_date},type:article",
                "per-page": OPENALEX_PER_KEYWORD_LIMIT,
                "sort": f"{sort_field}:desc",
                "select": select,
            }

            try:
                results = openalex_request(params).get("results", [])
            except requests.HTTPError as exc:
                if (
                    exc.response is not None
                    and exc.response.status_code == 429
                    and date_filter_field == "from_created_date"
                ):
                    date_filter_field = "from_publication_date"
                    sort_field = "publication_date"
                    if not fallback_notice_printed:
                        print("OpenAlex rejected from_created_date; falling back to from_publication_date.")
                        fallback_notice_printed = True
                    params["filter"] = f"{date_filter_field}:{from_date},type:article"
                    params["sort"] = f"{sort_field}:desc"
                    try:
                        results = openalex_request(params).get("results", [])
                    except requests.RequestException as fallback_exc:
                        print(f"OpenAlex request failed for {query_name}/{keyword}: {fallback_exc}")
                        continue
                else:
                    print(f"OpenAlex request failed for {query_name}/{keyword}: {exc}")
                    continue
            except requests.RequestException as exc:
                print(f"OpenAlex request failed for {query_name}/{keyword}: {exc}")
                continue

            for work in results:
                add_openalex_work(articles_by_key, work, query_name, keyword)

    articles = list(articles_by_key.values())
    articles.sort(key=lambda x: x.get("created_date") or "", reverse=True)
    return articles[:OPENALEX_MAX_ARTICLES]

openalex_articles = get_openalex_articles()
print(f"Fetched {len(openalex_articles)} unique OpenAlex articles for scoring.")

scored_articles = []

for abstract_data in openalex_articles:
    title = abstract_data["title"]
    abstract_clean = strip_html(abstract_data["abstract"])
    
    research_score, reasoning_research, impact_score, reasoning_impact, topic_tags, method_tags = extract_scores_and_reasons(
    title,
    abstract_clean
    )
    
    doi = abstract_data["doi"]
    journal = abstract_data["journal"]

    scored_articles.append({
        "title": title,
        "authors": abstract_data.get("authors", []),
        "abstract": abstract_clean,
        "keywords": abstract_data.get("keywords", []),
        "topic_tags": topic_tags,
        "method_tags": method_tags,
        "research_score": research_score,
        "reasoning_research": reasoning_research,
        "impact_score": impact_score,
        "reasoning_impact": reasoning_impact,
        "doi": doi,
        "journal": journal,
        "source_type": abstract_data.get("source_type", "N/A"),
        "created_date": abstract_data.get("created_date", "N/A"),
        "publication_date": abstract_data.get("publication_date", "N/A"),
        "openalex_id": abstract_data.get("openalex_id", "N/A"),
        "source_queries": abstract_data.get("source_queries", []),
        "matched_relevance_terms": abstract_data.get("matched_relevance_terms", []),
    })

issue_title = f"Weekly OpenAlex Literature Report - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the OpenAlex article scores and reasoning from the past week:\n\n"

if not scored_articles:
    issue_body += "No articles matched the current filters this week.\n"

for article_data in scored_articles:
    title = article_data["title"].strip()
    authors = article_data.get("authors", [])
    abstract = article_data.get("abstract", "").strip()
    research_score = article_data["research_score"]
    reasoning_research = article_data["reasoning_research"]
    impact_score = article_data["impact_score"]
    reasoning_impact = article_data["reasoning_impact"]
    journal = article_data["journal"].strip()
    publication_date = article_data.get("publication_date", "N/A")
    source_queries = article_data.get("source_queries", [])
    matched_relevance_terms = article_data.get("matched_relevance_terms", [])
    doi = (article_data["doi"] or "N/A").strip()
    doi_clean = doi.replace("doi:", "").replace("https://doi.org/", "").strip()
    doi_link = f"https://doi.org/{doi_clean}" if doi_clean != "N/A" and "/" in doi_clean else doi
    topic_tags = article_data.get("topic_tags", [])
    method_tags = article_data.get("method_tags", [])
    matched_filters = source_queries + [f"term:{term}" for term in matched_relevance_terms]

    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Authors**: {', '.join(authors) if authors else 'N/A'}\n"
    issue_body += f"  **Journal**: {journal}\n"
    issue_body += f"  **Publication date**: {publication_date}\n"
    issue_body += f"  **Keywords**: {', '.join(article_data.get('keywords', [])) if article_data.get('keywords') else 'N/A'}\n"
    issue_body += f"  **Abstract**: {abstract if abstract else 'N/A'}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Impact Score**: {impact_score}\n"
    issue_body += f"  **Reasoning**: Research: {reasoning_research} Impact: {reasoning_impact}\n"
    issue_body += f"  **DOI**: {doi_link}\n"
    openalex_id = article_data.get('openalex_id', 'N/A')
    issue_body += f"  **OpenAlex**: {openalex_id}\n"
    issue_body += f"  **Matched filters**: {', '.join(matched_filters) if matched_filters else 'N/A'}\n\n"

def create_github_issue(title, body, access_token):
    url = f"https://api.github.com/repos/JiangXY98/autoPsydecision/issues"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "title": title,
        "body": body
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 201:
        print("Issue created successfully!")
    else:
        print("Failed to create issue. Status code:", response.status_code)
        print("Response:", response.text)

create_github_issue(issue_title, issue_body, access_token)

run_date = datetime.now().strftime("%Y-%m-%d")
out_dir = pathlib.Path("data/weekly")
out_dir.mkdir(parents=True, exist_ok=True)

out_path = out_dir / f"{run_date}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(scored_articles, f, ensure_ascii=False, indent=2)
