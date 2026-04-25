import json
import re


class CavemanCompressor:

    FITNESS_ABBREVS: dict[str, str] = {
        "heart rate variability": "hrv",
        "training stress score": "tss",
        "acute chronic workload ratio": "acwr",
        "beats per minute": "bpm",
        "body battery": "bb",
        "sleep score": "slp_score",
        "sleep duration": "slp_dur",
        "deep sleep": "deep_slp",
        "rem sleep": "rem_slp",
        "resting heart rate": "rhr",
        "average heart rate": "avg_hr",
        "maximum heart rate": "max_hr",
        "training load": "trn_load",
        "readiness score": "rdns",
        "training gate": "gate",
        "perceived effort": "rpe",
        "rate of perceived exertion": "rpe",
        "zone 1": "z1",
        "zone 2": "z2",
        "zone 3": "z3",
        "zone 4": "z4",
        "zone 5": "z5",
        "minutes": "min",
        "seconds": "sec",
        "kilometers": "km",
        "kilocalories": "kcal",
        "not applicable": "n/a",
    }

    FILLER_PATTERNS: list[str] = [
        r"Please\s+",
        r"I would like you to\s+",
        r"Make sure (?:to\s+|that\s+)",
        r"It is important (?:to\s+|that\s+)",
        r"You should\s+",
        r"Note that\s+",
        r"Keep in mind that\s+",
        r"As an AI,?\s+",
    ]

    def __init__(self) -> None:
        # Pre-compile filler patterns
        self._filler_re = [re.compile(p, re.IGNORECASE) for p in self.FILLER_PATTERNS]
        # Pre-compile abbreviation patterns (longest first to avoid partial matches)
        sorted_abbrevs = sorted(self.FITNESS_ABBREVS, key=len, reverse=True)
        self._abbrev_re = [
            (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), repl)
            for phrase, repl in (
                (p, self.FITNESS_ABBREVS[p]) for p in sorted_abbrevs
            )
        ]
        # JSON block pattern
        self._json_block_re = re.compile(
            r"(\{[^{}]{10,}\}|\[[^\[\]]{10,}\])"
        )

    def compress(self, text: str) -> tuple[str, float]:
        original_len = len(text)
        if original_len == 0:
            return text, 0.0

        result = text

        # a. Strip filler patterns
        for pat in self._filler_re:
            result = pat.sub("", result)

        # b. Apply fitness abbreviations
        for pat, repl in self._abbrev_re:
            result = pat.sub(repl, result)

        # c. Compact JSON blocks
        def _compact_json(m: re.Match) -> str:
            block = m.group(0)
            try:
                parsed = json.loads(block)
                return json.dumps(parsed, separators=(",", ":"), default=str)
            except (json.JSONDecodeError, ValueError):
                return block

        result = self._json_block_re.sub(_compact_json, result)

        # d. Collapse 3+ newlines into 2
        result = re.sub(r"\n{3,}", "\n\n", result)

        # e. Strip trailing whitespace from each line
        result = "\n".join(line.rstrip() for line in result.split("\n"))

        ratio = 1 - (len(result) / original_len)
        return result, ratio

    def compress_json_value(self, obj: dict | list) -> str:
        raw = json.dumps(obj, separators=(",", ":"), default=str)
        return raw.replace(":null", ":~").replace("[null", "[~").replace(",null", ",~")


compressor = CavemanCompressor()


def compress(text: str) -> tuple[str, float]:
    return compressor.compress(text)


def compress_json(obj: dict | list) -> str:
    return compressor.compress_json_value(obj)


if __name__ == "__main__":
    sample = """\
Please analyze the following athlete data. I would like you to provide a detailed assessment.

Heart Rate Variability: 65 ms (baseline 70 ms)
Resting Heart Rate: 52 beats per minute
Training Stress Score: 87
Acute Chronic Workload Ratio: 1.3
Body Battery: min 15, max 80
Sleep Score: 78
Sleep Duration: 420 minutes
Deep Sleep: 95 minutes
REM Sleep: 110 minutes
Average Heart Rate during workout: 155 beats per minute
Maximum Heart Rate: 182 beats per minute

Note that the athlete completed a Zone 3 training session lasting 45 minutes
followed by Zone 1 recovery for 15 minutes. Keep in mind that the training load
has been increasing over the past week.

It is important to consider the perceived effort was 7/10 and the
rate of perceived exertion aligns with the heart rate data.

Activity data: {"activityId": 12345, "distance": 5017.8, "duration": 2716, "calories": 314, "averageHR": 148, "maxHR": 182, "steps": 5878}

You should provide recommendations for tomorrow's training.
As an AI fitness coach, make sure to prioritize recovery if needed.
"""

    compressed, ratio = compress(sample)
    print(f"Original:   {len(sample)} chars")
    print(f"Compressed: {len(compressed)} chars")
    print(f"Ratio:      {ratio:.1%}")
    print(f"\n--- Compressed output ---\n{compressed}")
