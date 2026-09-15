#!/usr/bin/env python3
"""Audit the actual ATLAS Production alpha path without mutating it."""
from __future__ import annotations
import ast, json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parent
SCORER=ROOT/'production_signal_scoring.py'
OUT=ROOT/'status/production-alpha-path-audit-latest.json'

EXPECTED_FORMULA=['trend_base','volume_bonus','relative_strength_adjustment','futures_adjustment','obstacle_adj']
SHADOW_OR_NON_SCORE=['whale10','smart_money','news','event','liquidity','pattern_memory','portfolio_risk']

def build():
    text=SCORER.read_text()
    tree=ast.parse(text)
    raw_expr=None
    version=None
    for n in ast.walk(tree):
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name) and t.id=='VERSION' and isinstance(n.value,ast.Constant): version=n.value.value
                if isinstance(t,ast.Name) and t.id=='raw_score': raw_expr=ast.unparse(n.value)
    present={x: bool(re.search(r'\b'+re.escape(x)+r'\b',text,re.I)) for x in SHADOW_OR_NON_SCORE}
    formula_ok=all(x in (raw_expr or '') for x in EXPECTED_FORMULA)
    return {
      'schema':'ATLAS_PRODUCTION_ALPHA_PATH_AUDIT_V1','product_horizon':'4-12H',
      'scorer_file':'production_signal_scoring.py','scoring_version':version,
      'raw_score_expression':raw_expr,'formula_components':EXPECTED_FORMULA,'formula_contract_ok':formula_ok,
      'decision_chain':[
        '1H spot candles -> EMA20/EMA50/RSI/momentum/ATR',
        'direction vote (>=3 of 4)',
        'paced relative volume',
        'relative strength vs BTC',
        'validated futures adjustment',
        'prior structural obstacle + breakout confirmation',
        'raw score -> threshold qualification',
        'playbook/regime label -> trade geometry -> downstream Final Gate'
      ],
      'non_score_feature_presence_in_scorer':present,
      'finding':'Production alpha remains a compact score; research intelligence must prove incremental forward R before promotion.',
      'production_mutation_authorized':False,'research_only':True,'automatic_promotion':False
    }

def main():
    out=build(); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,indent=2,sort_keys=True)); print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()
