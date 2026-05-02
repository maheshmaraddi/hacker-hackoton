#!/usr/bin/env python3
"""
Terminal-based Support Triage Agent

Usage:
  python triage_agent.py --corpus corpus.csv --tickets support_tickets.csv --out triaged_output.csv

Corpus CSV format (required columns): company,category,title,content,url
Tickets CSV format (required columns): issue,subject,company

The agent uses only the provided corpus file to retrieve supporting docs.
"""
import argparse
import csv
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

KEYWORDS_BUG = [r"\bbug\b", r"\berror\b", r"\bcrash\b", r"\bnot work\b", r"\bfailed\b", r"\bissue\b"]
KEYWORDS_FEATURE = [r"\bfeature request\b", r"\bfeature\b", r"\benhancement\b", r"\badd .* feature\b"]
KEYWORDS_INVALID = [r"\bspam\b", r"\binvalid\b", r"\bnot relevant\b"]
KEYWORDS_SENSITIVE = [r"password", r"card number", r"credit card", r"ssn", r"social security", r"bank", r"fraud", r"billing", r"charge", r"refund", r"login", r"account locked", r"suspend"]
KEYWORDS_URGENT = [r"urgent", r"asap", r"immediately", r"right now", r"critical"]

def load_csv(path: Path) -> List[Dict[str,str]]:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

def classify_request_type(text: str) -> str:
    t = text.lower()
    for p in KEYWORDS_BUG:
        if re.search(p, t):
            return 'bug'
    for p in KEYWORDS_FEATURE:
        if re.search(p, t):
            return 'feature_request'
    for p in KEYWORDS_INVALID:
        if re.search(p, t):
            return 'invalid'
    return 'product_issue'

def assess_risk_urgency(text: str) -> Tuple[bool,bool]:
    t = text.lower()
    risk = any(re.search(p, t) for p in KEYWORDS_SENSITIVE)
    urgent = any(re.search(p, t) for p in KEYWORDS_URGENT)
    return risk, urgent

def build_corpus_index(corpus: List[Dict[str,str]]):
    # Combine title + content for retrieval
    docs = [((row.get('company') or '').strip(), (row.get('category') or '').strip(), row.get('title',''), row.get('content',''), row.get('url','')) for row in corpus]
    texts = [((row[2] or '') + '\n' + (row[3] or '')) for row in docs]
    if TfidfVectorizer is None:
        return docs, None, texts
    vect = TfidfVectorizer(stop_words='english')
    X = vect.fit_transform(texts)
    return docs, (vect, X), texts

def retrieve_docs(query: str, docs, index, texts, top_k=3, company: str = None):
    # If company provided, filter docs first to prefer same-company articles
    candidate_indices = list(range(len(docs)))
    if company:
        company = company.strip().lower()
        filtered = [i for i,d in enumerate(docs) if (d[0] or '').strip().lower() == company]
        if filtered:
            candidate_indices = filtered


    if index is None or TfidfVectorizer is None:
        # simple keyword match fall-back restricted to candidates
        q = query.lower()
        scores = []
        for i in candidate_indices:
            txt = texts[i]
            s = sum(1 for w in q.split() if w and w in txt.lower())
            scores.append((s,i))
        scores.sort(reverse=True)
        return [(docs[idx], float(score)) for score, idx in scores[:top_k]]

    vect, X = index
    qv = vect.transform([query])
    sims = cosine_similarity(qv, X)[0]
    # sort only among candidate indices
    cand_scores = sorted(((float(sims[i]), i) for i in candidate_indices), key=lambda x: x[0], reverse=True)
    idxs = [i for _, i in cand_scores[:top_k]]
    # if we don't have enough from company, fill from global ranking
    if len(idxs) < top_k:
        global_idxs = sims.argsort()[::-1]
        for gi in global_idxs:
            if gi not in idxs:
                idxs.append(gi)
            if len(idxs) >= top_k:
                break
    return [(docs[i], float(sims[i])) for i in idxs[:top_k]]

def snippet(text: str, max_sentences=2) -> str:
    # naive sentence split
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(parts[:max_sentences]).strip()

