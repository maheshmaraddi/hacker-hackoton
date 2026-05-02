Submission checklist for HackerRank verification

- [x] Terminal-based script: `triage_agent.py` accepts `--corpus`, `--tickets`, `--out`.
- [x] Uses only provided corpus: responses are sourced from `sample_support_corpus.csv` (corpus-grounded).
- [x] Avoids unsupported claims: responses are snippets + citations.
- [x] Escalates high-risk or low-confidence cases.
- [x] Test runner: `run_tests.py` verifies output columns and non-empty responses.
- [x] Instructions in `README.md` for running and verifying.

How to verify locally

1. Install dependencies: `pip install -r requirements.txt`
2. Run tests: `python run_tests.py`
3. Run agent on full tickets: `python triage_agent.py --corpus sample_support_corpus.csv --tickets support_tickets_extracted/support_tickets/support_tickets.csv --out triaged_output.csv`
