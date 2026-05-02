import subprocess
import csv
from pathlib import Path

ROOT = Path(__file__).parent
CORPUS = ROOT / 'sample_support_corpus.csv'
TICKETS = ROOT / 'support_tickets_extracted' / 'support_tickets' / 'sample_support_tickets.csv'
OUT = ROOT / 'support_tickets_extracted' / 'support_tickets' / 'triaged_sample_test.csv'

def run_trie():
    cmd = ['python', str(ROOT / 'triage_agent.py'), '--corpus', str(CORPUS), '--tickets', str(TICKETS), '--out', str(OUT)]
    print('Running:', ' '.join(cmd))
    subprocess.check_call(cmd)

def validate():
    required = ['status','product_area','response','justification','request_type']
    with OUT.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for r in required:
            if r not in headers:
                raise SystemExit(f'Missing required column: {r}')
        # Ensure at least one non-empty response
        any_response = False
        for row in reader:
            if row.get('response','').strip():
                any_response = True
                break
        if not any_response:
            raise SystemExit('No non-empty responses in output')
    print('Validation passed — output columns present and responses non-empty')

if __name__ == '__main__':
    run_trie()
    validate()
