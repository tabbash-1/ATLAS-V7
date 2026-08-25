from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import whale10_consensus as w


def entity(i, z=1.0, entity_type='FUND', validated=True, confidence='HIGH'):
    return {
        'entity_id': f'w{i}',
        'symbol': 'BTCUSDT',
        'entity_type': entity_type,
        'validated': validated,
        'independent': True,
        'source_confidence': confidence,
        'netflow_z': z,
    }


def test_refuses_less_than_ten_validated_entities():
    r = w.build_consensus([entity(i) for i in range(9)], 'BTCUSDT')
    assert r['status'] == 'INSUFFICIENT_VALIDATED_WHALES'
    assert r['consensus'] is None
    assert r['production_eligible'] is False


def test_excludes_exchange_wallets():
    rows = [entity(i) for i in range(9)] + [entity(9, entity_type='EXCHANGE')]
    r = w.build_consensus(rows, 'BTCUSDT')
    assert r['validated_entities'] == 9
    assert any(x['reason'] == 'EXCLUDED_EXCHANGE' for x in r['rejected_entities'])


def test_ten_independent_whales_generate_consensus():
    rows = [entity(i, 1.2 if i < 7 else (-1.0 if i < 9 else 0.0)) for i in range(10)]
    r = w.build_consensus(rows, 'BTCUSDT')
    assert r['status'] == 'READY_RESEARCH_ONLY'
    assert r['counts'] == {'accumulating': 7, 'neutral': 1, 'distributing': 2}
    assert r['consensus_score'] == 50.0
    assert r['consensus'] == 'ACCUMULATION'
    assert r['production_eligible'] is False


if __name__ == '__main__':
    test_refuses_less_than_ten_validated_entities()
    test_excludes_exchange_wallets()
    test_ten_independent_whales_generate_consensus()
    print('whale10 consensus tests: ok')
