import feedparser
from datetime import datetime, timezone, timedelta
import json
import requests
import os
from openai import OpenAI

# Example PubMed RSS feed URL
rss_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/search/1ZM29-VQ7Y3AIGmXtfwB55QSl-K3N1gWErGoQ5G0krIim7hsty/?limit=100&utm_campaign=pubmed-2&fc=20250411080910'

access_token = os.getenv('GITHUB_TOKEN')
deepseekapikey = os.getenv('DEEPSEEK_API_KEY')

client = OpenAI(
    api_key=deepseekapikey,
    base_url="https://api.deepseek.com/v1"
)

def extract_scores(text):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"You are an decision psychologist, neural expert and researcher. You are skilled at selecting interesting/novelty research."},
            {"role": "user", "content": f"Given the text '{text}', evaluate this article with two scores:\n"
                                      "1. Research Score (0-100): Based on research innovation, methodological rigor, and data reliability.\n"
                                      "2. Social Impact Score (0-100): Based on public attention, policy relevance, and societal impact.\n"
                                      "Provide the scores in the following format:\n"
                                      "Research Score: <score>\n"
                                      "Social Impact Score: <score>"},
        ],
        max_tokens=100,
        temperature=0.5
    )

    generated_text = response.choices[0].message.content.strip()

    research_score_start = generated_text.find("Research Score:")
    research_score = generated_text[research_score_start + len("Research Score:"):].split("\n")[0].strip()

    social_impact_score_start = generated_text.find("Social Impact Score:")
    social_impact_score = generated_text[social_impact_score_start + len("Social Impact Score:"):].strip()

    return research_score, social_impact_score

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []
    feed = feedparser.parse(rss_url)

    for entry in feed.entries:
        title = entry.title
        abstract = entry.content[0].value
        doi = entry.dc_identifier
        abstracts_with_urls.append({"title": title, "abstract": abstract, "doi": doi})

    return abstracts_with_urls

pubmed_abstracts = get_pubmed_abstracts(rss_url)

scored_articles = []

for abstract_data in pubmed_abstracts:
    title = abstract_data["title"]
    research_score, social_impact_score = extract_scores(abstract_data["abstract"])
    doi = abstract_data["doi"]

    try:
        research_score = int(research_score)
        social_impact_score = int(social_impact_score)
        total_score = research_score + social_impact_score
    except ValueError:
        total_score = 0  # 如果评分无法转换为整数，则综合分数为0

    scored_articles.append({
        "title": title,
        "research_score": research_score,
        "social_impact_score": social_impact_score,
        "doi": doi,
        "total_score": total_score
    })

sorted_articles = sorted(scored_articles, key=lambda x: x["total_score"], reverse=True)[:20]

issue_title = f"Top 20 Article Scores - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the top 20 article scores:\n\n"

for article_data in sorted_articles:
    issue_body += f"- **Title**: {article_data['title']}\n"
    issue_body += f"  **Research Score**: {article_data['research_score']}\n"
    issue_body += f"  **Social Impact Score**: {article_data['social_impact_score']}\n"
    issue_body += f"  **Total Score**: {article_data['total_score']}\n"
    issue_body += f"  **DOI**: https://doi.org/{article_data['doi']}\n\n"

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