def decide_escalation(request_type: str, risk: bool, urgent: bool, top_docs_with_scores: List[Tuple], confidence_threshold: float = 0.12) -> Tuple[str,str]:
    # If risk or account/billing/fraud or invalid product mapping -> escalate
    top_docs = [d for d, s in top_docs_with_scores]
    scores = [s for d, s in top_docs_with_scores]
    categories = [d[1].lower() for d in top_docs if d[1]]
    # escalate on any detected sensitive keywords
    if risk:
        return 'escalated', 'Sensitive information detected (billing, fraud, account access, identity)'
    if request_type == 'invalid':
        return 'replied', 'Ticket classified as invalid — replied with out-of-scope guidance'
    # product area unknown or empty => escalate
    if not categories or all(not c for c in categories):
        return 'escalated', 'Could not determine product area from corpus'
    # urgent bugs -> escalate
    if urgent and request_type == 'bug':
        return 'escalated', 'Urgent bug requires human triage'
    # Low confidence in retrieval -> escalate
    if scores:
        top_score = scores[0]
        if top_score < confidence_threshold:
            return 'escalated', f'Low confidence in matched documentation (score={top_score:.3f})'
    return 'replied', 'Safe to reply automatically'

def build_response(ticket: Dict[str,str], docs_with_scores: List[Tuple], status: str) -> str:
    # Responses must be strictly grounded in the provided corpus.
    if status == 'escalated':
        reasons = []
        for d, s in docs_with_scores[:2]:
            title = d[2] or ''
            url = d[4] or ''
            if title or url:
                reasons.append(f"{title} ({url})")
        reasons_text = '\n'.join(reasons) if reasons else 'No matching support article found in corpus.'
        return f"Escalated to human agent. Relevant articles:\n{reasons_text}"

    # replied: include only a short snippet from the top doc and the citation — no new policy claims
    if not docs_with_scores:
        return "No relevant support documentation found in the provided corpus; escalated for human review."
    top, score = docs_with_scores[0]
    title, content, url = top[2], top[3], top[4]
    snip = snippet(content or '')
    resp = f"{snip}\n\nSource: {title} ({url})"
    return resp

def triage(corpus_file: Path, tickets_file: Path, out_file: Path, confidence_threshold: float = 0.12):
    corpus = load_csv(corpus_file)
    tickets = load_csv(tickets_file)
    docs, index, texts = build_corpus_index(corpus)

    # Ensure we don't duplicate any of the standardized output columns if present in input (case-insensitive)
    target_cols = {'status', 'product_area', 'response', 'justification', 'request_type'}
    if tickets:
        original_fields = [k for k in tickets[0].keys() if k.lower() not in target_cols]
    else:
        original_fields = []
    fieldnames = original_fields + ['status', 'product_area', 'response', 'justification', 'request_type']

    with out_file.open('w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        for t in tickets:
            issue = ' '.join([t.get('subject',''), t.get('issue','')])
            req_type = classify_request_type(issue)
            risk, urgent = assess_risk_urgency(issue)
            top_docs_with_scores = retrieve_docs(issue, docs, index, texts, top_k=3, company=(t.get('company') or None))
            status, justification_decision = decide_escalation(req_type, risk, urgent, top_docs_with_scores, confidence_threshold)
            product_area = top_docs_with_scores[0][0][1] if top_docs_with_scores and top_docs_with_scores[0][0][1] else ''
            response = build_response(t, top_docs_with_scores, status)
            justification = f"Decision: {justification_decision}; Matched docs: {[(d[2], d[4]) for d, s in top_docs_with_scores[:2]]}"
            # Remove any existing keys that collide with our standardized outputs (case-insensitive)
            sanitized = {k: v for k, v in t.items() if k.lower() not in target_cols}
            out_row = sanitized
            out_row.update({'status': status, 'product_area': product_area, 'response': response, 'justification': justification, 'request_type': req_type})
            # Ensure the writer writes fields in the specified order
            writer.writerow({fn: out_row.get(fn, '') for fn in fieldnames})

def triage_cli(corpus: str, tickets: str, out: str, confidence_threshold: float):
    triage(Path(corpus), Path(tickets), Path(out), confidence_threshold=confidence_threshold)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--corpus', required=True)
    p.add_argument('--tickets', required=True)
    p.add_argument('--out', default='triaged_output.csv')
    p.add_argument('--confidence-threshold', type=float, default=0.12, help='Score threshold below which matches are considered low-confidence and escalated')
    args = p.parse_args()
    triage_cli(args.corpus, args.tickets, args.out, args.confidence_threshold)

if __name__ == '__main__':
    main()
