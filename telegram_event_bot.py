"""A simple Telegram bot for the event planner service.

This module implements a Telegram bot without relying on external
dependencies like ``python-telegram-bot``.  It communicates directly
with Telegram's HTTP API using the ``requests`` library and performs
long polling to receive updates.  The bot integrates with the
:class:`event_planner_api.EventPlannerAPI` client to provide rich
functionality:

* List upcoming events and their identifiers.
* Allow users to register for events via a slash command.
* Allow users to cancel registrations.
* Broadcast messages (for administrators only).
* Fetch and cache message templates from the API to minimise
  round‑trips.
* Register users in the backend when they invoke ``/start``.
* Forward all unrecognised messages to an administrator for manual
  handling.

The bot expects a small set of environment variables to be defined:

``TELEGRAM_BOT_TOKEN``
    The token assigned by BotFather for your bot.  Required.

``EVENT_PLANNER_BASE_URL``
    Base URL of the event planner API.  Required.

``EVENT_PLANNER_API_KEY``
    Optional API key for authenticating with the event planner API.

``ADMIN_CHAT_ID``
    A numeric chat identifier for the administrator.  If set, the bot
    will forward all unsolicited user messages to this chat.  If
    omitted no forwarding is performed.

``OPENAPI_SPEC_PATH``
    Optional path to the OpenAPI specification file on disk.  If
    provided, the :class:`EventPlannerAPI` will use it to discover
    endpoints dynamically.

The bot runs in a simple loop and can be terminated with Ctrl+C.  It
logs informational messages to the console.  Because the polling
loop is blocking, it is advisable to run the bot as a dedicated
process or inside a container.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import random
from typing import Any, Dict, Optional

import requests

from event_planner_api import EventPlannerAPI


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class TelegramEventBot:
    """Implementation of a Telegram bot that talks to an event planner API."""

    def __init__(self) -> None:
        # Validate required environment variables
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
        self.base_url = os.getenv("EVENT_PLANNER_BASE_URL")
        if not self.base_url:
            raise RuntimeError("Missing EVENT_PLANNER_BASE_URL environment variable")
        self.api_key = os.getenv("EVENT_PLANNER_API_KEY") or None
        self.admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        # If admin_chat_id is provided convert to int when possible
        if self.admin_chat_id:
            try:
                self.admin_chat_id = int(self.admin_chat_id)
            except ValueError:
                logger.warning(
                    "ADMIN_CHAT_ID environment variable should be a numeric Telegram chat identifier."
                )
        openapi_path = "/openapi.json"
        self.api = EventPlannerAPI(
            base_url=self.base_url,
            openapi_path=openapi_path,
            api_key=self.api_key,
        )
        # Telegram API endpoint
        self.telegram_api_url = f"https://api.telegram.org/bot{self.bot_token}"
        # Keep track of the last processed update to avoid repeated processing
        self.last_update_id = 0
        # Cache for message templates retrieved from the API
        self.message_cache: Dict[str, Any] = {}
        # Map Telegram user IDs to backend user objects (if returned by the API)
        self.user_registry: Dict[int, Dict[str, Any]] = {}
        # Track per‑user state for multi‑step interactions such as support
        # messages or feedback.  Possible values include 'awaiting_support'
        # and 'awaiting_feedback'.  Absence of a key means the user is
        # currently not engaged in a multi‑step operation.
        # For complex multi‑step flows we store either a simple string or a
        # dictionary with metadata.  If the value is a string, it denotes
        # a simple state such as 'awaiting_support' or 'awaiting_feedback'.
        # If the value is a dict, keys may include 'state', 'event_id',
        # 'count' and 'names' for collecting additional participant names.
        self.user_states: Dict[int, Any] = {}
        # Initialise menu_labels as None; it will be built lazily in
        # ``_send_main_menu`` using the current message cache.  This
        # avoids loading messages prematurely during initialisation.
        self.menu_labels: Optional[Dict[str, str]] = None
        # Counter for consecutive request failures to implement
        # exponential backoff between retries
        self.retry_attempts = 0

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------
    def _reset_backoff(self) -> None:
        """Reset the retry attempt counter after a successful request."""
        self.retry_attempts = 0

    def _sleep_backoff(self, resp: Optional[requests.Response] = None) -> None:
        """Sleep for an exponentially increasing interval with jitter.

        If a ``Retry-After`` header is present on a 429 response it is
        respected.  Otherwise the delay doubles with each attempt up to a
        ceiling of 60 seconds and a random jitter is added to avoid
        thundering herds.
        """
        self.retry_attempts += 1
        delay = None
        if resp is not None and resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except ValueError:
                    pass
        if delay is None:
            delay = min(2 ** (self.retry_attempts - 1), 60) + random.random()
        logger.warning(
            "Request failure #%d, sleeping %.1fs before retry", self.retry_attempts, delay
        )
        time.sleep(delay)

    def _telegram_request(
        self,
        http_method: str,
        method: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """Perform a request against the Telegram API with retries."""
        url = f"{self.telegram_api_url}/{method}"
        while True:
            try:
                resp = requests.request(
                    http_method,
                    url,
                    params=params,
                    json=payload,
                    timeout=timeout,
                )
                if resp.status_code == 429:
                    self._sleep_backoff(resp)
                    continue
                resp.raise_for_status()
                self._reset_backoff()
                try:
                    return resp.json()
                except ValueError:
                    return None
            except requests.RequestException as exc:
                resp = getattr(exc, "response", None)
                logger.error("Telegram %s error: %s", method, exc)
                self._sleep_backoff(resp)
    def _get_updates(self, timeout: int = 30) -> list[Dict[str, Any]]:
        """Request new updates from Telegram.

        Args:
            timeout: Long polling timeout in seconds.
        Returns:
            A list of update objects.  If the call fails an empty list
            is returned.
        """
        params = {
            "timeout": timeout,
            "offset": self.last_update_id + 1,
        }
        data = self._telegram_request(
            "get", "getUpdates", params=params, timeout=timeout + 5
        )
        if isinstance(data, dict) and data.get("ok"):
            return data.get("result", [])
        if data:
            logger.error("Telegram getUpdates failed: %s", data)
        return []

    def _send_message(self, chat_id: int, text: str, *, parse_mode: Optional[str] = None) -> None:
        """Send a plain text message to a Telegram chat.

        Args:
            chat_id: The target chat ID.
            text: The message content.
            parse_mode: Optional Telegram parse mode (e.g. 'Markdown').
        """
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        data = self._telegram_request("post", "sendMessage", payload=payload)
        if data and not data.get("ok"):
            logger.error("Telegram sendMessage failed: %s", data)

    def _forward_message(self, chat_id: int, from_chat_id: int, message_id: int) -> None:
        """Forward a message to another chat.

        Args:
            chat_id: Target chat ID where the message will be forwarded.
            from_chat_id: Original chat ID of the message.
            message_id: Identifier of the original message.
        """
        payload = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }
        data = self._telegram_request("post", "forwardMessage", payload=payload)
        if data and not data.get("ok"):
            logger.error("Telegram forwardMessage failed: %s", data)

    # ------------------------------------------------------------------
    # Message caching
    # ------------------------------------------------------------------
    def _load_messages(self) -> None:
        """Populate the internal message cache from the API.

        If messages are already cached this method returns immediately.  In
        a running bot the administrator can refresh the cache via the
        ``/messages_refresh`` command.
        """
        if self.message_cache:
            return
        logger.info("Loading message templates from API...")
        messages = self.api.get_messages()
        if messages:
            self.message_cache = messages
            logger.info("Loaded %d message templates", len(messages))
        else:
            logger.warning("Failed to load message templates or none available")

    def _get_message(self, key: str, default: Optional[str] = None) -> str:
        """Retrieve a message template by key with optional fallback.

        Args:
            key: Identifier of the message.
            default: Fallback message if the key is missing.
        Returns:
            The message text or the fallback if not found.
        """
        # Ensure messages are loaded at least once
        if not self.message_cache:
            self._load_messages()
        return str(self.message_cache.get(key, default or key))

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def _handle_start(self, chat_id: int, user: Dict[str, Any]) -> None:
        """Handle the /start command.

        Registers the user in the backend if not already registered and
        sends a welcome message.
        """
        user_id = user.get("id")
        # Register user if not already registered in local registry
        if user_id not in self.user_registry:
            payload = {
                "telegram_id": user_id,
                "username": user.get("username"),
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
            }
            backend_user = self.api.register_user(payload)
            if backend_user:
                self.user_registry[user_id] = backend_user
                logger.info("Registered new user %s", user_id)
            else:
                logger.warning("Failed to register user %s via API", user_id)
        welcome_msg = self._get_message(
            "welcome",
            default=(
                "👋 Welcome to the Event Planner Bot!\n"
                "Use /events to see upcoming events or /help to view available commands."
            ),
        )
        self._send_message(chat_id, welcome_msg)
        # Present the main menu after welcoming the user
        self._send_main_menu(chat_id)

    def _handle_help(self, chat_id: int) -> None:
        """Send a help message describing available commands."""
        help_text = (
            "You can use the on‑screen menu to navigate the bot's features. "
            "If you prefer commands, the following are available:\n"
            "/start – Register yourself with the event system and open the main menu.\n"
            "/events – List all available events (equivalent to the menu option).\n"
            "/register <event_id> – Register for an event (use menu buttons for convenience).\n"
            "/cancel <registration_id> – Cancel a registration.\n"
            "/help – Display this help message."
        )
        # Only advertise admin commands to the admin
        if self.admin_chat_id and chat_id == self.admin_chat_id:
            help_text += (
                "\nAdmin commands:\n"
                "/broadcast <message> – Send a broadcast to all users via the API.\n"
                "/messages_refresh – Reload message templates from the API."
            )
        self._send_message(chat_id, help_text)

    def _handle_events(self, chat_id: int) -> None:
        """Retrieve and display a list of events."""
        events = self.api.list_events()
        if not events:
            text = self._get_message(
                "no_events", default="There are no upcoming events at the moment."
            )
            self._send_message(chat_id, text)
            return
        lines = [self._get_message("events_header", default="Upcoming events:")]
        for event in events:
            # Attempt to extract id, name and date fields from the event
            event_id = event.get("id") or event.get("event_id") or event.get("uuid")
            name = event.get("name") or event.get("title") or "(unnamed event)"
            date = event.get("date") or event.get("start_date") or event.get("startDate")
            line = f"ID {event_id}: {name}"
            if date:
                line += f" on {date}"
            lines.append(line)
        lines.append(
            self._get_message(
                "events_footer",
                default="\nTo register for an event send /register <event_id>.",
            )
        )
        self._send_message(chat_id, "\n".join(lines))

    def _handle_register(self, chat_id: int, args: str, user_id: int) -> None:
        """Register the user for the specified event.

        Args:
            chat_id: The chat where the command originated.
            args: Arguments following the command (expected event ID).
            user_id: Telegram ID of the user.
        """
        event_id = args.strip()
        if not event_id:
            self._send_message(chat_id, "Usage: /register <event_id>")
            return
        payload = {"telegram_id": user_id}
        result = self.api.register_for_event(event_id, payload)
        if result is not None:
            text = self._get_message(
                "registration_success",
                default=f"✅ You have been registered for event {event_id}.",
            )
        else:
            text = self._get_message(
                "registration_failure",
                default=f"❌ Failed to register for event {event_id}. Please try again later.",
            )
        self._send_message(chat_id, text)

    def _handle_cancel(self, chat_id: int, args: str) -> None:
        """Cancel an existing registration.

        Args:
            chat_id: The chat where the command originated.
            args: Arguments following the command (expected registration ID).
        """
        registration_id = args.strip()
        if not registration_id:
            self._send_message(chat_id, "Usage: /cancel <registration_id>")
            return
        ok = self.api.cancel_registration(registration_id)
        if ok:
            text = self._get_message(
                "cancellation_success",
                default=f"✅ Registration {registration_id} has been cancelled.",
            )
        else:
            text = self._get_message(
                "cancellation_failure",
                default=f"❌ Failed to cancel registration {registration_id}.",
            )
        self._send_message(chat_id, text)

    def _handle_broadcast(self, chat_id: int, args: str) -> None:
        """Send a broadcast message via the mailing endpoint.

        Only the administrator is allowed to invoke this command.
        """
        if not args.strip():
            self._send_message(chat_id, "Usage: /broadcast <message>")
            return
        payload = {
            "subject": "Broadcast",  # Could be customised
            "body": args.strip(),
        }
        result = self.api.create_mailing(payload)
        if result is not None:
            self._send_message(chat_id, "📢 Broadcast sent successfully.")
        else:
            self._send_message(chat_id, "❌ Failed to send broadcast.")

    def _handle_messages_refresh(self, chat_id: int) -> None:
        """Reload the message templates from the API."""
        self.message_cache.clear()
        self._load_messages()
        self._send_message(chat_id, "🔄 Message templates refreshed.")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _send_main_menu(self, chat_id: int) -> None:
        """Send the main menu to the user with a reply keyboard."""
        # Compute menu labels on demand to ensure they reflect the
        # current message cache.  Use fallbacks if keys are missing.
        if not self.menu_labels:
            self.menu_labels = {
                "events": self._get_message("menu_events", default="Events"),
                "faq": self._get_message("menu_faq", default="FAQ"),
                "bookings": self._get_message("menu_bookings", default="My bookings"),
                "support": self._get_message("menu_support", default="Support"),
                "feedback": self._get_message("menu_feedback", default="Feedback"),
            }
        # Build keyboard layout.  Each inner list represents a row.
        keyboard = [
            [
                {"text": self.menu_labels.get("events", "Events")},
                {"text": self.menu_labels.get("faq", "FAQ")},
            ],
            [
                {"text": self.menu_labels.get("bookings", "My bookings")},
                {"text": self.menu_labels.get("support", "Support")},
            ],
            [
                {"text": self.menu_labels.get("feedback", "Feedback")},
            ],
        ]
        reply_markup = {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }
        # Send menu as separate message to avoid interfering with previous text
        self._send_message(chat_id, self._get_message("menu_prompt", default="Please choose an option:"))
        payload = {
            "chat_id": chat_id,
            "text": "",
            "reply_markup": reply_markup,
        }
        self._telegram_request("post", "sendMessage", payload=payload)

    # ------------------------------------------------------------------
    # Update dispatcher
    # ------------------------------------------------------------------
    def _dispatch_update(self, update: Dict[str, Any]) -> None:
        """Process a single update from Telegram."""
        # Handle callback queries (not used presently)
        if "callback_query" in update:
            callback = update["callback_query"]
            data = callback.get("data") or ""
            callback_id = callback.get("id")
            user_id = (callback.get("from") or {}).get("id")
            message_obj = callback.get("message") or {}
            chat_id_cb = (message_obj.get("chat") or {}).get("id")
            # Handle registration initiation: ask for participant count
            if data.startswith("register:") and user_id and chat_id_cb:
                event_id = data.split(":", 1)[1]
                # Save state to identify event for subsequent count selection
                self.user_states[user_id] = f"select_count:{event_id}"
                # Present number of participants options (1–5)
                self._prompt_participant_count(chat_id_cb, event_id)
                self._answer_callback_query(callback_id)
                return
            # Handle number selection callback for registration
            if data.startswith("regcount:") and user_id and chat_id_cb:
                # Format: regcount:<event_id>:<count>
                parts = data.split(":")
                if len(parts) == 3:
                    _, event_id, count_str = parts
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 1
                    # If only one participant, perform registration immediately
                    if count <= 1:
                        self._process_multi_registration(chat_id_cb, user_id, event_id, 1)
                    else:
                        # Set up state for collecting names of additional participants
                        # We store event_id, total count and an empty list of names
                        self.user_states[user_id] = {
                            "state": "collecting_names",
                            "event_id": event_id,
                            "count": count,
                            "names": [],
                        }
                        # Prompt for the first additional participant's name
                        self._prompt_next_participant_name(chat_id_cb, user_id)
                self._answer_callback_query(callback_id)
                return
            # Handle cancellation via callback
            if data.startswith("cancelReg:") and chat_id_cb:
                reg_id = data.split(":", 1)[1]
                self._handle_cancel_via_callback(chat_id_cb, reg_id)
                self._answer_callback_query(callback_id)
                return
            # Handle payment via callback
            if data.startswith("pay:") and chat_id_cb:
                reg_id = data.split(":", 1)[1]
                self._handle_payment(chat_id_cb, reg_id)
                self._answer_callback_query(callback_id)
                return
            # Handle waitlist join via callback
            if data.startswith("waitlist:") and chat_id_cb and user_id:
                event_id = data.split(":", 1)[1]
                self._handle_join_waitlist(chat_id_cb, user_id, event_id)
                self._answer_callback_query(callback_id)
                return
            # For unhandled callback queries, simply acknowledge them
            self._answer_callback_query(callback_id)
            return
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None:
            return
        from_user = message.get("from") or {}
        text = message.get("text") or ""
        # Update last_update_id for next poll
        if update.get("update_id"):
            self.last_update_id = update["update_id"]
        # Ignore messages from the bot itself
        if from_user.get("is_bot"):
            return
        # Command handling
        if text.startswith("/"):
            parts = text.split(" ", 1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if command == "/start":
                self._handle_start(chat_id, from_user)
            elif command == "/help":
                self._handle_help(chat_id)
            elif command == "/events":
                # Display events using interactive buttons
                self._handle_events_menu(chat_id)
            elif command == "/register":
                self._handle_register(chat_id, args, from_user.get("id"))
            elif command == "/cancel":
                self._handle_cancel(chat_id, args)
            elif command == "/broadcast" and chat_id == self.admin_chat_id:
                self._handle_broadcast(chat_id, args)
            elif command == "/messages_refresh" and chat_id == self.admin_chat_id:
                self._handle_messages_refresh(chat_id)
            elif command == "/menu":
                self._send_main_menu(chat_id)
            else:
                # Unknown command; respond with help
                self._send_message(chat_id, "Unknown command. Use /help to see available commands.")
        else:
            # Handle non‑command messages.  If the user is currently
            # engaged in a multi‑step interaction (support or feedback),
            # process accordingly.
            user_id = from_user.get("id")
            state = self.user_states.get(user_id)
            # Handle support and feedback states stored as simple strings
            if state == "awaiting_support":
                self._process_support(chat_id, from_user, text)
                return
            if state == "awaiting_feedback":
                self._process_feedback(chat_id, from_user, text)
                return
            # Handle multi-registration name collection stored as dict
            if isinstance(state, dict) and state.get("state") == "collecting_names":
                # Append the provided name and either prompt for the next or finalise
                names = state.get("names", [])
                # Append trimmed name
                name = text.strip()
                if name:
                    names.append(name)
                    state["names"] = names
                # Check if we have collected all additional names (count - 1)
                count = state.get("count", 0)
                if len(names) < max(count - 1, 0):
                    # Prompt for next name
                    self.user_states[user_id] = state
                    self._prompt_next_participant_name(chat_id, user_id)
                else:
                    # We have all names; finalise registration
                    self._finalize_multi_registration(chat_id, user_id, from_user)
                return
            # Not in a multi‑step flow.  Check if the message
            # corresponds to one of the menu options.
            # Ensure menu labels are up to date
            if not self.menu_labels:
                self.menu_labels = {
                    "events": self._get_message("menu_events", default="Events"),
                    "faq": self._get_message("menu_faq", default="FAQ"),
                    "bookings": self._get_message("menu_bookings", default="My bookings"),
                    "support": self._get_message("menu_support", default="Support"),
                    "feedback": self._get_message("menu_feedback", default="Feedback"),
                }
            normalized = text.strip().lower()
            label_map = {value.lower(): key for key, value in self.menu_labels.items()}
            if normalized in label_map:
                key = label_map[normalized]
                if key == "events":
                    self._handle_events_menu(chat_id)
                elif key == "faq":
                    self._handle_faq(chat_id)
                elif key == "bookings":
                    self._handle_bookings(chat_id, user_id)
                elif key == "support":
                    self._prompt_support(chat_id, user_id)
                elif key == "feedback":
                    self._prompt_feedback(chat_id, user_id)
                return
            # Otherwise forward to admin if configured
            if self.admin_chat_id and chat_id != self.admin_chat_id:
                sender_name = from_user.get('username') or from_user.get('first_name') or 'unknown'
                forward_prefix = f"📨 Forwarded message from {sender_name}\n"
                self._send_message(self.admin_chat_id, forward_prefix + text)
                self._send_message(chat_id, self._get_message("forwarded_notice", default="Your message has been forwarded to support."))
            else:
                # Generic fallback
                self._send_message(chat_id, self._get_message("unknown_input", default="I'm not sure how to respond to that. Please choose an option from the menu or use /help."))

    def _answer_callback_query(self, callback_id: str) -> None:
        """Acknowledge a callback query to remove the loading state in Telegram clients."""
        if not callback_id:
            return
        payload = {"callback_query_id": callback_id}
        self._telegram_request(
            "post", "answerCallbackQuery", payload=payload, timeout=5
        )

    # ------------------------------------------------------------------
    # High‑level handlers for menu actions
    # ------------------------------------------------------------------
    def _handle_events_menu(self, chat_id: int) -> None:
        """Display events with inline registration buttons."""
        events = self.api.list_events()
        if not events:
            self._send_message(chat_id, self._get_message("no_events", default="There are no upcoming events."))
            return
        # Build inline keyboard: each row contains the event name and a button to register
        inline_keyboard = []
        message_lines = []
        for event in events:
            event_id = event.get("id") or event.get("event_id") or event.get("uuid")
            name = event.get("name") or event.get("title") or "(unnamed)"
            date = event.get("date") or event.get("start_date") or event.get("startDate")
            # Compose a line of text for the event list
            line = f"{name}"
            if date:
                line += f" – {date}"
            message_lines.append(line)
            # Determine if the event is full based on available fields
            is_full = False
            capacity = event.get("capacity") or event.get("max_participants")
            registered = event.get("registered_count") or event.get("participants")
            try:
                if capacity is not None:
                    # registered may be a list or integer
                    if isinstance(registered, list):
                        registered_count = len(registered)
                    else:
                        registered_count = int(registered or 0)
                    if registered_count >= int(capacity):
                        is_full = True
            except Exception:
                pass
            # Add appropriate button(s)
            if event_id:
                if not is_full:
                    inline_keyboard.append([
                        {
                            "text": self._get_message("btn_register", default="Register"),
                            "callback_data": f"register:{event_id}",
                        }
                    ])
                else:
                    inline_keyboard.append([
                        {
                            "text": self._get_message("btn_waitlist", default="Join Waitlist"),
                            "callback_data": f"waitlist:{event_id}",
                        }
                    ])
        # Send event list with inline keyboard
        text = "\n".join(message_lines)
        reply_markup = {"inline_keyboard": inline_keyboard}
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
        }
        self._telegram_request("post", "sendMessage", payload=payload)

    def _handle_faq(self, chat_id: int) -> None:
        """Display the frequently asked questions."""
        faq_entries = self.api.get_faq()
        if not faq_entries:
            self._send_message(chat_id, self._get_message("no_faq", default="No FAQ available at the moment."))
            return
        # Build text listing questions and answers
        lines = []
        for entry in faq_entries:
            question = entry.get("question") or entry.get("title") or entry.get("q") or ""
            answer = entry.get("answer") or entry.get("body") or entry.get("a") or ""
            if question:
                lines.append(f"• {question}")
            if answer:
                lines.append(f"  {answer}\n")
        text = "\n".join(lines)
        self._send_message(chat_id, text)

    def _handle_bookings(self, chat_id: int, user_id: int) -> None:
        """Display the current user's registrations."""
        bookings = self.api.get_user_registrations(user_id)
        if not bookings:
            self._send_message(chat_id, self._get_message("no_bookings", default="You have no active registrations."))
            return
        lines = [self._get_message("bookings_header", default="Your registrations:")]
        inline_keyboard = []
        for reg in bookings:
            event = reg.get("event") or {}
            event_name = event.get("name") or event.get("title") or reg.get("event_name") or "Unknown event"
            reg_id = reg.get("id") or reg.get("registration_id") or reg.get("uuid")
            status = reg.get("status") or ""
            line = f"• {event_name} (ID: {reg_id})"
            if status:
                line += f" – {status}"
            lines.append(line)
            # Add cancel button for each registration
            if reg_id:
                row = [
                    {
                        "text": self._get_message("btn_cancel", default="Cancel"),
                        "callback_data": f"cancelReg:{reg_id}",
                    }
                ]
                # Add pay button if applicable
                price = reg.get("price") or reg.get("total_price")
                paid = reg.get("paid") or reg.get("is_paid")
                if price and not paid:
                    row.append({
                        "text": self._get_message("btn_pay", default="Pay"),
                        "callback_data": f"pay:{reg_id}",
                    })
                inline_keyboard.append(row)
        # Send message with inline buttons below
        payload = {
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "reply_markup": {"inline_keyboard": inline_keyboard} if inline_keyboard else None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        self._telegram_request("post", "sendMessage", payload=payload)

    def _prompt_support(self, chat_id: int, user_id: int) -> None:
        """Prompt the user to enter their support message."""
        self.user_states[user_id] = "awaiting_support"
        self._send_message(chat_id, self._get_message("prompt_support", default="Please describe your issue and we will get back to you:"))

    def _process_support(self, chat_id: int, from_user: Dict[str, Any], text: str) -> None:
        """Handle the user's support message and forward to admin/API."""
        user_id = from_user.get("id")
        # Send to backend API if available
        payload = {
            "telegram_id": user_id,
            "message": text,
        }
        result = self.api.create_support_message(payload)
        # Forward to admin chat if configured
        if self.admin_chat_id and chat_id != self.admin_chat_id:
            sender_name = from_user.get('username') or from_user.get('first_name') or 'unknown'
            forward_text = f"📩 Support request from {sender_name}:\n{text}"
            self._send_message(self.admin_chat_id, forward_text)
        # Send acknowledgement to user
        if result is not None:
            ack = self._get_message("support_ack", default="Your request has been received. Our team will respond shortly.")
        else:
            ack = self._get_message("support_fail", default="There was an issue submitting your request. Please try again later.")
        self._send_message(chat_id, ack)
        # Clear state
        self.user_states.pop(user_id, None)

    def _prompt_feedback(self, chat_id: int, user_id: int) -> None:
        """Prompt the user to enter feedback."""
        self.user_states[user_id] = "awaiting_feedback"
        self._send_message(chat_id, self._get_message("prompt_feedback", default="Please send us your feedback:"))

    def _process_feedback(self, chat_id: int, from_user: Dict[str, Any], text: str) -> None:
        """Handle the user's feedback submission."""
        user_id = from_user.get("id")
        payload = {
            "telegram_id": user_id,
            "feedback": text,
        }
        result = self.api.create_feedback(payload)
        if result is not None:
            ack = self._get_message("feedback_ack", default="Thank you for your feedback!")
        else:
            ack = self._get_message("feedback_fail", default="Failed to submit feedback. Please try again later.")
        self._send_message(chat_id, ack)
        self.user_states.pop(user_id, None)

    # ------------------------------------------------------------------
    # Additional interaction helpers for advanced features
    # ------------------------------------------------------------------
    def _prompt_participant_count(self, chat_id: int, event_id: Any) -> None:
        """Prompt the user to select the number of participants for an event."""
        # Build inline keyboard with numbers 1–5
        inline_keyboard = []
        max_count = 5
        row = []
        for i in range(1, max_count + 1):
            row.append({"text": str(i), "callback_data": f"regcount:{event_id}:{i}"})
            # Arrange buttons in rows of 5
            if len(row) == 5:
                inline_keyboard.append(row)
                row = []
        if row:
            inline_keyboard.append(row)
        payload = {
            "chat_id": chat_id,
            "text": self._get_message("select_count", default="How many participants would you like to register?"),
            "reply_markup": {"inline_keyboard": inline_keyboard},
        }
        self._telegram_request("post", "sendMessage", payload=payload)

    # ------------------------------------------------------------------
    # Multi‑registration name collection helpers
    # ------------------------------------------------------------------
    def _prompt_next_participant_name(self, chat_id: int, user_id: int) -> None:
        """Prompt the user for the next participant's name when registering multiple people.

        The method consults the user_states dictionary to determine which
        participant number is being requested and sends a message asking
        for the person's name.  If the state is not set up correctly
        nothing happens.
        """
        state = self.user_states.get(user_id)
        if not isinstance(state, dict):
            return
        count = state.get("count")
        names = state.get("names", [])
        # Index starts at 0 for the requesting user; ask for additional names
        next_index = len(names) + 2  # Participant numbers start at 2 for the second person
        if count and next_index <= count:
            prompt = self._get_message(
                "prompt_participant_name",
                default=f"Please enter the name of participant {next_index}:",
            )
            self._send_message(chat_id, prompt)

    def _finalize_multi_registration(self, chat_id: int, user_id: int, from_user: Dict[str, Any]) -> None:
        """Complete a multi‑registration by registering or waitlisting participants.

        Once all names have been collected, this method retrieves the
        event ID and participant count from the user state, fetches
        event details to determine available seats, and then
        individually registers participants or adds them to the waitlist.
        Finally it sends a summary to the user and clears the state.
        """
        state = self.user_states.get(user_id)
        if not isinstance(state, dict):
            return
        event_id = state.get("event_id")
        count = state.get("count", 0)
        names: list[str] = state.get("names", [])
        # Build full list of participants including the requesting user
        participants_info: list[tuple[str, Dict[str, Any]]] = []
        # first participant is the user; use first_name + last_name or username
        full_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name")
        if last_name:
            full_name = f"{full_name} {last_name}"
        if not full_name:
            full_name = from_user.get("username") or str(user_id)
        # Participant tuple: (display_name, payload)
        participants_info.append((full_name, {"telegram_id": user_id, "name": full_name}))
        # Additional participants from collected names
        for name in names:
            participants_info.append((name, {"name": name}))
        # Fetch event details to determine remaining seats
        seats_remaining: Optional[int] = None
        try:
            if hasattr(self.api, "get_event") and event_id is not None:
                event_details = self.api.get_event(event_id)
                if isinstance(event_details, dict):
                    capacity = event_details.get("capacity") or event_details.get("max_participants")
                    registered = event_details.get("registered_count") or event_details.get("participants")
                    if capacity is not None:
                        try:
                            if isinstance(registered, list):
                                reg_count = len(registered)
                            else:
                                reg_count = int(registered or 0)
                            seats_remaining = int(capacity) - reg_count
                        except Exception:
                            seats_remaining = None
        except Exception:
            seats_remaining = None
        # Default seats remaining if not determinable
        if seats_remaining is None:
            seats_remaining = len(participants_info)
        # Register participants until seats run out; remaining go to waitlist
        registered_names: list[str] = []
        waitlisted_names: list[str] = []
        for display_name, payload in participants_info:
            if seats_remaining > 0:
                result = self.api.register_for_event(event_id, payload)
                if result is not None:
                    registered_names.append(display_name)
                    seats_remaining -= 1
                else:
                    # If registration fails, fall back to waitlist
                    wl_result = self.api.join_waitlist(event_id, payload)
                    if wl_result is not None:
                        waitlisted_names.append(display_name)
            else:
                wl_result = self.api.join_waitlist(event_id, payload)
                if wl_result is not None:
                    waitlisted_names.append(display_name)
        # Compose summary message
        summary_lines = []
        if registered_names:
            registered_list = ", ".join(registered_names)
            summary_lines.append(
                self._get_message(
                    "multi_reg_success",
                    default=f"✅ Registered: {registered_list}.",
                )
            )
        if waitlisted_names:
            waitlisted_list = ", ".join(waitlisted_names)
            summary_lines.append(
                self._get_message(
                    "multi_reg_waitlisted",
                    default=f"⚠️ Added to waitlist: {waitlisted_list}.",
                )
            )
        if not summary_lines:
            summary_lines.append(
                self._get_message(
                    "multi_reg_failure",
                    default="❌ Failed to register participants. Please try again later.",
                )
            )
        self._send_message(chat_id, "\n".join(summary_lines))
        # Clear state
        self.user_states.pop(user_id, None)

    def _process_multi_registration(self, chat_id: int, user_id: int, event_id: Any, count: int) -> None:
        """Handle registration for multiple participants, including payment if required."""
        # Build participants payload: at minimum include the requesting user
        participants = []
        # Include the initiating user as the first participant
        participants.append({"telegram_id": user_id})
        # Add placeholders for additional participants; in a real implementation
        # this would prompt the user for each participant's details.  Here we
        # simply duplicate the requester or send an empty dict as a placeholder.
        for _ in range(count - 1):
            participants.append({})
        # Attempt multi‑registration
        result = None
        if count > 1:
            result = self.api.register_multiple(event_id, participants)
        else:
            result = self.api.register_for_event(event_id, {"telegram_id": user_id})
        if result is not None:
            # Registration succeeded.  Determine whether payment is required by
            # inspecting the returned object.  For example the API might
            # return a field like 'price' or 'is_paid'.
            pay_needed = False
            registration_id = None
            try:
                # Example heuristics: result may be a dict with price or free
                if isinstance(result, dict):
                    registration_id = result.get("id") or result.get("registration_id")
                    price = result.get("price") or result.get("total_price")
                    paid = result.get("paid") or result.get("is_paid")
                    if price and not paid:
                        pay_needed = True
                # If result is a list, take the first entry
                elif isinstance(result, list) and result:
                    reg = result[0]
                    registration_id = reg.get("id") or reg.get("registration_id")
                    price = reg.get("price") or reg.get("total_price")
                    paid = reg.get("paid") or reg.get("is_paid")
                    if price and not paid:
                        pay_needed = True
            except Exception:
                pass
            # Send confirmation
            self._send_message(chat_id, self._get_message("registration_success", default="✅ Registration completed."))
            # If payment required, send pay button
            if pay_needed and registration_id:
                inline_keyboard = [[{
                    "text": self._get_message("btn_pay", default="Pay"),
                    "callback_data": f"pay:{registration_id}",
                }]]
                payload = {
                    "chat_id": chat_id,
                    "text": self._get_message(
                        "payment_required",
                        default="Payment is required for this registration.",
                    ),
                    "reply_markup": {"inline_keyboard": inline_keyboard},
                }
                self._telegram_request("post", "sendMessage", payload=payload)
        else:
            self._send_message(chat_id, self._get_message("registration_failure", default="❌ Failed to register. Please try again later."))
        # Clear state after registration
        self.user_states.pop(user_id, None)

    def _handle_cancel_via_callback(self, chat_id: int, registration_id: Any) -> None:
        """Cancel a registration from an inline button."""
        ok = self.api.cancel_registration(registration_id)
        if ok:
            self._send_message(chat_id, self._get_message("cancellation_success", default="✅ Registration has been cancelled."))
        else:
            self._send_message(chat_id, self._get_message("cancellation_failure", default="❌ Failed to cancel registration."))

    def _handle_payment(self, chat_id: int, registration_id: Any) -> None:
        """Initiate a payment for a registration and return payment instructions."""
        # Call API to start payment.  The API may return a URL or invoice details.
        result = self.api.initiate_payment(registration_id)
        if result is None:
            self._send_message(chat_id, self._get_message("payment_init_fail", default="❌ Could not initiate payment."))
            return
        # Inspect result for a payment link or invoice
        payment_url = None
        invoice = None
        if isinstance(result, dict):
            payment_url = result.get("payment_url") or result.get("url")
            invoice = result.get("invoice")
        # If payment URL is provided, send it as a button
        if payment_url:
            inline_keyboard = [[{
                "text": self._get_message("btn_open_payment", default="Open Payment Page"),
                "url": payment_url,
            }]]
            payload = {
                "chat_id": chat_id,
                "text": self._get_message(
                    "payment_prompt",
                    default="Please complete the payment using the link below.",
                ),
                "reply_markup": {"inline_keyboard": inline_keyboard},
            }
            self._telegram_request("post", "sendMessage", payload=payload)
        elif invoice:
            # If invoice details are provided, include them directly in the message
            message = self._get_message("payment_invoice", default="Please pay according to the invoice below:") + "\n" + str(invoice)
            self._send_message(chat_id, message)
        else:
            # Fallback message
            self._send_message(chat_id, self._get_message("payment_info", default="Payment initiation succeeded. Please follow further instructions sent separately."))

    def _handle_join_waitlist(self, chat_id: int, user_id: int, event_id: Any) -> None:
        """Join the waiting list for a full event."""
        payload = {"telegram_id": user_id}
        result = self.api.join_waitlist(event_id, payload)
        if result is not None:
            self._send_message(chat_id, self._get_message("waitlist_joined", default="You have been added to the waiting list."))
        else:
            self._send_message(chat_id, self._get_message("waitlist_failed", default="Failed to join waiting list. Please try again later."))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the bot and process updates indefinitely."""
        logger.info("Event planner bot is running...")
        # Preload message templates
        self._load_messages()
        try:
            while True:
                updates = self._get_updates(timeout=30)
                for update in updates:
                    self._dispatch_update(update)
                # Sleep briefly to avoid hammering Telegram in case of
                # empty updates; Telegram recommends at least a short pause
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")


def main() -> None:
    try:
        bot = TelegramEventBot()
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)
    bot.run()


if __name__ == "__main__":
    main()