#!/usr/bin/env python3
import post_combined_shadow_residual_autopsy as a


def main():
    assert a.volume_bin(0.49) == '<0.50'
    assert a.volume_bin(0.8) == '0.80-0.99'
    assert a.score_bin(68) == '68-69'
    assert a.score_bin(77) == '77+'
    assert a.base.THRESHOLD == 68.0
    # The combined scope must preserve the LONG+CLOSE veto from the validated
    # second shadow rather than silently reverting to fourth-vote alone.
    row = {'direction':'LONG','obstacle_reason':'CLOSE_PRIOR_STRUCTURE'}
    assert a.lc.is_vetoed(row) is True
    print('post combined shadow residual autopsy tests: ok')

if __name__ == '__main__':
    main()
