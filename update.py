import feedparser
from datetime import datetime, timezone, timedelta
import json
import requests
import os
import re
from openai import OpenAI

# Example PubMed RSS feed URL
rss_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/search/1ZM29-VQ7Y3AIGmXtfwB55QSl-K3N1gWErGoQ5G0krIim7hsty/?limit=100&utm_campaign=pubmed-2&fc=20250411080910'

access_token = os.getenv('GITHUB_TOKEN')
deepseekapikey = os.getenv('DEEPSEEK_API_KEY')

client = OpenAI(
    api_key=deepseekapikey,
    base_url="https://api.deepseek.com/v1"
)

def extract_scores_and_reasons(text):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"You are an psychologist and researcher. You are skilled at selecting interesting/novelty research."},
            {"role": "user", "content": f"Given the text '{text}', evaluate this article with two scores and a brief justification for each score:\n"
                                        f"1. Research Score (0-100): Based on research innovation, methodological rigor, and data reliability.\n"
                                        f"2. Social Impact Score (0-100): Based on public attention, policy relevance, and societal impact.\n"
                                        f"Provide the scores and justifications in the following format, with each on a new line:\n"
                                        f"Research Score: <score>\n"
                                        f"Reasoning (Research): <reasoning>\n"
                                        f"Social Impact Score: <score>\n"
                                        f"Reasoning (Social Impact): <reasoning>\n"},
        ],
        max_tokens=200,
        temperature=0.3
    )

    generated_text = response.choices[0].message.content.strip()

    research_score = "N/A"
    reasoning_research = "N/A"
    social_impact_score = "N/A"
    reasoning_social_impact = "N/A"

    research_match = re.search(r"Research Score:\s*(\d+)", generated_text, re.IGNORECASE)
    if research_match:
        research_score = research_match.group(1)

    reason_research_match = re.search(r"Reasoning \(Research\):\s*(.+)", generated_text, re.IGNORECASE)
    if reason_research_match:
        reasoning_research = reason_research_match.group(1).strip()

    social_match = re.search(r"Social Impact Score:\s*(\d+)", generated_text, re.IGNORECASE)
    if social_match:
        social_impact_score = social_match.group(1)

    reason_social_match = re.search(r"Reasoning \(Social Impact\):\s*(.+)", generated_text, re.IGNORECASE)
    if reason_social_match:
        reasoning_social_impact = reason_social_match.group(1).strip()

    return research_score, reasoning_research, social_impact_score, reasoning_social_impact

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []
    feed = feedparser.parse(rss_url)
    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
        if published_date >= one_week_ago:
            title = entry.title
            abstract = entry.content[0].value
            doi = entry.dc_identifier
            abstracts_with_urls.append({"title": title, "abstract": abstract, "doi": doi})

    return abstracts_with_urls

pubmed_abstracts = get_pubmed_abstracts(rss_url)

scored_articles = []

for abstract_data in pubmed_abstracts:
    title = abstract_data["title"]
    research_score, reasoning_research, social_impact_score, reasoning_social_impact = extract_scores_and_reasons(abstract_data["abstract"])
    doi = abstract_data["doi"]

    scored_articles.append({
        "title": title,
        "research_score": research_score,
        "reasoning_research": reasoning_research,
        "social_impact_score": social_impact_score,
        "reasoning_social_impact": reasoning_social_impact,
        "doi": doi
    })

issue_title = f"Weekly Article Scores and Reasoning - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the article scores and reasoning from the past week:\n\n"

for article_data in scored_articles:
    title = article_data["title"].strip()
    research_score = article_data["research_score"]
    reasoning_research = article_data["reasoning_research"]
    social_impact_score = article_data["social_impact_score"]
    reasoning_social_impact = article_data["reasoning_social_impact"]
    doi = article_data["doi"].strip()

    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Reasoning (Research)**: {reasoning_research}\n"
    issue_body += f"  **Social Impact Score**: {social_impact_score}\n"
    issue_body += f"  **Reasoning (Social Impact)**: {reasoning_social_impact}\n"
    issue_body += f"  **DOI**: https://doi.org/{doi}\n\n"

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
