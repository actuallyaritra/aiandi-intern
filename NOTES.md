# Notes

## How to run

1. Copy `cloud-flare.sh` to `cloud-flare.local.sh` and add your Cloudflare Account ID and API token.
2. Run `python3 classify.py` to use the default model.
3. Run `python3 classify.py clef` to use the larger model.
4. Open `comments_report.html` in a browser to review the results.

## Tools and models used

- Python 3 for the classification script.
- Cloudflare Workers AI for comment classification.
- `clef-flash` and `clef` for model comparison.

## What I felt about this task

The task helped me understand how AI can classify comments as acceptable, toxic, or spam. The HTML report made it easier to review predictions. I learned that confidence scores do not guarantee correctness and that human review is important for identifying contextual errors.

Also, I understood the importance of System One decision models. Unlike traditional generative Large Language Models (LLMs) that output conversational text, these specialized models are designed to take inputs (like text or images) and instantly return bounded, structured JSON decisions (such as classification, yes/no flags, or scores) along with calibrated probabilities.

I felt performance can be further improved with the inclusion of Jev and Laya.