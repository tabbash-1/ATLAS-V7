#!/usr/bin/env python3
import long_3h_confirmation_entry_shadow as s


def main():
    r={'return_3h_pct':1.0,'return_12h_pct':3.02}
    assert s.confirmed(r) is True
    # (1.0302 / 1.01 - 1) ~= 2%
    assert round(s.delayed_return(r),4) == 2.0
    assert s.confirmed({'return_3h_pct':-0.1}) is False
    assert s.base.THRESHOLD == 68.0
    print('long 3h confirmation entry shadow tests: ok')

if __name__=='__main__': main()
