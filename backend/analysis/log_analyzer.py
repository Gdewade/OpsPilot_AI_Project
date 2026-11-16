"""Rule-based log analysis: levels, severity, signals, prompt-injection check."""

import re

LEVEL_RE = re.compile(r"\b(CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG)\b", re.I)

# Lines without an explicit level that still look like failures.
ERROR_HINTS = re.compile(
    r"exception|traceback|timed? ?out|refused|failed|failure|denied|unreachable|"
    r"out of memory|oom|no space left|segfault|panic",
    re.I,
)

# Patterns that make an incident critical on their own.
CRITICAL_PATTERNS = re.compile(
    r"out of memory|oomkilled|no space left on device|data corruption|"
    r"disk (is )?full|segfault|kernel panic",
    re.I,
)

# Category -> keywords. Used for query rewriting and confidence signals.
SIGNALS: dict[str, re.Pattern] = {
    "database": re.compile(r"postgres|database|\bdb\b|sql|pg_|connection pool|too many connections", re.I),
    "redis": re.compile(r"redis|cache", re.I),
    "memory": re.compile(r"out of memory|oom|memory|heap", re.I),
    "cpu": re.compile(r"\bcpu\b|load average|throttl", re.I),
    "disk": re.compile(r"no space left|disk|inode|volume", re.I),
    "network": re.compile(r"connection (refused|reset)|unreachable|dns|socket|timeout|timed out", re.I),
    "auth": re.compile(r"auth|password|token|credential|unauthori[sz]ed|forbidden|\b40[13]\b", re.I),
    "http_5xx": re.compile(r"\b5\d\d\b|bad gateway|service unavailable|internal server error", re.I),
    "deployment": re.compile(r"deploy|rollout|release|migration|rollback|crashloop", re.I),
    "latency": re.compile(r"slow|latency|took \d+|response time|p9\d", re.I),
}

INJECTION_RE = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)|"
    r"disregard (the )?(system|previous) |you are now |system prompt|"
    r"reveal (your|the) (instructions|prompt|key)",
    re.I,
)

_TS_RE = re.compile(
    r"^\s*\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\]?\s*"
    r"|^\s*\[?\d{2}:\d{2}:\d{2}\]?\s*"
)


# Words that appear in almost every log/runbook and say nothing about the cause.
GENERIC_TERMS = frozenset(
    """error errors warning warn info debug critical fatal failed failure fail exception
    the and for with from that this was were are has have not after before into than then
    service request requests server process processes exited exit code unable cannot could
    would should when while during user users app application api""".split()
)


def distinctive_terms(text: str) -> set[str]:
    """Meaningful words of a log line: no timestamps, numbers, levels or filler."""
    text = _TS_RE.sub("", text)
    return {
        w
        for w in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower())
        if w not in GENERIC_TERMS
    }


def normalize_line(line: str) -> str:
    """Lowercase, drop a leading timestamp, collapse whitespace.

    Used both to deduplicate log lines and to check that a line quoted by
    the model really exists in the original logs.
    """
    return re.sub(r"\s+", " ", _TS_RE.sub("", line)).strip().lower()


def _level_of(line: str) -> str:
    match = LEVEL_RE.search(line)
    if match:
        level = match.group(1).upper()
        return "WARNING" if level.startswith("WARN") else level
    return "ERROR" if ERROR_HINTS.search(line) else "OTHER"


def analyze_logs(log_text: str) -> dict:
    lines = [ln.strip() for ln in log_text.splitlines() if ln.strip()]
    errors, warnings, critical = [], [], []
    for line in lines:
        level = _level_of(line)
        if level in ("CRITICAL", "FATAL") or CRITICAL_PATTERNS.search(line):
            critical.append(line)
            errors.append(line)
        elif level == "ERROR":
            errors.append(line)
        elif level == "WARNING":
            warnings.append(line)

    def unique(items: list[str]) -> list[str]:
        seen, out = set(), []
        for item in items:
            key = normalize_line(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out

    errors_u, warnings_u = unique(errors), unique(warnings)

    # critical: fatal/OOM/disk-full. high: repeated errors. medium: a few
    # errors or many warnings. low: everything else.
    if critical:
        severity = "critical"
    elif len(errors) >= 3:
        severity = "high"
    elif errors or len(warnings) >= 3:
        severity = "medium"
    else:
        severity = "low"

    haystack = "\n".join(errors_u + warnings_u) or log_text
    signals = [name for name, rx in SIGNALS.items() if rx.search(haystack)]

    return {
        "total_lines": len(lines),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "critical_count": len(critical),
        "unique_errors": errors_u,
        "unique_warnings": warnings_u,
        "signals": signals,
        "severity": severity,
        "injection_suspected": bool(INJECTION_RE.search(log_text)),
    }
