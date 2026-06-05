import re
from dataclasses import dataclass

from app.schemas.parsed import ContactInfo

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
LINKEDIN_URL_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/in/[\w-]+", re.I)
GITHUB_URL_RE = re.compile(r"(https?://)?(www\.)?github\.com/[\w-]+", re.I)
PORTFOLIO_URL_RE = re.compile(r"https?://[\w\-.]+(?:/[\w\-.~/?%&+=]*)?", re.I)

SPANISH_PHONE_RE = re.compile(
    r"(?:"
    r"(?:\+|00)\s*34[\s().-]*"
    r"|"
    r"\(\s*(?:\+|00)?\s*34\s*\)\s*"
    r")?"
    r"(?:6|7|9)\d{2}[\s().-]*\d{2}[\s().-]*\d{2}[\s().-]*\d{2}"
    r"(?!\d)",
    re.I,
)

INTERNATIONAL_PHONE_RE = re.compile(
    r"(?:\+|00)\s*\d{1,3}[\s().-]*(?:\d[\s().-]*){7,12}\d(?!\d)",
    re.I,
)

LINK_MENTION_RE = {
    "linkedin": re.compile(r"\blinkedin\b", re.I),
    "github": re.compile(r"\bgithub\b", re.I),
    "portfolio": re.compile(r"\bportfolio\b", re.I),
}


@dataclass
class ProfessionalLinksStatus:
    level: str  # ok | mention_only | missing
    urls: dict[str, str | None]
    mentions: list[str]


def _find_phone(text: str) -> str | None:
    for pattern in (SPANISH_PHONE_RE, INTERNATIONAL_PHONE_RE):
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(0).strip())
    return None


def detect_professional_links(text: str) -> ProfessionalLinksStatus:
    urls = {
        "linkedin": None,
        "github": None,
        "portfolio": None,
    }
    linkedin_match = LINKEDIN_URL_RE.search(text)
    github_match = GITHUB_URL_RE.search(text)
    if linkedin_match:
        urls["linkedin"] = linkedin_match.group(0)
    if github_match:
        urls["github"] = github_match.group(0)

    for url in PORTFOLIO_URL_RE.findall(text):
        lower = url.lower()
        if "linkedin" not in lower and "github" not in lower:
            urls["portfolio"] = url
            break

    mentions: list[str] = []
    for name, pattern in LINK_MENTION_RE.items():
        if pattern.search(text) and not urls.get(name):
            mentions.append(name)

    has_urls = any(urls.values())
    if has_urls:
        level = "ok"
    elif mentions:
        level = "mention_only"
    else:
        level = "missing"

    return ProfessionalLinksStatus(level=level, urls=urls, mentions=mentions)


def extract_contact(text: str) -> ContactInfo:
    lines = text.split("\n")[:15]
    header = "\n".join(lines)

    email_match = EMAIL_RE.search(header) or EMAIL_RE.search(text)
    phone = _find_phone(header) or _find_phone(text)
    links = detect_professional_links(text)

    full_name = None
    for line in lines[:3]:
        stripped = line.strip()
        if stripped and not EMAIL_RE.search(stripped) and len(stripped) < 60:
            if "@" not in stripped and "http" not in stripped.lower():
                if not _find_phone(stripped):
                    full_name = stripped
                    break

    location = None
    location_keywords = ["madrid", "barcelona", "españa", "spain", "remote", "remoto"]
    for line in lines[:8]:
        if any(kw in line.lower() for kw in location_keywords):
            location = line.strip()
            break

    return ContactInfo(
        full_name=full_name,
        email=email_match.group(0) if email_match else None,
        phone=phone,
        location=location,
        linkedin=links.urls["linkedin"],
        github=links.urls["github"],
        portfolio=links.urls["portfolio"],
        professional_links_level=links.level,
        professional_link_mentions=links.mentions,
    )
