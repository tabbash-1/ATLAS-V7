#!/usr/bin/env python3
import episode_substitution_audit as a


def main():
    assert a.H == 24
    assert a.base.THRESHOLD == 68.0
    assert a.neutral.is_vetoed({'rs_reason':'NEUTRAL'}) is True
    row={'symbol':'BTCUSDT','direction':'LONG','captured_at':a.base.parse_time('2026-08-01T00:00:00+00:00')}
    assert a.eid(row).startswith('BTCUSDT|LONG|')
    print('episode substitution audit tests: ok')

if __name__=='__main__':
    main()
