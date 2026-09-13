from atlas_decision_architecture import CORE_ASSETS, PRODUCT_HORIZON, EVALUATION_HORIZONS_H, PRODUCTION_THRESHOLD


def test_product_contract_is_unchanged():
    assert CORE_ASSETS == ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT')
    assert PRODUCT_HORIZON == '4-12H'
    assert EVALUATION_HORIZONS_H == (4, 8, 12)
    assert PRODUCTION_THRESHOLD == 68
