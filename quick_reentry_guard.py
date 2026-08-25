"""Persistent research-only guard for ATLAS quick-trade shadow signals.

The guard prevents the same symbol/direction from being emitted repeatedly while
an existing quick signal is active, and applies a cooldown after a sampled stop
breach. It never changes Production scoring, thresholds, or execution.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

DEFAULT_ACTIVE_TTL_SECONDS = 3 * 3600
DEFAULT_POST_STOP_COOLDOWN_SECONDS = 3 * 3600


class QuickReentryGuard:
    def __init__(self, path, active_ttl_seconds=DEFAULT_ACTIVE_TTL_SECONDS,
                 post_stop_cooldown_seconds=DEFAULT_POST_STOP_COOLDOWN_SECONDS):
        self.path = Path(path)
        self.active_ttl_seconds = int(active_ttl_seconds)
        self.post_stop_cooldown_seconds = int(post_stop_cooldown_seconds)
        self.lock = threading.RLock()
        self.state = self._load()

    def _load(self):
        try:
            if self.path.exists():
                obj = json.loads(self.path.read_text())
                if isinstance(obj, dict):
                    return obj
        except Exception:
            pass
        return {'schema': 'ATLAS_QUICK_REENTRY_GUARD_V1', 'signals': {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True))
        tmp.replace(self.path)

    @staticmethod
    def _key(symbol, direction):
        return f'{str(symbol).upper()}:{str(direction).upper()}'

    @staticmethod
    def _stop_hit(direction, price, stop):
        if direction == 'LONG':
            return price <= stop
        if direction == 'SHORT':
            return price >= stop
        return False

    def inspect(self, symbol, direction, price, now=None):
        now = float(now if now is not None else time.time())
        direction = str(direction or '').upper()
        price = float(price)
        key = self._key(symbol, direction)
        with self.lock:
            rec = (self.state.get('signals') or {}).get(key)
            if not isinstance(rec, dict):
                return {'allow_new': True, 'state': 'CLEAR', 'reason': 'NO_PREVIOUS_SIGNAL'}

            status = str(rec.get('status') or 'ACTIVE').upper()
            stop = rec.get('stop_loss')
            try:
                stop = float(stop)
            except Exception:
                stop = None

            if status == 'ACTIVE':
                if stop is not None and self._stop_hit(direction, price, stop):
                    rec['status'] = 'STOPPED'
                    rec['stop_detected_at'] = now
                    rec['stop_detected_price'] = price
                    self._save()
                    return {
                        'allow_new': False, 'state': 'POST_STOP_COOLDOWN',
                        'reason': 'STOP_BREACH_DETECTED', 'record': dict(rec),
                        'cooldown_remaining_seconds': self.post_stop_cooldown_seconds,
                    }
                age = max(0.0, now - float(rec.get('signal_at') or now))
                if age < self.active_ttl_seconds:
                    return {
                        'allow_new': False, 'state': 'ACTIVE',
                        'reason': 'ACTIVE_SAME_DIRECTION_SIGNAL_NOT_REISSUED',
                        'record': dict(rec),
                        'active_remaining_seconds': max(0, int(self.active_ttl_seconds - age)),
                    }
                rec['status'] = 'EXPIRED'
                rec['expired_at'] = now
                self._save()
                return {'allow_new': True, 'state': 'EXPIRED', 'reason': 'PREVIOUS_SIGNAL_EXPIRED', 'record': dict(rec)}

            if status == 'STOPPED':
                stopped_at = float(rec.get('stop_detected_at') or now)
                age = max(0.0, now - stopped_at)
                if age < self.post_stop_cooldown_seconds:
                    return {
                        'allow_new': False, 'state': 'POST_STOP_COOLDOWN',
                        'reason': 'POST_STOP_REENTRY_COOLDOWN', 'record': dict(rec),
                        'cooldown_remaining_seconds': max(0, int(self.post_stop_cooldown_seconds - age)),
                    }
                rec['status'] = 'COOLDOWN_COMPLETE'
                rec['cooldown_completed_at'] = now
                self._save()
                return {'allow_new': True, 'state': 'COOLDOWN_COMPLETE', 'reason': 'POST_STOP_COOLDOWN_COMPLETE', 'record': dict(rec)}

            return {'allow_new': True, 'state': status, 'reason': 'PREVIOUS_SIGNAL_NOT_ACTIVE', 'record': dict(rec)}

    def register(self, symbol, direction, entry, stop_loss, target, risk_reward=None,
                 confidence=None, score=None, now=None):
        now = float(now if now is not None else time.time())
        direction = str(direction or '').upper()
        key = self._key(symbol, direction)
        rec = {
            'symbol': str(symbol).upper(),
            'direction': direction,
            'status': 'ACTIVE',
            'signal_at': now,
            'entry': float(entry),
            'stop_loss': float(stop_loss),
            'target': float(target),
            'risk_reward': risk_reward,
            'confidence': confidence,
            'score': score,
        }
        with self.lock:
            self.state.setdefault('signals', {})[key] = rec
            self._save()
        return dict(rec)

    def approve_active_policy(self, symbol, direction, policy_version, now=None):
        """Stamp an ACTIVE quick record after the strict horizon policy approves it."""
        now = float(now if now is not None else time.time())
        direction = str(direction or '').upper()
        key = self._key(symbol, direction)
        with self.lock:
            rec = (self.state.get('signals') or {}).get(key)
            if not isinstance(rec, dict) or str(rec.get('status') or '').upper() != 'ACTIVE':
                return {'approved': False, 'reason': 'NO_ACTIVE_SIGNAL'}
            rec['policy_version'] = str(policy_version)
            rec['policy_approved_at'] = now
            self._save()
            return {'approved': True, 'record': dict(rec)}

    def reject_legacy_active(self, symbol, direction, required_policy_version,
                             reason='LEGACY_POLICY_STATE', now=None):
        """Cancel ACTIVE records that predate the required strict horizon policy.

        Newly approved strict Quick records are stamped with policy_version by
        approve_active_policy(). This migration only rejects unversioned or stale
        ACTIVE records; stopped/cooldown history is preserved.
        """
        now = float(now if now is not None else time.time())
        direction = str(direction or '').upper()
        key = self._key(symbol, direction)
        with self.lock:
            rec = (self.state.get('signals') or {}).get(key)
            if not isinstance(rec, dict) or str(rec.get('status') or '').upper() != 'ACTIVE':
                return {'cancelled': False, 'reason': 'NO_ACTIVE_SIGNAL'}
            if str(rec.get('policy_version') or '') == str(required_policy_version):
                return {'cancelled': False, 'reason': 'POLICY_VERSION_CURRENT', 'record': dict(rec)}
            rec['status'] = 'POLICY_REJECTED'
            rec['policy_rejected_at'] = now
            rec['policy_rejection_reason'] = str(reason)
            rec['required_policy_version'] = str(required_policy_version)
            self._save()
            return {'cancelled': True, 'record': dict(rec)}

    def cancel_active(self, symbol, direction, reason='POLICY_REJECTED', now=None):
        """Cancel a just-registered research signal rejected by a stricter policy.

        This is intentionally limited to ACTIVE records. It does not erase stop
        history or cooldown state and never affects Production decisions.
        """
        now = float(now if now is not None else time.time())
        direction = str(direction or '').upper()
        key = self._key(symbol, direction)
        with self.lock:
            rec = (self.state.get('signals') or {}).get(key)
            if not isinstance(rec, dict) or str(rec.get('status') or '').upper() != 'ACTIVE':
                return {'cancelled': False, 'reason': 'NO_ACTIVE_SIGNAL'}
            rec['status'] = 'POLICY_REJECTED'
            rec['policy_rejected_at'] = now
            rec['policy_rejection_reason'] = str(reason)
            self._save()
            return {'cancelled': True, 'record': dict(rec)}
