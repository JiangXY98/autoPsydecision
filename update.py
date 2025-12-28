import feedparser
from datetime import datetime, timezone, timedelta
import json
import requests
import os
import re
from openai import OpenAI

# Example PubMed RSS feed URL
rss_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/search/1bYz7DSbRS5nPC1Sop1SziAxQ38TJj7lsnpC-_682rLIkEkg-h/?limit=100&utm_campaign=pubmed-2&fc=20251227231501'

access_token = os.getenv('GITHUB_TOKEN')
deepseekapikey = os.getenv('DEEPSEEK_API_KEY')

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
        model="deepseek-chat",
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

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []
    feed = feedparser.parse(rss_url)
    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    for entry in feed.entries:
        published_raw = entry.get("published")
        if not published_raw:
            continue

        try:
            published_date = datetime.strptime(
                published_raw, '%a, %d %b %Y %H:%M:%S %z'
            )
        except ValueError:
            continue

        if published_date >= one_week_ago:
            title = entry.get("title", "N/A")

            if getattr(entry, "content", None) and len(entry.content) > 0:
                abstract = entry.content[0].value
            else:
                abstract = entry.get("summary", "")

            doi = entry.get("dc_identifier", "N/A")
            journal = entry.get("dc_source", "N/A")

            abstracts_with_urls.append({
                "title": title,
                "abstract": abstract,
                "doi": doi,
                "journal": journal
            })

    return abstracts_with_urls

pubmed_abstracts = get_pubmed_abstracts(rss_url)

scored_articles = []

for abstract_data in pubmed_abstracts:
    title = abstract_data["title"]
    abstract_clean = strip_html(abstract_data["abstract"])
    
    research_score, reasoning_research, impact_score, reasoning_impact = extract_scores_and_reasons(
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
        "journal": journal
    })

issue_title = f"Weekly Article Scores and Reasoning - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the article scores and reasoning from the past week:\n\n"

for article_data in scored_articles:
    title = article_data["title"].strip()
    research_score = article_data["research_score"]
    reasoning_research = article_data["reasoning_research"]
    impact_score = article_data["impact_score"]
    reasoning_impact = article_data["reasoning_impact"]
    journal = article_data["journal"].strip()
    doi = (article_data["doi"] or "N/A").strip()
    doi_clean = doi.replace("doi:", "").strip()
    doi_link = f"https://doi.org/{doi_clean}" if doi_clean != "N/A" and "/" in doi_clean else doi
    topic_tags = article_data.get("topic_tags", [])
    method_tags = article_data.get("method_tags", [])

    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Journal**: {journal}\n"
    issue_body += f"  **Topic tags**: {', '.join(topic_tags) if topic_tags else 'N/A'}\n"
    issue_body += f"  **Method tags**: {', '.join(method_tags) if method_tags else 'N/A'}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Reasoning (Research)**: {reasoning_research}\n"
    issue_body += f"  **Impact Score**: {impact_score}\n"
    issue_body += f"  **Reasoning (Impact)**: {reasoning_impact}\n"
    issue_body += f"  **DOI**: {doi_link}\n\n"

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

import pathlib

run_date = datetime.now().strftime("%Y-%m-%d")
out_dir = pathlib.Path("data/weekly")
out_dir.mkdir(parents=True, exist_ok=True)

out_path = out_dir / f"{run_date}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(scored_articles, f, ensure_ascii=False, indent=2)
