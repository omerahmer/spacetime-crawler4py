import json
import re
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse


STATS_FILE = Path("crawler_stats.json")
MAX_URL_LENGTH = 250
MAX_PATH_DEPTH = 12
MAX_REPEAT_PATH_SEGMENTS = 3
MAX_QUERY_PARAMS = 6

ALLOWED_DOMAINS = (
    ".ics.uci.edu",
    ".cs.uci.edu",
    ".informatics.uci.edu",
    ".stat.uci.edu",
)

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s",
    "same", "she", "should", "so", "some", "such", "t", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "you", "your",
    "yours", "yourself", "yourselves",
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value.strip())


def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]


def _load_stats():
    if not STATS_FILE.exists():
        return {
            "unique_pages": [],
            "longest_page": {"url": "", "word_count": 0},
            "word_freq": {},
            "subdomains": {},
        }
    try:
        with STATS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("unique_pages", [])
        data.setdefault("longest_page", {"url": "", "word_count": 0})
        data.setdefault("word_freq", {})
        data.setdefault("subdomains", {})
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "unique_pages": [],
            "longest_page": {"url": "", "word_count": 0},
            "word_freq": {},
            "subdomains": {},
        }


def _save_stats(stats):
    with STATS_FILE.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)


def _canon_url(candidate):
    clean_url, _ = urldefrag(candidate)
    parsed = urlparse(clean_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{host}{path}{query}"


def _extract_words(html_content):
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_content)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text).lower()
    words = re.findall(r"[a-z0-9]+", text)
    return [w for w in words if w not in STOP_WORDS]


def _record_page_stats(page_url, html_content):
    stats = _load_stats()
    unique_pages = set(stats["unique_pages"])
    if page_url in unique_pages:
        return

    unique_pages.add(page_url)
    stats["unique_pages"] = sorted(unique_pages)

    words = _extract_words(html_content)
    word_count = len(words)
    if word_count > stats["longest_page"].get("word_count", 0):
        stats["longest_page"] = {"url": page_url, "word_count": word_count}

    freq = Counter(stats.get("word_freq", {}))
    freq.update(words)
    stats["word_freq"] = dict(freq)

    host = urlparse(page_url).netloc.lower()
    subdomains = stats.get("subdomains", {})
    subdomains[host] = subdomains.get(host, 0) + 1
    stats["subdomains"] = subdomains
    _save_stats(stats)


def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    if not resp or resp.status != 200 or not resp.raw_response:
        return []

    content_type = resp.raw_response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type:
        return []

    raw = resp.raw_response.content or b""
    if len(raw) > 10_000_000:
        return []

    html = raw.decode("utf-8", errors="ignore")
    if not html.strip():
        return []

    page_url = _canon_url(resp.raw_response.url or url)
    if page_url and is_valid(page_url):
        _record_page_stats(page_url, html)

    parser = LinkParser()
    try:
        parser.feed(html)
    except Exception:
        return []

    next_links = []
    base = page_url or url
    for href in parser.links:
        absolute = urljoin(base, href)
        clean = _canon_url(absolute)
        if clean:
            next_links.append(clean)
    return next_links


def is_valid(url):
    # Decide whether to crawl this url or not.
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        host = parsed.netloc.lower()
        if not any(host == dom[1:] or host.endswith(dom) for dom in ALLOWED_DOMAINS):
            return False

        if len(url) > MAX_URL_LENGTH:
            return False

        path_segments = [seg for seg in parsed.path.lower().split("/") if seg]
        if len(path_segments) > MAX_PATH_DEPTH:
            return False
        if path_segments:
            counts = Counter(path_segments)
            if counts.most_common(1)[0][1] > MAX_REPEAT_PATH_SEGMENTS:
                return False

        query = parse_qs(parsed.query, keep_blank_values=True)
        if len(query) > MAX_QUERY_PARAMS:
            return False

        trap_tokens = (
            "calendar", "event", "share=", "replytocom=", "sort=", "sessionid=",
            "filter=", "page=", "login", "signup", "wp-content", "wp-json"
        )
        lowered = url.lower()
        if any(token in lowered for token in trap_tokens):
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$",
            parsed.path.lower(),
        )

    except TypeError:
        print("TypeError for ", parsed)
        raise
