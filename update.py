import feedparser
from datetime import datetime, timedelta, timezone
import json
import requests
import os
from openai import OpenAI  # 修正导入语法

# PubMed RSS feed URL
rss_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/search/1jeAVjyuKpXgEVWo0CwWvCsGuJkv73KyXjHBP9vV1tH6idhEe7/?limit=100&utm_campaign=pubmed-2&fc=20250406034018'

# 从环境变量加载密钥
access_token = os.getenv('GITHUB_TOKEN')
deepseekapikey = os.getenv('DEEPSEEK_API_KEY')

# 初始化 DeepSeek API 客户端
client = OpenAI(
    api_key=deepseekapikey,  # 直接使用变量，而非字符串
    base_url="https://api.deepseek.ai/v1",  # 修正 API 地址
)

def extract_scores(text):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a decision psychologist and researcher. Evaluate the text."},
                {"role": "user", "content": f"Given the text '{text}', provide:\n"
                                          "1. Research Score (0-100): For innovation and rigor.\n"
                                          "2. Social Impact Score (0-100): For societal relevance.\n"
                                          "Format:\n"
                                          "Research Score: <score>\n"
                                          "Social Impact Score: <score>"}
            ],
            max_tokens=100,
            temperature=0.5
        )
        generated_text = response.choices[0].message.content.strip()

        # 更健壮的分数提取逻辑
        research_score = "N/A"
        social_impact_score = "N/A"

        if "Research Score:" in generated_text:
            research_score = generated_text.split("Research Score:")[1].split("\n")[0].strip()
        if "Social Impact Score:" in generated_text:
            social_impact_score = generated_text.split("Social Impact Score:")[1].split("\n")[0].strip()

        return research_score, social_impact_score
    except Exception as e:
        print(f"Error extracting scores: {e}")
        return "N/A", "N/A"

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []
    feed = feedparser.parse(rss_url)
    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
        if published_date >= one_week_ago:
            abstracts_with_urls.append({
                "title": entry.title,
                "abstract": entry.content[0].value,
                "doi": entry.dc_identifier
            })
    return abstracts_with_urls

# 主流程
if __name__ == "__main__":
    pubmed_abstracts = get_pubmed_abstracts(rss_url)
    new_articles_data = []

    for abstract_data in pubmed_abstracts:
        research_score, social_impact_score = extract_scores(abstract_data["abstract"])
        new_articles_data.append({
            "title": abstract_data["title"],
            "research_score": research_score,
            "social_impact_score": social_impact_score,
            "doi": abstract_data["doi"]
        })

    # 生成 GitHub Issue
    issue_title = f"Weekly Article Score - {datetime.now().strftime('%Y-%m-%d')}"
    issue_body = "## Weekly Research Evaluation\n\n"
    
    for article in new_articles_data:
        issue_body += (
            f"- **Title**: {article['title']}\n"
            f"  - **Research Score**: {article['research_score']}\n"
            f"  - **Social Impact Score**: {article['social_impact_score']}\n"
            f"  - **DOI**: {article.get('doi', 'N/A')}\n\n"
        )

    # 创建 Issue
    if access_token:
        create_github_issue(issue_title, issue_body, access_token)
    else:
        print("GitHub token not found. Issue content:\n", issue_body)
