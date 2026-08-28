#!/usr/bin/env python3
from datetime import timezone
import prospective_fourth_vote_evaluator as e


def main():
    assert e.PROSPECTIVE_START_AT.tzinfo is not None
    assert e.PROSPECTIVE_START_AT.astimezone(timezone.utc).isoformat() == '2026-08-28T08:56:44+00:00'
    assert e.SCHEMA == 'ATLAS_PROSPECTIVE_FOURTH_VOTE_EVALUATION_V1'
    assert e.base.THRESHOLD == 68.0
    print('prospective fourth vote evaluator tests: ok')


if __name__ == '__main__':
    main()
