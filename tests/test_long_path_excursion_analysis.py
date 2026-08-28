#!/usr/bin/env python3
from datetime import timedelta
import long_path_excursion_analysis as a


def main():
    t0=a.base.parse_time('2026-08-01T00:00:00+00:00')
    series={'times':[t0+timedelta(hours=h) for h in (0,1,3,12,13)],'prices':[100,101,99,103,104]}
    pts=a.path_points(series,t0,12)
    assert len(pts)==4
    assert pts[-1][1]==103
    assert a.base.THRESHOLD==68.0
    assert a.combined_long({'direction':'SHORT'}) is False
    print('long path excursion analysis tests: ok')

if __name__=='__main__': main()
