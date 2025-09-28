import requests
import logging
from typing import Dict, Any


class GitHubHandler:
    """Handler for GitHub repository metadata fetching."""
    
    def __init__(self):
        self.session = requests.Session()
        # Set user agent for GitHub API
        self.session.headers.update({
            'User-Agent': 'ACME-CLI/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def fetch_meta(self, url: str) -> Dict[str, Any]:
        """Fetch repository metadata from GitHub API."""
        try:
            # Parse GitHub URL: https://github.com/owner/repo
            parts = url.rstrip('/').split('/')
            if len(parts) < 5 or 'github.com' not in parts[2]:
                logging.error(f"Invalid GitHub URL format: {url}")
                return {}
            
            owner, repo = parts[3], parts[4]
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            
            response = self.session.get(api_url)
            response.raise_for_status()
            
            repo_data = response.json()
            
            # Fetch additional metadata
            meta = {
                'name': repo_data.get('name', ''),
                'full_name': repo_data.get('full_name', ''),
                'description': repo_data.get('description', ''),
                'stars': repo_data.get('stargazers_count', 0),
                'forks': repo_data.get('forks_count', 0),
                'watchers': repo_data.get('watchers_count', 0),
                'size': repo_data.get('size', 0),  # in KB
                'language': repo_data.get('language', ''),
                'topics': repo_data.get('topics', []),
                'license': repo_data.get('license', {}).get('spdx_id', '') if repo_data.get('license') else '',
                'created_at': repo_data.get('created_at', ''),
                'updated_at': repo_data.get('updated_at', ''),
                'pushed_at': repo_data.get('pushed_at', ''),
                'default_branch': repo_data.get('default_branch', 'main'),
                'open_issues_count': repo_data.get('open_issues_count', 0),
                'has_wiki': repo_data.get('has_wiki', False),
                'has_pages': repo_data.get('has_pages', False),
                'archived': repo_data.get('archived', False),
                'disabled': repo_data.get('disabled', False),
            }
            
            # Try to fetch contributors data
            try:
                contributors_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
                contrib_response = self.session.get(contributors_url)
                if contrib_response.status_code == 200:
                    contributors = contrib_response.json()
                    meta['contributors'] = {
                        contrib.get('login', 'unknown'): contrib.get('contributions', 0)
                        for contrib in contributors[:10]  # Limit to top 10
                    }
                else:
                    meta['contributors'] = {}
            except Exception as e:
                logging.warning(f"Failed to fetch contributors for {url}: {e}")
                meta['contributors'] = {}
            
            # Try to fetch README
            try:
                readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
                readme_response = self.session.get(readme_url)
                if readme_response.status_code == 200:
                    readme_data = readme_response.json()
                    import base64
                    readme_content = base64.b64decode(readme_data.get('content', '')).decode('utf-8')
                    meta['readme_text'] = readme_content
                else:
                    meta['readme_text'] = ''
            except Exception as e:
                logging.warning(f"Failed to fetch README for {url}: {e}")
                meta['readme_text'] = ''
            
            return meta
            
        except requests.RequestException as e:
            logging.error(f"HTTP error fetching metadata for {url}: {e}")
            return {}
        except Exception as e:
            logging.error(f"Failed to fetch metadata for {url}: {e}")
            return {}


def fetch_github_metadata(url: str) -> Dict[str, Any]:
    """Module-level function to fetch GitHub metadata."""
    handler = GitHubHandler()
    return handler.fetch_meta(url)