"""Event planner API client.

This module defines a simple client wrapper around a REST API defined by an
OpenAPI/Swagger specification.  It can parse an ``openapi.json`` file if
available to dynamically discover endpoint paths.  If the specification
file is not present or cannot be parsed, the client falls back to a set
of conventional endpoints for events, registrations, messages and
mailings.  The client uses the ``requests`` library internally to make
HTTP calls.

The client exposes high‑level methods for the operations required by the
Telegram bot:

* :meth:`list_events` – return the available events.
* :meth:`get_event` – fetch a single event by its identifier.
* :meth:`register_for_event` – register the current user for a given event.
* :meth:`cancel_registration` – cancel a previously made registration.
* :meth:`get_messages` – download message templates from the server.
* :meth:`create_mailing` – send a broadcast or mailing.
* :meth:`register_user` – create a new user in the remote system.

Where possible the client inspects the OpenAPI document to determine
paths and HTTP methods.  It looks for operations tagged with
``Events``, ``Registrations``, ``Messages`` or ``Mailings`` (case
insensitive).  If no matching paths are discovered, the client uses
default paths such as ``/events`` and ``/mailings``.  This makes the
client robust against variations in the specification and allows it to
operate even when the specification is unavailable.

The client supports optional authentication via an API key which will
be sent in the ``Authorization`` header.  To enable this behaviour,
initialise the client with ``api_key='<your token>'``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


@dataclass
class ApiEndpoint:
    """Represents a discovered API endpoint.

    Attributes:
        path: The URI template, e.g. ``/events`` or ``/events/{id}``.
        method: The HTTP method in upper case (``GET``, ``POST``, etc.).
        operation_id: Optional identifier for the operation.
    """

    path: str
    method: str
    operation_id: Optional[str] = None


class EventPlannerAPI:
    """Client for interacting with the event planner API.

    The client attempts to load and parse an OpenAPI specification at
    initialisation.  Paths tagged with known categories are stored for
    later use.  The client exposes high‑level methods to access the
    underlying endpoints.
    """

    # Known tags that correspond to the required modules.  These are
    # matched case‑insensitively when scanning the OpenAPI document.
    _KNOWN_TAGS = {
        "events": "events",
        "registrations": "registrations",
        "messages": "messages",
        "mailings": "mailings",
        # Additional tags for optional modules.  These may or may not be
        # present in the OpenAPI specification.  They are included here
        # so that the client can discover endpoints for FAQs, support
        # tickets, feedback and general info.
        "faq": "faq",
        "faqs": "faq",
        "info": "info",
        "feedback": "feedback",
        "support": "support",
        "tickets": "tickets",
        "waitlist": "waitlist",
        "waitinglist": "waitlist",
        "wait": "waitlist",
        "payment": "payment",
        "payments": "payment",
        "pay": "payment",
        "multiregistration": "multiregistration",
        "multi_registration": "multiregistration",
    }

    def __init__(
        self,
        *,
        base_url: str,
        openapi_path: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialise the API client.

        Args:
            base_url: Base URL for the API, e.g. ``https://example.com``.
            openapi_path: Optional path to an OpenAPI JSON file.  If
                provided and readable, endpoints will be inferred from it.
            api_key: Optional API key.  If set, an ``Authorization``
                header with the value ``Bearer <api_key>`` will be
                included in all requests.
            session: Optional requests session.  If not supplied a
                session will be created automatically.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.spec: Dict[str, Any] = {}
        # Mappings from category to endpoints (method + path).  These
        # lists are filled during specification parsing.
        self.endpoints: Dict[str, List[ApiEndpoint]] = {
            tag: [] for tag in self._KNOWN_TAGS.values()
        }
        if openapi_path and os.path.exists(openapi_path):
            try:
                with open(openapi_path, "r", encoding="utf-8") as f:
                    self.spec = json.load(f)
                self._discover_endpoints()
            except Exception as e:
                logger.warning(
                    "Failed to load or parse OpenAPI specification %s: %s. Falling back to defaults.",
                    openapi_path,
                    e,
                )
        # If endpoints were not discovered, ensure that defaults are
        # present so that the client does not raise exceptions when
        # performing operations.  These defaults are based on common
        # conventions used in RESTful APIs.
        self._ensure_default_endpoints()

    # ------------------------------------------------------------------
    # OpenAPI discovery
    # ------------------------------------------------------------------
    def _discover_endpoints(self) -> None:
        """Discover operations from the loaded OpenAPI specification.

        The client scans the ``paths`` section of the OpenAPI document and
        records any operations whose tags match the known categories.  A
        mapping from tag to a list of :class:`ApiEndpoint` objects is
        produced.  If no tags match a category, the corresponding list
        remains empty.
        """
        paths = self.spec.get("paths", {})
        for path, methods in paths.items():
            for method_lower, op in methods.items():
                method = method_lower.upper()
                if not isinstance(op, dict):
                    continue
                tags = [t.lower() for t in op.get("tags", [])]
                operation_id = op.get("operationId")
                for tag in tags:
                    if tag in self._KNOWN_TAGS:
                        category = self._KNOWN_TAGS[tag]
                        self.endpoints[category].append(
                            ApiEndpoint(path=path, method=method, operation_id=operation_id)
                        )

    def _ensure_default_endpoints(self) -> None:
        """Populate default endpoints when none are provided by the specification.

        In the absence of an OpenAPI specification or when it does not
        define a particular category, the client uses sensible defaults.
        These defaults reflect typical REST resource conventions and
        enable basic functionality.
        """
        # Default endpoints for each category.  The client uses the
        # first entry in the list for operations that do not specify an
        # endpoint in the spec.  Each entry contains the method and
        # path.  Additional entries could be appended based on more
        # advanced heuristics.
        defaults: Dict[str, List[Tuple[str, str]]] = {
            "events": [("GET", "/events"), ("GET", "/events/{id}"), ("POST", "/events/{id}/register")],
            "registrations": [("DELETE", "/registrations/{id}"), ("GET", "/registrations/{id}")],
            "messages": [("GET", "/messages")],
            "mailings": [("POST", "/mailings")],
        }
        for category, ep_list in defaults.items():
            if not self.endpoints.get(category):
                self.endpoints[category] = [
                    ApiEndpoint(path=path, method=method) for method, path in ep_list
                ]

    # ------------------------------------------------------------------
    # Low level HTTP helpers
    # ------------------------------------------------------------------
    def _request(
        self, method: str, path: str, *, params: Dict[str, Any] | None = None,
        json_body: Any | None = None
    ) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Perform an HTTP request to the API.

        Args:
            method: HTTP method (``GET``, ``POST``, ``PATCH``, ``DELETE``, etc.).
            path: Path relative to :attr:`base_url` (e.g. ``/events``).
            params: Query parameters to include in the request.
            json_body: JSON body to send with the request (for POST/PATCH).
        Returns:
            A tuple ``(data, error)``. ``data`` contains the parsed JSON
            response on success and ``error`` is ``None``. On failure,
            ``data`` is ``None`` and ``error`` is a dictionary with keys
            ``status_code`` and ``message`` describing the issue.
        """
        url = f"{self.base_url}{path}"
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            logger.debug("Sending %s request to %s", method, url)
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            if response.content:
                return response.json(), None
            return None, None
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            message = ""
            if exc.response is not None:
                try:
                    err_json = exc.response.json()
                    message = err_json.get("detail") or err_json.get("message") or str(err_json)
                except Exception:
                    message = exc.response.text
            if not message:
                message = str(exc)
            logger.error("API request failed (%s): %s", status, message)
            return None, {"status_code": status, "message": message}
        except requests.RequestException as exc:
            logger.error("API request failed: %s", exc)
            return None, {"status_code": None, "message": str(exc)}

    # ------------------------------------------------------------------
    # Event operations
    # ------------------------------------------------------------------
    def list_events(self) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Retrieve all available events.

        Returns:
            A tuple ``(events, error)``. ``events`` contains a list of
            events or is empty on failure.
        """
        ep = self._pick_endpoint("events", method="GET", has_id=False)
        if not ep:
            logger.warning("No endpoint available for listing events")
            return [], {"status_code": None, "message": "No endpoint for listing events"}
        data, error = self._request(ep.method, ep.path)
        if error:
            return [], error
        if isinstance(data, list):
            return data, None
        # Sometimes the API may return the list inside a dictionary.
        if isinstance(data, dict):
            # Attempt to guess the key containing events
            for key in ["events", "data", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key], None
        return [], None

    def get_event(self, event_id: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Retrieve a single event by ID.

        Args:
            event_id: Identifier of the event.
        Returns:
            A tuple ``(event, error)``.
        """
        ep = self._pick_endpoint("events", method="GET", has_id=True)
        if not ep:
            logger.warning("No endpoint available for retrieving an event")
            return None, {"status_code": None, "message": "No endpoint for retrieving event"}
        path = ep.path.replace("{id}", str(event_id))
        data, error = self._request(ep.method, path)
        if error:
            return None, error
        return data, None

    def register_for_event(self, event_id: Any, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Register for an event.

        Args:
            event_id: Identifier of the event to register for.
            payload: Data to send in the request body (e.g. user details).
        Returns:
            A tuple ``(result, error)``.
        """
        ep = self._pick_endpoint("events", method="POST", has_id=True)
        if not ep:
            logger.warning("No endpoint available for event registration")
            return None, {"status_code": None, "message": "No endpoint for event registration"}
        path = ep.path.replace("{id}", str(event_id))
        data, error = self._request(ep.method, path, json_body=payload)
        if error:
            return None, error
        return data, None

    # ------------------------------------------------------------------
    # Registration operations
    # ------------------------------------------------------------------
    def cancel_registration(self, registration_id: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Cancel (delete) a registration.

        Args:
            registration_id: Identifier of the registration to cancel.
        Returns:
            A tuple ``(success, error)``.
        """
        ep = self._pick_endpoint("registrations", method="DELETE", has_id=True)
        if not ep:
            logger.warning("No endpoint available for cancelling registrations")
            return False, {"status_code": None, "message": "No endpoint for cancelling registrations"}
        path = ep.path.replace("{id}", str(registration_id))
        resp, error = self._request(ep.method, path)
        if error:
            return False, error
        return resp is not None, None

    def register_user(self, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Create a new user registration.

        Args:
            payload: User data to send in the request body (e.g. name, email).
        Returns:
            A tuple ``(user, error)``.
        """
        # Some APIs may expose user registration via a dedicated path
        # separate from event registrations.  Attempt to discover such
        # endpoints tagged as 'registrations' but without an id in the path.
        ep = self._pick_endpoint("registrations", method="POST", has_id=False)
        # Fallback to a conventional /registrations path.
        if not ep:
            ep = ApiEndpoint(path="/registrations", method="POST")
        data, error = self._request(ep.method, ep.path, json_body=payload)
        if error:
            return None, error
        return data, None

    # ------------------------------------------------------------------
    # Extended registration operations
    # ------------------------------------------------------------------
    def register_multiple(self, event_id: Any, participants: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Register multiple participants for an event.

        Args:
            event_id: Identifier of the event.
            participants: A list of participant data dictionaries.  The
                exact schema is determined by the API (e.g. each
                dictionary may contain names, emails or telegram ids).
        Returns:
            A tuple ``(result, error)``.
        """
        # Discover a multi‑registration endpoint if defined
        ep = self._pick_endpoint("multiregistration", method="POST", has_id=True)
        if not ep:
            # Fall back to the regular registration endpoint
            ep = self._pick_endpoint("events", method="POST", has_id=True)
        if not ep:
            logger.warning("No endpoint available for multi registration")
            return None, {"status_code": None, "message": "No endpoint for multi registration"}
        path = ep.path.replace("{id}", str(event_id))
        payload = {"participants": participants}
        data, error = self._request(ep.method, path, json_body=payload)
        if error:
            return None, error
        return data, None

    def join_waitlist(self, event_id: Any, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Join the waiting list for an event.

        Args:
            event_id: Identifier of the event.
            payload: Additional data such as the user's identifier.
        Returns:
            A tuple ``(result, error)``.
        """
        ep = self._pick_endpoint("waitlist", method="POST", has_id=True)
        if not ep:
            # fallback path
            ep = ApiEndpoint(path="/events/{id}/waiting-list", method="POST")
        path = ep.path.replace("{id}", str(event_id))
        data, error = self._request(ep.method, path, json_body=payload)
        if error:
            return None, error
        return data, None

    def initiate_payment(self, registration_id: Any, payload: Dict[str, Any] | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Initiate a payment for a registration.

        Args:
            registration_id: Identifier of the registration.
            payload: Optional additional data (e.g. payment method).
        Returns:
            A tuple ``(result, error)`` where ``result`` may include a payment URL or instructions.
        """
        ep = self._pick_endpoint("payment", method="POST", has_id=True)
        if not ep:
            ep = ApiEndpoint(path="/registrations/{id}/pay", method="POST")
        path = ep.path.replace("{id}", str(registration_id))
        data, error = self._request(ep.method, path, json_body=payload or {})
        if error:
            return None, error
        return data, None

    # ------------------------------------------------------------------
    # FAQ / Information operations
    # ------------------------------------------------------------------
    def get_faq(self) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Retrieve frequently asked questions from the server.

        The client attempts to discover an endpoint tagged as ``info`` or
        ``faq`` in the OpenAPI specification.  If none is found it
        falls back to conventional paths such as ``/faq`` or ``/info``.

        Returns:
            A tuple ``(faq_list, error)``.
        """
        last_error: Optional[Dict[str, Any]] = None
        # Discover endpoints with tags matching 'faq' or 'info'.
        for tag_key in ("faq", "info"):
            category = self._KNOWN_TAGS.get(tag_key)
            if category and self.endpoints.get(category):
                for ep in self.endpoints[category]:
                    if ep.method == "GET" and "{" not in ep.path:
                        data, error = self._request(ep.method, ep.path)
                        if error:
                            last_error = error
                            continue
                        if isinstance(data, list):
                            return data, None
                        if isinstance(data, dict):
                            # Attempt to extract list from known keys
                            for key in ["faq", "faqs", "items", "data"]:
                                if key in data and isinstance(data[key], list):
                                    return data[key], None
        # Fall back to default paths
        for path in ("/faq", "/faqs", "/info"):
            data, error = self._request("GET", path)
            if error:
                last_error = error
                continue
            if isinstance(data, list):
                return data, None
            if isinstance(data, dict):
                for key in ["faq", "faqs", "items", "data"]:
                    if key in data and isinstance(data[key], list):
                        return data[key], None
        return [], last_error

    # ------------------------------------------------------------------
    # User registration/booking retrieval
    # ------------------------------------------------------------------
    def get_user_registrations(self, telegram_id: Any) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Retrieve all registrations for a given user.

        Args:
            telegram_id: The user's Telegram identifier used as a key in the API.
        Returns:
            A tuple ``(registrations, error)``.
        """
        last_error: Optional[Dict[str, Any]] = None
        # Attempt to discover a path tagged as 'registrations' that includes a user id
        for ep in self.endpoints.get("registrations", []):
            if ep.method == "GET" and "{id}" in ep.path:
                path = ep.path.replace("{id}", str(telegram_id))
                data, error = self._request(ep.method, path)
                if error:
                    last_error = error
                    continue
                if isinstance(data, list):
                    return data, None
                if isinstance(data, dict):
                    for key in ["registrations", "data", "items"]:
                        if key in data and isinstance(data[key], list):
                            return data[key], None
        # Fallback to /users/{id}/registrations
        path = f"/users/{telegram_id}/registrations"
        data, error = self._request("GET", path)
        if error:
            last_error = error
        if isinstance(data, list):
            return data, None
        if isinstance(data, dict):
            for key in ["registrations", "data", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key], None
        return [], last_error

    # ------------------------------------------------------------------
    # Support and feedback operations
    # ------------------------------------------------------------------
    def create_support_message(self, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Send a support request to the server.

        Args:
            payload: A dictionary containing support request details such as
                user identifier and message text.
        Returns:
            A tuple ``(result, error)``.
        """
        # Look for a path tagged 'support' or 'tickets'
        last_error: Optional[Dict[str, Any]] = None
        for tag in ("support", "ticket", "tickets"):
            category = self._KNOWN_TAGS.get(tag)
            if category and self.endpoints.get(category):
                for ep in self.endpoints[category]:
                    if ep.method == "POST" and "{" not in ep.path:
                        data, error = self._request(ep.method, ep.path, json_body=payload)
                        if error:
                            last_error = error
                            continue
                        return data, None
        # Fallback to /support
        data, error = self._request("POST", "/support", json_body=payload)
        if error:
            return None, error if error else last_error
        return data, None

    def create_feedback(self, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Send user feedback to the server.

        Args:
            payload: A dictionary containing user feedback details (e.g. rating, text).
        Returns:
            A tuple ``(result, error)``.
        """
        # Look for a path tagged 'feedback'
        category = self._KNOWN_TAGS.get("feedback")
        if category and self.endpoints.get(category):
            for ep in self.endpoints[category]:
                if ep.method == "POST" and "{" not in ep.path:
                    data, error = self._request(ep.method, ep.path, json_body=payload)
                    if error:
                        return None, error
                    return data, None
        # Fallback to /feedback
        return self._request("POST", "/feedback", json_body=payload)

    # ------------------------------------------------------------------
    # Messaging operations
    # ------------------------------------------------------------------
    def get_messages(self) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Retrieve all message templates from the server.

        Returns:
            A tuple ``(messages, error)`` where ``messages`` is a dictionary
            mapping identifiers to message contents.
        """
        ep = self._pick_endpoint("messages", method="GET", has_id=False)
        if not ep:
            logger.warning("No endpoint available for messages")
            return {}, {"status_code": None, "message": "No endpoint for messages"}
        data, error = self._request(ep.method, ep.path)
        if error:
            return {}, error
        if isinstance(data, dict):
            return data, None
        return {}, None

    # ------------------------------------------------------------------
    # Mailing operations
    # ------------------------------------------------------------------
    def create_mailing(self, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Send a broadcast/mailing.

        Args:
            payload: The mailing content, including subject, body and
                possibly audience selection.
        Returns:
            A tuple ``(result, error)``.
        """
        ep = self._pick_endpoint("mailings", method="POST", has_id=False)
        if not ep:
            logger.warning("No endpoint available for mailings")
            return None, {"status_code": None, "message": "No endpoint for mailings"}
        data, error = self._request(ep.method, ep.path, json_body=payload)
        if error:
            return None, error
        return data, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pick_endpoint(self, category: str, method: str, *, has_id: bool) -> Optional[ApiEndpoint]:
        """Select an endpoint for a given category and HTTP method.

        The client attempts to choose the most appropriate endpoint for the
        requested operation.  It first searches the discovered
        endpoints in the order they appeared in the specification.  If
        none match the given method and path requirements, it returns
        ``None``.

        Args:
            category: One of ``'events'``, ``'registrations'``,
                ``'messages'`` or ``'mailings'``.
            method: The desired HTTP method (case insensitive).
            has_id: Whether the endpoint should include a ``{id}``
                placeholder in its path.
        Returns:
            An :class:`ApiEndpoint` instance or ``None``.
        """
        method_upper = method.upper()
        for ep in self.endpoints.get(category, []):
            if ep.method != method_upper:
                continue
            # Check for presence of {id} in the path based on has_id flag.
            id_in_path = "{id}" in ep.path
            if has_id == id_in_path:
                return ep
        return None
