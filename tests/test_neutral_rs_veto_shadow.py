#!/usr/bin/env python3
import neutral_rs_veto_shadow as s


def main():
    assert s.is_vetoed({'rs_reason':'NEUTRAL'}) is True
    assert s.is_vetoed({'rs_reason':'ALIGNED_STRONG'}) is False
    assert s.base.THRESHOLD == 68.0
    # Guard the inherited combined baseline: LONG+CLOSE remains vetoed before
    # the third shadow is considered.
    row = {'direction':'LONG','obstacle_reason':'CLOSE_PRIOR_STRUCTURE','rs_reason':'ALIGNED_STRONG'}
    assert s.combined.is_vetoed(row) is True
    print('neutral rs veto shadow tests: ok')

if __name__ == '__main__':
    main()
