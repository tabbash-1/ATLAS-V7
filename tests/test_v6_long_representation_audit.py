#!/usr/bin/env python3
import v6_long_representation_audit as a


def main():
    assert a.H == 12
    assert a.base.THRESHOLD == 68.0
    assert a.score_band(51) == '<52'
    assert a.score_band(68) == '68-71'
    assert a.score_band(76) == '76+'
    assert 'score' in a.NUMERIC
    print('v6 long representation audit tests: ok')

if __name__=='__main__': main()
