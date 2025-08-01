# Credit: B站:Byron的算法分享

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

# Initialize the MCP server
mcp = FastMCP("scholar-search", log_level="ERROR")


def get_paper_abstract(paper_url):
    """Try to get the abstract from the paper page"""
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

            # Define a list of matching rules
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

            # Traverse the rules to extract the abstract
            for tag, attrs, content_attr in abstract_rules:
                try:
                    element = soup.find(tag, attrs)
                    if element:
                        # If there is a content_attr, extract it from the attribute
                        if content_attr:
                            abstract_candidates.append(element.attrs.get(content_attr, '').strip())
                        # If there is no content_attr, get the text directly
                        else:
                            abstract_candidates.append(element.get_text().strip())
                except:
                    continue  # If a rule goes wrong, skip it

            # Select the longest non-empty abstract
            if abstract_candidates:
                max_abstract = max(abstract_candidates, key=len)
                if len(max_abstract) > 0:
                    return max_abstract

        return "Could not retrieve abstract"
    except Exception as e:
        return f"Error getting abstract: {str(e)}"


@mcp.tool(name="Google Scholar Search",
          description="Search Google Scholar and return relevant paper information, including title, authors, journal, year, and abstract")
async def search_google_scholar(query: str = Field(description="Search keywords"),
                                num_results: int = Field(default=10, description="Number of results to return, default is 5")) -> str:
    """Search and return the specified number of papers from Google Scholar"""
    print(f"\nSearching for '{query}'...")

    translator = Translator()

    # If the query is in Chinese, translate it
    if any('\u4e00' <= char <= '\u9fff' for char in query):  # Check if it contains Chinese
        translated = await translator.translate(query, src='zh-cn', dest='en')  # Translate from Chinese to English
        query = translated.text  # Use the translated English

    print(f"\nSearching for '{query}'...")

    # Search for papers
    search_query = scholarly.search_pubs(query)

    results = []
    count = 0

    for i in range(num_results * 2):  # Take a few more to deal with possible failures
        try:
            paper = next(search_query)

            # Basic information
            paper_info = {
                'title': paper.get('bib', {}).get('title', 'No title'),
                'authors': paper.get('bib', {}).get('author', 'No author information'),
                'journal': paper.get('bib', {}).get('venue', 'No journal information'),
                'year': paper.get('bib', {}).get('pub_year', 'No publication year'),
                'url': paper.get('pub_url', 'No URL'),
                'num_citations': paper.get('num_citations', 'No citation'),
            }

            # Try to get the abstract
            tmp_flag = 1
            if 'pub_url' in paper and paper['pub_url']:
                paper_info['abstract'] = get_paper_abstract(paper['pub_url'])
                if paper_info['abstract'] == 'Could not retrieve abstract':
                    tmp_flag = 0
            else:
                paper_info['abstract'] = 'Could not retrieve abstract'
                tmp_flag = 0

            if tmp_flag:
                results.append(paper_info)
                count += 1

            if count >= num_results:
                break

            # Add a delay to avoid being blocked, and add a normal disturbance
            time.sleep(2 + random.gauss(0, 0.5))

        except StopIteration:
            break
        except Exception as e:
            print(f"Error processing paper: {str(e)}")
            continue

    # Format the output results
    if not results:
        return "No relevant papers found"

    formatted_results = []
    for i, paper in enumerate(results, 1):
        paper_text = f"=== Paper {i} ===\n"
        paper_text += f"Title: {paper['title']}\n"
        paper_text += f"Authors: {', '.join(paper['authors']) if isinstance(paper['authors'], list) else paper['authors']}\n"
        paper_text += f"Journal: {paper['journal']}\n"
        paper_text += f"Publication Year: {paper['year']}\n"
        paper_text += f"URL: {paper['url']}\n"
        paper_text += f"Number of citations: {paper['num_citations']}\n"
        paper_text += "Abstract:\n"

        # Format the abstract to make it more readable
        if paper['abstract'] and paper['abstract'] != "No abstract information" and paper['abstract'] != "Could not retrieve abstract":
            abstract_lines = textwrap.wrap(paper['abstract'], width=80)
            for line in abstract_lines:
                paper_text += f"  {line}\n"
        else:
            paper_text += f"  {paper['abstract']}\n"

        formatted_results.append(paper_text)

    return "\n\n".join(formatted_results)


if __name__ == "__main__":
    # Start the MCP server
    # You can choose stdio or sse mode
    # For local use, stdio mode is recommended
    mcp.run(transport="stdio")
    # For remote deployment, you can use sse mode
    # mcp.run(transport="sse")
