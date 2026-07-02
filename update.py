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
        "reputation concern",
        "prosocial lying",
    ],
    "decision_process": [
        "drift diffusion model",
        "diffusion model decision making",
        "HDDM",
        "evidence accumulation",
        "sequential sampling model",
        "decision process model",
        "boundary separation",
        "drift rate",
        "nondecision time",
        "RLDDM",
    ],
    "cognitive_control": [
        "cognitive control",
        "executive control",
        "self-control",
        "response inhibition",
        "conflict monitoring",
        "mental effort",
        "effort allocation",
        "expected value of control",
    ],
    "consumer_decision": [
        "consumer neuroscience",
        "consumer decision making",
        "consumer behavior",
        "value-based decision",
        "purchase decision",
        "choice behavior",
        "intertemporal choice",
        "loss aversion",
        "risk preference",
        "decision under uncertainty",
    ],
    "computational_neuroscience": [
        "computational psychiatry",
        "computational cognitive neuroscience",
        "computational modeling",
        "latent decision process",
        "computational phenotyping",
        "hierarchical Bayesian",
        "reinforcement learning decision making",
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

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for position in positions:
            words.append((position, word))

    return " ".join(word for _, word in sorted(words))

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
        max_tokens=500,
        temperature=0.2,
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
        # Keep N/A; optionally log generated for debugging
        pass

    return research_score, reasoning_research, impact_score, reasoning_impact, topic_tags, method_tags

def openalex_request(params):
    if not openalex_api_key:
        raise RuntimeError("OPENALEX_API_KEY is not set")

    params = dict(params)
    params["api_key"] = openalex_api_key
    response = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def get_openalex_articles():
    articles_by_key = {}
    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    select = ",".join([
        "id",
        "doi",
        "title",
        "display_name",
        "publication_date",
        "primary_location",
        "abstract_inverted_index",
    ])

    for query_name, keywords in OPENALEX_QUERIES.items():
        for keyword in keywords:
            params = {
                "search": keyword,
                "filter": f"from_publication_date:{from_date},type:article",
                "per-page": OPENALEX_PER_KEYWORD_LIMIT,
                "sort": "publication_date:desc",
                "select": select,
            }

            try:
                results = openalex_request(params).get("results", [])
            except requests.RequestException as exc:
                print(f"OpenAlex request failed for {query_name}/{keyword}: {exc}")
                continue

            for work in results:
                openalex_id = work.get("id") or ""
                doi = work.get("doi") or ""
                dedupe_key = (doi or openalex_id).lower()
                if not dedupe_key:
                    continue

                title = work.get("title") or work.get("display_name") or "N/A"
                source = ((work.get("primary_location") or {}).get("source") or {})
                journal = source.get("display_name") or "N/A"

                article = articles_by_key.setdefault(dedupe_key, {
                    "title": title,
                    "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                    "doi": doi or "N/A",
                    "journal": journal,
                    "publication_date": work.get("publication_date") or "N/A",
                    "openalex_id": openalex_id,
                    "source_queries": [],
                })
                source_label = f"{query_name}: {keyword}"
                if source_label not in article["source_queries"]:
                    article["source_queries"].append(source_label)

    articles = list(articles_by_key.values())
    articles.sort(key=lambda x: x.get("publication_date") or "", reverse=True)
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
        "topic_tags": topic_tags,
        "method_tags": method_tags,
        "research_score": research_score,
        "reasoning_research": reasoning_research,
        "impact_score": impact_score,
        "reasoning_impact": reasoning_impact,
        "doi": doi,
        "journal": journal,
        "publication_date": abstract_data.get("publication_date", "N/A"),
        "openalex_id": abstract_data.get("openalex_id", "N/A"),
        "source_queries": abstract_data.get("source_queries", []),
    })

issue_title = f"Weekly OpenAlex Literature Report - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the OpenAlex article scores and reasoning from the past week:\n\n"

for article_data in scored_articles:
    title = article_data["title"].strip()
    research_score = article_data["research_score"]
    reasoning_research = article_data["reasoning_research"]
    impact_score = article_data["impact_score"]
    reasoning_impact = article_data["reasoning_impact"]
    journal = article_data["journal"].strip()
    publication_date = article_data.get("publication_date", "N/A")
    openalex_id = article_data.get("openalex_id", "N/A")
    source_queries = article_data.get("source_queries", [])
    doi = (article_data["doi"] or "N/A").strip()
    doi_clean = doi.replace("doi:", "").replace("https://doi.org/", "").strip()
    doi_link = f"https://doi.org/{doi_clean}" if doi_clean != "N/A" and "/" in doi_clean else doi
    topic_tags = article_data.get("topic_tags", [])
    method_tags = article_data.get("method_tags", [])

    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Journal**: {journal}\n"
    issue_body += f"  **Publication date**: {publication_date}\n"
    issue_body += f"  **Matched queries**: {', '.join(source_queries) if source_queries else 'N/A'}\n"
    issue_body += f"  **Topic tags**: {', '.join(topic_tags) if topic_tags else 'N/A'}\n"
    issue_body += f"  **Method tags**: {', '.join(method_tags) if method_tags else 'N/A'}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Reasoning (Research)**: {reasoning_research}\n"
    issue_body += f"  **Impact Score**: {impact_score}\n"
    issue_body += f"  **Reasoning (Impact)**: {reasoning_impact}\n"
    issue_body += f"  **DOI**: {doi_link}\n"
    issue_body += f"  **OpenAlex**: {openalex_id}\n\n"

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
