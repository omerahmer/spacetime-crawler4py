import json
from collections import Counter
from pathlib import Path


STATS_FILE = Path("crawler_stats.json")
OUTPUT_FILE = Path("report.txt")


def generate_report():
    if not STATS_FILE.exists():
        raise FileNotFoundError(
            "crawler_stats.json not found. Run the crawler first."
        )

    with STATS_FILE.open("r", encoding="utf-8") as f:
        stats = json.load(f)

    unique_pages = stats.get("unique_pages", [])
    longest_page = stats.get("longest_page", {"url": "", "word_count": 0})
    word_freq = Counter(stats.get("word_freq", {}))
    subdomains = stats.get("subdomains", {})

    top_50 = word_freq.most_common(50)
    sorted_subdomains = sorted(subdomains.items(), key=lambda item: item[0])

    lines = []
    lines.append(f"1) Unique pages found: {len(unique_pages)}")
    lines.append("")
    lines.append(
        "2) Longest page by words: "
        f"{longest_page.get('url', '')} "
        f"({longest_page.get('word_count', 0)} words)"
    )
    lines.append("")
    lines.append("3) 50 most common words (non-stopwords):")
    for word, count in top_50:
        lines.append(f"{word}, {count}")

    lines.append("")
    lines.append("4) Subdomains discovered and unique page counts:")
    for subdomain, count in sorted_subdomains:
        lines.append(f"{subdomain}, {count}")

    content = "\n".join(lines)
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_report()
