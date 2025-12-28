import feedparser
from datetime import datetime, timezone, timedelta
import json
import requests
import os
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

=== Output Format (STRICT JSON ONLY) ===

Return a valid JSON object only (no extra text):

{
  "research_quality_score": <integer 0-100>,
  "research_reasoning": "<2–3 concise sentences>",
  "potential_impact_score": <integer 0-100>,
  "impact_reasoning": "<2–3 concise sentences>"
}
"""

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
        max_tokens=300,
        temperature=0.2,
    )

    generated = response.choices[0].message.content.strip()

    # Defaults (robust fallback)
    research_score = "N/A"
    reasoning_research = "N/A"
    impact_score = "N/A"
    reasoning_impact = "N/A"

    try:
        obj = json.loads(generated)
        research_score = int(obj.get("research_quality_score"))
        reasoning_research = str(obj.get("research_reasoning", "")).strip() or "N/A"
        impact_score = int(obj.get("potential_impact_score"))
        reasoning_impact = str(obj.get("impact_reasoning", "")).strip() or "N/A"
    except Exception:
        # Keep N/A; optionally log generated for debugging
        pass

    return research_score, reasoning_research, impact_score, reasoning_impact

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []
    feed = feedparser.parse(rss_url)
    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
        if published_date >= one_week_ago:
            title = entry.title
            abstract = entry.content[0].value
            doi = entry.get("dc_identifier", "N/A")
            journal = entry.get('dc_source', 'N/A')
            abstracts_with_urls.append({"title": title, "abstract": abstract, "doi": doi, "journal": journal})

    return abstracts_with_urls

pubmed_abstracts = get_pubmed_abstracts(rss_url)

scored_articles = []

for abstract_data in pubmed_abstracts:
    title = abstract_data["title"]
    research_score, reasoning_research, impact_score, reasoning_impact = extract_scores_and_reasons(abstract_data["title"],abstract_data["abstract"])
    doi = abstract_data["doi"]
    journal = abstract_data["journal"]

    scored_articles.append({
        "title": title,
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
    doi = article_data["doi"].strip()
    journal = article_data["journal"].strip()

    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Journal**: {journal}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Reasoning (Research)**: {reasoning_research}\n"
    issue_body += f"  **Impact Score**: {impact_score}\n"
    issue_body += f"  **Reasoning Impact**: {reasoning_impact}\n"
    issue_body += f"  **DOI**: https://doi.org/{doi}\n\n"

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
