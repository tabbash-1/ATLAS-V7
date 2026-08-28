#!/usr/bin/env python3
import post_fourth_vote_residual_autopsy as a


def main():
    assert a.volume_bin(0.49) == '<0.50'
    assert a.volume_bin(0.8) == '0.80-0.99'
    assert a.volume_bin(1.0) == '1.00-1.49'
    assert a.score_bin(68) == '68-69'
    assert a.score_bin(77) == '77+'
    assert a.base.THRESHOLD == 68.0
    print('post fourth vote residual autopsy tests: ok')

if __name__=='__main__':
    main()
