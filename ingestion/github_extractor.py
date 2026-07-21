"""
GitHub Extractor — Rate-limit aware, incremental PR extraction.

Problem solved: GitHub's 5,000 req/hr cap meant full-org extractions
crashed mid-run. We solved this with:
  1. Header-driven rate limit tracking (not guessing)
  2. Early-exit pagination: sort updated_at DESC, stop at lookback boundary
  3. Exponential backoff on 5xx errors
"""

import time
import logging
from datetime import datetime, timezone
from typing import Generator, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubExtractor:
    BASE_URL = "https://api.github.com"
    RATE_LIMIT_BUFFER = 100  # stop if remaining calls drop below this

    def __init__(self, token: str, org: str):
        self.org = org
        self.session = self._build_session(token)

    def _build_session(self, token: str) -> requests.Session:
        """Build a session with retry logic and auth headers."""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        # Retry on transient server errors — NOT on 403/429 (handled separately)
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def _get(self, url: str, params: dict = None) -> dict:
        """
        Make a GET request, checking rate limit headers before each call.
        Sleeps proactively if we're close to the limit.
        """
        resp = self.session.get(url, params=params, timeout=30)

        # Check rate limit headers on every response
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 9999))
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))

        if remaining <= self.RATE_LIMIT_BUFFER:
            sleep_seconds = max(0, reset_ts - int(time.time())) + 5
            logger.warning(
                f"Rate limit low ({remaining} remaining). "
                f"Sleeping {sleep_seconds}s until reset."
            )
            time.sleep(sleep_seconds)

        resp.raise_for_status()
        return resp.json(), resp.headers

    def get_repos(self) -> list[dict]:
        """Fetch all repositories for the org (paginated)."""
        repos = []
        page = 1
        while True:
            data, _ = self._get(
                f"{self.BASE_URL}/orgs/{self.org}/repos",
                params={"per_page": 100, "page": page, "type": "all"},
            )
            if not data:
                break
            repos.extend(data)
            logger.info(f"Fetched page {page} of repos ({len(data)} repos)")
            page += 1
        logger.info(f"Total repos found: {len(repos)}")
        return repos

    def extract_pull_requests(
        self,
        repo: str,
        since: Optional[datetime] = None,
    ) -> Generator[dict, None, None]:
        """
        Extract PRs for a single repo with early-exit pagination.

        KEY OPTIMIZATION: GitHub doesn't support filtering PRs by date directly.
        We sort by updated_at DESC and stop pagination as soon as we hit PRs
        older than `since`. This avoids scanning the entire PR history.

        Args:
            repo: Repository name (e.g., "my-service")
            since: Only extract PRs updated after this datetime
        """
        page = 1
        total_yielded = 0
        url = f"{self.BASE_URL}/repos/{self.org}/{repo}/pulls"

        while True:
            data, _ = self._get(url, params={
                "state": "all",          # open + closed + merged
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            })

            if not data:
                logger.info(f"{repo}: exhausted all pages at page {page}")
                break

            for pr in data:
                updated_at = datetime.fromisoformat(
                    pr["updated_at"].replace("Z", "+00:00")
                )

                # EARLY EXIT: once we see PRs older than our lookback, stop
                if since and updated_at < since.replace(tzinfo=timezone.utc):
                    logger.info(
                        f"{repo}: reached lookback boundary at page {page}. "
                        f"Yielded {total_yielded} PRs."
                    )
                    return

                yield {
                    "id": pr["id"],
                    "number": pr["number"],
                    "repo": repo,
                    "org": self.org,
                    "title": pr["title"],
                    "state": pr["state"],
                    "author": pr["user"]["login"] if pr.get("user") else None,
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "merged_at": pr.get("merged_at"),
                    "closed_at": pr.get("closed_at"),
                    "additions": pr.get("additions", 0),
                    "deletions": pr.get("deletions", 0),
                    "changed_files": pr.get("changed_files", 0),
                    "review_comments": pr.get("review_comments", 0),
                    "labels": [lbl["name"] for lbl in pr.get("labels", [])],
                    "base_branch": pr["base"]["ref"] if pr.get("base") else None,
                    "extracted_at": datetime.utcnow().isoformat(),
                }
                total_yielded += 1

            page += 1
            logger.debug(f"{repo}: fetched page {page - 1}, {total_yielded} PRs so far")

    def extract_all_repos(
        self,
        since: Optional[datetime] = None,
    ) -> Generator[dict, None, None]:
        """Extract PRs across all org repos. Used for backfills."""
        repos = self.get_repos()
        for repo_obj in repos:
            repo_name = repo_obj["name"]
            try:
                logger.info(f"Extracting PRs for: {self.org}/{repo_name}")
                yield from self.extract_pull_requests(repo_name, since=since)
            except Exception as e:
                # Don't let one repo failure break the entire org extraction
                logger.error(f"Failed extracting {repo_name}: {e}", exc_info=True)
