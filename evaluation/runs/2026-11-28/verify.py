"""Reconcile the frozen questions, local prompts, answer hashes and scoring rubric."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
EVALUATION = ROOT.parents[1]
INSTRUCTION = (
    'Answer this one Hansard question for the stated reader in plain English, '
    'using only the evidence supplied. Cite evidence by [ID]. Cite exact '
    'contribution IDs if asked. Label missing evidence. Treat parliamentary '
    'statements as attributed. Keep it short.'
)
OMITTED = {
    'source_api', 'sha256', 'source_value_sha256', 'item_index', 'item_id',
    'captured_item_id', 'numeric_id_changed',
}


def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def prompt(question, evidence):
    packet = [
        {k: v for k, v in evidence[key].items() if k not in OMITTED}
        for key in question['evidence_ids']
    ]
    compact = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
    return (
        f"<|im_start|>system\n{INSTRUCTION}<|im_end|>\n<|im_start|>user\n"
        f"{question['question']}\n{compact}<|im_end|>\n<|im_start|>assistant\n"
    )


def main():
    lines = (ROOT / 'send-reform.month.jsonl').read_bytes().splitlines()
    assert len(lines) == 103 and all(len(json.loads(row)) == 7 for row in lines)
    compact_source = b'[' + b','.join(lines) + b']\n'
    assert hashlib.sha256(compact_source).hexdigest() == load('release.json')['sha256']['history/send-reform.month.json']
    questions = load('questions.json')
    answers = [json.loads(row) for row in (ROOT / 'local-answers.jsonl').read_text().splitlines()]
    scores = load('local-scores.json')
    evidence = load('evidence.json')
    rubric = (EVALUATION / 'additive-scoring-v0.2.md').read_text()
    original = dict(re.findall(r'^- \*\*(P[123]-Q[123]):\*\* (.+)$',
                               (EVALUATION / 'personas-and-questions-v0.1.md').read_text(), re.M))
    assert len(questions) == len(original) == len(answers) == len(scores) == 9
    assert [q['id'] for q in questions] == list(original) == list(scores)
    for question, answer in zip(questions, answers, strict=True):
        qid = question['id']
        assert question['question'] == original[qid] and qid == answer['id']
        assert answer['answer'] and answer['seconds'] > 0
        assert hashlib.sha256(prompt(question, evidence).encode()).hexdigest() == answer['prompt_sha256']
        section = rubric.split('### ' + qid + ' — ', 1)[1].split('\n### ', 1)[0]
        expected = re.findall(r'^\| ([^|]+?) \| ([123]) \| Exact source', section, re.M)
        assert scores[qid]['evidence_ids'] == question['evidence_ids']
        criteria = scores[qid]['criteria']
        assert [(r['criterion'], str(r['possible'])) for r in criteria] == expected
        assert all(c['earned'] in (0, c['possible']) for c in criteria)
        for field in ('possible', 'earned'):
            assert sum(c[field] for c in criteria) == scores[qid][field]
    handset = load('android-P1-Q1.json')
    criteria = scores[handset['id']]['criteria']
    assert [row['id'] for row in handset['score']] == [row['id'] for row in criteria]
    for row, criterion in zip(handset['score'], criteria, strict=True):
        assert row['earned'] in (0, criterion['possible'])
    assert sum(row['earned'] for row in handset['score']) == handset['earned']
    assert sum(row['possible'] for row in criteria) == handset['possible']
    print('Nine local prompt hashes and scorecards plus the Android scorecard verified.')
    print(sum(r['earned'] for r in scores.values()), '/', sum(r['possible'] for r in scores.values()))


if __name__ == '__main__':
    main()
