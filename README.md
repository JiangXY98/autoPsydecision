# Autoaiscore
This is a repo template to generate score for PubMed RSS update based on research abstract. You could custom this repo by changing the propmt and RSS links.

已实现功能：

- ✅ 自动、可复现的文献扫描 + 结构化判断记录
- ✅ 每周判断 → 持久化数据
- ✅ 每月对“自己判断系统”的审计
- ✅ 可回放的科研判断轨迹

# Usage

- Fork and clone this repo to your own account or click `use this template - Create a new Repository`
- Set up AI API: Add your API token as `OPENAI_API_KEY` in your repo's Settings - Security - Actions - Repository secrets.
- Fill RSS: Change Line 9 of `update.py` to your own rss.
- Change prompt
- Change issue repo: Fill your GitHub user name.
- Trigger the first update

Click your repo's Actions, select Weekly Article, and click run workflow in the right panel.

Thank to [yufree.cn](https://yufree.cn)
