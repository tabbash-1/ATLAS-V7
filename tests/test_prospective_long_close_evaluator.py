#!/usr/bin/env python3
from datetime import timezone
import prospective_long_close_evaluator as e


def main():
    assert e.PROSPECTIVE_START_AT.astimezone(timezone.utc).isoformat() == '2026-08-28T09:04:14+00:00'
    assert e.SCHEMA == 'ATLAS_PROSPECTIVE_LONG_CLOSE_EVALUATION_V1'
    assert e.base.THRESHOLD == 68.0
    print('prospective long close evaluator tests: ok')


if __name__ == '__main__':
    main()
