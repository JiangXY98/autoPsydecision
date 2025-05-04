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

def extract_scores(text):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"You are an psychologist and researcher. You are skilled at selecting interesting/novelty research."},
            {"role": "user", "content": f"Given the text '{text}', evaluate this article with two scores:\n"
                                      "1. Research Score (0-100): Based on research innovation, methodological rigor, and data reliability.\n"
                                      "2. Social Impact Score (0-100): Based on public attention, policy relevance, and societal impact.\n"
                                      "Provide ONLY the scores in the following format, with each score on a new line and nothing else:\n"
                                      "Research Score: <score>\n"
                                      "Social Impact Score: <score>\n"},
        ],
        max_tokens=60,
        temperature=0.2
    )

    generated_text = response.choices[0].message.content.strip()

    # 使用正则表达式提取分数
    research_score = "N/A" # 默认值
    social_impact_score = "N/A" # 默认值

    # 查找 "Research Score: <数字>"
    research_match = re.search(r"Research Score:\s*(\d+)", generated_text, re.IGNORECASE)
    if research_match:
        research_score = research_match.group(1) # 提取括号匹配的数字部分

    # 查找 "Social Impact Score: <数字>"
    social_match = re.search(r"Social Impact Score:\s*(\d+)", generated_text, re.IGNORECASE)
    if social_match:
        social_impact_score = social_match.group(1) # 提取括号匹配的数字部分

    # 打印提取结果用于调试 (可选)
    # print(f"Generated Text:\n{generated_text}")
    # print(f"Extracted Research Score: {research_score}")
    # print(f"Extracted Social Impact Score: {social_impact_score}")

    return research_score, social_impact_score
    
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
    research_score, social_impact_score = extract_scores(abstract_data["abstract"])
    doi = abstract_data["doi"]

    scored_articles.append({
        "title": title,
        "research_score": research_score,
        "social_impact_score": social_impact_score,
        "doi": doi
    })

issue_title = f"Weekly Article Scores - {datetime.now().strftime('%Y-%m-%d')}"
issue_body = "Below are the article scores from the past week:\n\n"

for abstract_data in pubmed_abstracts:
    title = abstract_data["title"].strip()
    doi = abstract_data["doi"].strip()
    # 调用更新后的函数提取分数
    research_score, social_impact_score = extract_scores(abstract_data["abstract"])

    # 格式化输出 - 保持之前的格式或者使用块引用格式
    issue_body += f"- **Title**: {title}\n"
    issue_body += f"  **Research Score**: {research_score}\n"
    issue_body += f"  **Social Impact Score**: {social_impact_score}\n"
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
