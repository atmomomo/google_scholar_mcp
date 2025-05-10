from typing import Any
import json
import scholarly
from scholarly import scholarly
import textwrap
import time
import requests
from bs4 import BeautifulSoup
import random
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from googletrans import Translator

# 初始化MCP服务器
mcp = FastMCP("scholar-search", log_level="ERROR")


def get_paper_abstract(paper_url):
    """尝试从论文页面获取摘要"""
    try:
        headers_candidate = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]
        headers = {
            'User-Agent': random.choice(headers_candidate),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            # 'Connection': 'keep-alive',
        }
        response = requests.get(paper_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 定义匹配规则列表
            abstract_rules = [
                ('meta', {'property': 'og:description'}, 'content'),
                ('meta', {'name': 'citation_abstract'}, 'content'),
                ('div', {'class': 'abstract'}, None),
                ('div', {'class': 'abstract-text'}, None),
                ('section', {'id': 'abstract'}, None),
                ('section', {'class': 'article-information abstract'}, None),
                ('p', {'class': 'abstract-text'}, None)
            ]

            abstract_candidates = []

            # 遍历规则提取摘要
            for tag, attrs, content_attr in abstract_rules:
                try:
                    element = soup.find(tag, attrs)
                    if element:
                        # 如果有 content_attr，则从属性中提取
                        if content_attr:
                            abstract_candidates.append(element.attrs.get(content_attr, '').strip())
                        # 如果没有 content_attr，则直接获取文本
                        else:
                            abstract_candidates.append(element.get_text().strip())
                except:
                    continue  # 如果某个规则出错，则跳过

            # 选出长度最大且不为空的摘要
            if abstract_candidates:
                max_abstract = max(abstract_candidates, key=len)
                if len(max_abstract) > 0:
                    return max_abstract

        return "无法获取摘要"
    except Exception as e:
        return f"获取摘要时出错: {str(e)}"


@mcp.tool(name="谷歌学术搜索(B站:Byron的算法分享)",
          description="搜索谷歌学术并返回相关论文信息，包括标题、作者、期刊、年份和摘要")
async def search_google_scholar(query: str = Field(description="搜索关键词"),
                                num_results: int = Field(default=5, description="返回的结果数量，默认为5")) -> str:
    """从Google Scholar搜索并返回指定数量的论文信息"""
    print(f"\n正在搜索 '{query}'...")

    translator = Translator()

    # 如果查询是中文，则进行翻译
    if any('\u4e00' <= char <= '\u9fff' for char in query):  # 判断是否包含中文
        translated = await translator.translate(query, src='zh-cn', dest='en')  # 从中文翻译成英文
        query = translated.text  # 使用翻译后的英文

    print(f"\n正在搜索 '{query}'...")

    # 搜索论文
    search_query = scholarly.search_pubs(query)

    results = []
    count = 0

    for i in range(num_results * 2):  # 多取一些，以应对可能的失败情况
        try:
            paper = next(search_query)

            # 基本信息
            paper_info = {
                'title': paper.get('bib', {}).get('title', '无题目'),
                'authors': paper.get('bib', {}).get('author', '无作者信息'),
                'journal': paper.get('bib', {}).get('venue', '无期刊信息'),
                'year': paper.get('bib', {}).get('pub_year', '无发表年份'),
                'url': paper.get('pub_url', '无URL'),
                'num_citations': paper.get('num_citations', '无引用'),
            }

            # 尝试获取摘要
            tmp_flag = 1
            if 'pub_url' in paper and paper['pub_url']:
                paper_info['abstract'] = get_paper_abstract(paper['pub_url'])
                if paper_info['abstract'] == '无法获取摘要':
                    tmp_flag = 0
            else:
                paper_info['abstract'] = '无法获取摘要'
                tmp_flag = 0

            if tmp_flag:
                results.append(paper_info)
                count += 1

            if count >= num_results:
                break

            # 添加延迟以避免被封，并添加正态扰动
            time.sleep(2 + random.gauss(0, 0.5))

        except StopIteration:
            break
        except Exception as e:
            print(f"处理论文时出错: {str(e)}")
            continue

    # 格式化输出结果
    if not results:
        return "未找到相关论文"

    formatted_results = []
    for i, paper in enumerate(results, 1):
        paper_text = f"=== 论文 {i} ===\n"
        paper_text += f"标题: {paper['title']}\n"
        paper_text += f"作者: {', '.join(paper['authors']) if isinstance(paper['authors'], list) else paper['authors']}\n"
        paper_text += f"期刊: {paper['journal']}\n"
        paper_text += f"发表年份: {paper['year']}\n"
        paper_text += f"URL: {paper['url']}\n"
        paper_text += f"引用次数: {paper['num_citations']}\n"
        paper_text += "摘要:\n"

        # 格式化打印摘要，使其更易读
        if paper['abstract'] and paper['abstract'] != "无摘要信息" and paper['abstract'] != "无法获取摘要":
            abstract_lines = textwrap.wrap(paper['abstract'], width=80)
            for line in abstract_lines:
                paper_text += f"  {line}\n"
        else:
            paper_text += f"  {paper['abstract']}\n"

        formatted_results.append(paper_text)

    return "\n\n".join(formatted_results)


if __name__ == "__main__":
    # 启动MCP服务器
    # 可以选择stdio或sse模式
    # 对于本地使用，推荐stdio模式
    mcp.run(transport="stdio")
    # 对于远程部署，可以使用sse模式
    # mcp.run(transport="sse")
