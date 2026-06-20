"""
instagram_client.py
--------------------
Core Instagram client wrapper built on top of instagrapi.
Handles authentication, session persistence, 2FA/challenge flows,
and exposes a clean API for mcp_server.py to consume.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

from instagrapi import Client
from instagrapi.exceptions import (
    TwoFactorRequired,
    ChallengeRequired,
    LoginRequired,
    UserNotFound,
    MediaNotFound,
    RateLimitError,
    BadPassword,
)

# Log to stderr only — never stdout (would corrupt stdio MCP transport)
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="[instagram_client] %(levelname)s: %(message)s")
logger = logging.getLogger("instagram_client")


class InstagramClientWrapper:
    def __init__(self, session_path: str = "instagram_session.json"):
        self.cl = Client()
        self.cl.delay_range = [1, 3]  # human-like delays between requests
        self.session_path = session_path
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.pending_2fa: bool = False
        self.pending_challenge: bool = False

    # ------------------------------------------------------------------
    # SESSION MANAGEMENT
    # ------------------------------------------------------------------

    def load_session(self) -> bool:
        """Attempts to load a saved session from disk."""
        if os.path.exists(self.session_path):
            try:
                logger.info(f"Loading session from {self.session_path}")
                self.cl.load_settings(self.session_path)
                return True
            except Exception as e:
                logger.error(f"Failed to load session: {e}")
                try:
                    os.remove(self.session_path)
                except Exception:
                    pass
        return False

    def save_session(self):
        """Saves the current session to disk."""
        try:
            self.cl.dump_settings(self.session_path)
            logger.info(f"Session saved to {self.session_path}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def is_logged_in(self) -> bool:
        """Probes Instagram to verify the current session is valid."""
        try:
            if self.cl.user_id:
                self.cl.get_timeline_feed()
                return True
        except Exception:
            pass
        return False

    def init_from_saved_session(self) -> Dict[str, Any]:
        """Try restoring an existing session on startup."""
        if self.load_session():
            if self.is_logged_in():
                self.username = self.cl.username
                return {"status": "success", "message": f"Auto-restored session for @{self.username}"}
        return {"status": "not_logged_in", "message": "No valid saved session found."}

    # ------------------------------------------------------------------
    # LOGIN METHODS
    # ------------------------------------------------------------------

    def login_with_credentials(self, username: str, password: str,
                                verification_code: Optional[str] = None) -> Dict[str, Any]:
        """Login using username + password, with optional 2FA code."""
        self.username = username
        self.password = password
        self.pending_2fa = False
        self.pending_challenge = False

        def challenge_code_handler(uname, choice):
            logger.warning(f"Challenge triggered for {uname} via {choice}")
            self.pending_challenge = True
            raise ChallengeRequired("Challenge code required.")

        self.cl.challenge_code_handler = challenge_code_handler

        try:
            logger.info(f"Logging in as {username}...")
            if verification_code:
                self.cl.login(username, password, verification_code=verification_code)
            else:
                self.cl.login(username, password)

            self.save_session()
            return {"status": "success", "message": f"Logged in as @{username}"}

        except TwoFactorRequired:
            self.pending_2fa = True
            return {
                "status": "needs_2fa",
                "message": "2FA required. Call instagram_complete_2fa with the code from your authenticator app."
            }
        except ChallengeRequired:
            self.pending_challenge = True
            return {
                "status": "needs_challenge",
                "message": "Security challenge triggered. Call instagram_complete_challenge with the code sent to your email/SMS."
            }
        except BadPassword:
            return {"status": "error", "message": "Incorrect password."}
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {"status": "error", "message": str(e)}

    def login_with_sessionid(self, username: str, session_id: str) -> Dict[str, Any]:
        """Login using a browser sessionid cookie — most stable method."""
        self.username = username
        self.pending_2fa = False
        self.pending_challenge = False

        try:
            logger.info(f"Logging in via session ID for @{username}...")
            self.cl.login_by_sessionid(session_id)

            if self.is_logged_in():
                self.username = self.cl.username
                self.save_session()
                return {"status": "success", "message": f"Authenticated as @{self.username} via session ID."}
            else:
                return {"status": "error", "message": "Session ID login verification failed. The session may be expired."}
        except Exception as e:
            logger.error(f"Session ID login error: {e}")
            return {"status": "error", "message": str(e)}

    def complete_2fa(self, code: str) -> Dict[str, Any]:
        """Completes a pending 2FA login."""
        if not self.username or not self.password:
            return {"status": "error", "message": "No pending login. Call login_with_credentials first."}
        return self.login_with_credentials(self.username, self.password, verification_code=code)

    def complete_challenge(self, code: str) -> Dict[str, Any]:
        """Completes a pending security challenge."""
        if not self.username or not self.password:
            return {"status": "error", "message": "No pending login. Call login_with_credentials first."}
        return self.login_with_credentials(self.username, self.password, verification_code=code)

    def logout(self) -> Dict[str, Any]:
        """Logs out and removes saved session."""
        try:
            self.cl.logout()
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
            self.username = None
            self.password = None
            return {"status": "success", "message": "Logged out and session cleared."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_login_status(self) -> Dict[str, Any]:
        logged = self.is_logged_in()
        return {
            "logged_in": logged,
            "username": (self.cl.username if logged else None),
            "user_id": (str(self.cl.user_id) if logged else None)
        }
