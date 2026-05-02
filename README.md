# Support Triage Agent

Terminal-based triage agent that processes support tickets using only a provided support corpus.


Quick start

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Prepare a corpus CSV with columns: `company,category,title,content,url`.

3. Run the agent:

```
python triage_agent.py --corpus sample_support_corpus.csv --tickets support_tickets_extracted/support_tickets/support_tickets.csv --out triaged_output.csv
```

Outputs a CSV with added fields: `status,product_area,response,justification,request_type`.

Verification
- A small test runner is included: run `python run_tests.py`. It runs the agent on the sample tickets and verifies required columns and at least one non-empty response.

Security & Safety
- The agent only uses the provided corpus file. Responses are strictly grounded: replies include a short snippet from the matched support article and a citation (title + URL). The agent will escalate low-confidence or sensitive cases.

Expected request types: `product_issue`, `feature_request`, `bug`, `invalid`.

Submission package
- Included files for submission: `triage_agent.py`, `run_tests.py`, `README.md`, `requirements.txt`, `sample_support_corpus.csv`, and sample tickets under `support_tickets_extracted/support_tickets/`.

