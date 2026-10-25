from __future__ import annotations

import re

_PUNCT = re.compile(r"[^a-z0-9+#]+")

# Canonical name -> accepted aliases (lowercase, punctuation-stripped).
_CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "javascript": ("js", "javascript", "ecmascript"),
    "typescript": ("ts", "typescript"),
    "python": ("python", "py"),
    "react": ("react", "reactjs"),
    "nextjs": ("next", "nextjs"),
    "nodejs": ("node", "nodejs"),
    "vue": ("vue", "vuejs"),
    "angular": ("angular", "angularjs"),
    "express": ("express", "expressjs"),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "postgresql": ("postgres", "postgresql", "psql"),
    "mysql": ("mysql",),
    "mongodb": ("mongo", "mongodb"),
    "redis": ("redis",),
    "elasticsearch": ("elasticsearch", "elastic", "es"),
    "kubernetes": ("kubernetes", "k8s"),
    "docker": ("docker",),
    "aws": ("aws", "amazonwebservices"),
    "gcp": ("gcp", "googlecloud", "googlecloudplatform"),
    "azure": ("azure", "microsoftazure"),
    "graphql": ("graphql",),
    "rest": ("rest", "restapi", "restful"),
    "html": ("html", "html5"),
    "css": ("css", "css3"),
    "sass": ("sass", "scss"),
    "tailwind": ("tailwind", "tailwindcss"),
    "c++": ("c++", "cpp", "cplusplus"),
    "c#": ("c#", "csharp"),
    "golang": ("go", "golang"),
    "java": ("java",),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "ruby": ("ruby",),
    "php": ("php",),
    "rust": ("rust",),
    "scala": ("scala",),
    "tensorflow": ("tensorflow", "tf"),
    "pytorch": ("pytorch", "torch"),
    "pandas": ("pandas",),
    "numpy": ("numpy", "np"),
    "spark": ("spark", "apachespark"),
    "airflow": ("airflow", "apacheairflow"),
    "kafka": ("kafka", "apachekafka"),
    "terraform": ("terraform",),
    "ansible": ("ansible",),
    "linux": ("linux",),
    "git": ("git",),
    "github": ("github",),
    "gitlab": ("gitlab",),
    "cicd": ("cicd", "ci", "cd"),
    "machine learning": ("ml", "machinelearning"),
    "artificial intelligence": ("ai", "artificialintelligence"),
    "natural language processing": ("nlp", "naturallanguageprocessing"),
    "large language model": ("llm", "largelanguagemodel"),
}


def _normalize_key(value: str) -> str:
    text = str(value or "").strip().lower().replace(".js", "js").replace(".ts", "ts")
    return _PUNCT.sub("", text)


_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in _CANONICAL_ALIASES.items():
    _ALIAS_TO_CANONICAL[_normalize_key(canonical)] = canonical
    for alias in aliases:
        key = _normalize_key(alias)
        if key:
            _ALIAS_TO_CANONICAL[key] = canonical


def canonical_skill(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    key = _normalize_key(raw)
    if not key:
        return ""
    return _ALIAS_TO_CANONICAL.get(key, key)


def canonical_set(names: list[str] | tuple[str, ...] | None) -> set[str]:
    keys: set[str] = set()
    for name in names or []:
        key = canonical_skill(str(name))
        if key:
            keys.add(key)
    return keys
