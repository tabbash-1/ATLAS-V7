#!/usr/bin/env python3
import long_3h_failfast_exit_shadow as s


def main():
    assert s.overlay_return({'return_3h_pct':-1.2,'return_12h_pct':-4.0}) == -1.2
    assert s.overlay_return({'return_3h_pct':1.2,'return_12h_pct':2.0}) == 2.0
    assert s.action_at_3h({'return_3h_pct':-0.1}) == 'EXIT_EARLY'
    assert s.action_at_3h({'return_3h_pct':0.1}) == 'HOLD_TO_12H'
    assert s.base.THRESHOLD == 68.0
    print('long 3h fail-fast exit shadow tests: ok')

if __name__=='__main__': main()
