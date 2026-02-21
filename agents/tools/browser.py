"""
Browser Tool for CoderAgent.
Uses DuckDuckGo HTML for search and Playwright for page reading.
"""
import sys
import time
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class BrowserTool:
    def __init__(self):
        self.headless = True
        self.browser = None
        self.context = None
        self.playwright = None

    def start_browser(self):
        """Starts the playwright browser instance."""
        if not self.browser:
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=self.headless)
                self.context = self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            except Exception as e:
                print(f"⚠️ [BrowserTool] Failed to start Playwright: {e}")
                self.browser = None

    def close(self):
        """Closes the browser."""
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def search_documentation(self, query: str) -> List[Dict[str, str]]:
        """
        Searches using DuckDuckGo HTML version.
        Returns a list of {title, url, snippet}.
        """
        results = []
        try:
            print(f"🔍 [BrowserTool] Searching for: {query}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query}

            response = requests.post(url, data=data, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"⚠️ [BrowserTool] Search failed: Status {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # DuckDuckGo HTML structure
            for result in soup.find_all('div', class_='result'):
                title_tag = result.find('a', class_='result__a')
                snippet_tag = result.find('a', class_='result__snippet')

                if title_tag and snippet_tag:
                    title = title_tag.get_text(strip=True)
                    link = title_tag['href']
                    snippet = snippet_tag.get_text(strip=True)

                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet
                    })

                    if len(results) >= 5:
                        break

        except Exception as e:
            print(f"⚠️ [BrowserTool] Search failed: {e}")
            return []

        return results

    def read_url(self, url: str) -> str:
        """
        Visits a URL and extracts the main text content using Playwright.
        """
        self.start_browser()
        if not self.browser:
            return "Error: Browser not available."

        page = None
        try:
            page = self.context.new_page()
            print(f"🌐 [BrowserTool] Visiting: {url}")
            page.goto(url, timeout=30000)

            # Wait for content to load
            try:
                page.wait_for_load_state('networkidle', timeout=5000)
            except:
                pass

            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
                script.decompose()

            text = soup.get_text(separator='\n')

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text[:15000] # Return first 15k chars

        except Exception as e:
            return f"Error reading URL '{url}': {e}"
        finally:
            if page:
                page.close()

if __name__ == "__main__":
    # Test
    browser = BrowserTool()
    print("Searching for 'python synapse engine'...")
    results = browser.search_documentation("python synapse engine")
    print(f"Found {len(results)} results.")

    if results:
        first_url = results[0]['url']
        print(f"Reading first result: {first_url}")
        content = browser.read_url(first_url)
        print(f"Content length: {len(content)}")
        print(f"Preview:\n{content[:500]}")

    browser.close()
