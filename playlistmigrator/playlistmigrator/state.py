import os
import json
import time
import logging

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_file='state.json'):
        self.state_file = state_file
        self.state = self.load()

    def load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'current_csv': None,
            'current_row': 0,
            'completed_csvs': [],
            'playlist_mapping': {}
        }

    def save(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=4)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        self.state[key] = value

class RateLimiter:
    def __init__(self, track_sleep=0.1):
        self.track_sleep = track_sleep

    def apply_sleep(self):
        if self.track_sleep > 0:
            time.sleep(self.track_sleep)

    def reset(self):
        # We don't have hard daily limits anymore, so reset is empty, but kept for compatibility
        pass
