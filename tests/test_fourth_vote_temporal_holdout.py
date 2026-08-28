#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone
import fourth_vote_temporal_holdout as h


def main():
    rows=[]
    t=datetime(2026,8,24,0,tzinfo=timezone.utc)
    for i in range(10):
        rows.append({'captured_at':t+timedelta(hours=i)})
    train, hold, cutoff=h.split_hourly(rows)
    assert len(train)==6
    assert len(hold)==4
    assert cutoff == t+timedelta(hours=6)
    assert h.TRAIN_FRACTION == 0.60
    print('fourth vote temporal holdout tests: ok')

if __name__ == '__main__':
    main()
