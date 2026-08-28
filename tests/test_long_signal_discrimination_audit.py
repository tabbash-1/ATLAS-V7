#!/usr/bin/env python3
import long_signal_discrimination_audit as a


def main():
    assert a.H == 12
    assert a.base.THRESHOLD == 68.0
    assert a.rankdata([10,20,20,30]) == [1.0,2.5,2.5,4.0]
    assert round(a.spearman([1,2,3],[1,2,3]),6) == 1.0
    assert round(a.spearman([1,2,3],[3,2,1]),6) == -1.0
    print('long signal discrimination audit tests: ok')

if __name__=='__main__': main()
