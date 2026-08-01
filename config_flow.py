"""Config flow for EnergyFace Solar Controller integration."""
from __future__ import annotations

import logging
from typing import Any
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnergyFace Solar Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Optional quick connection test
            try:
                session = aiohttp.ClientSession()
                ws_url = f"http://{host}:81/"
                # Simple ping check on port 81/ws connection setup
                async with session.ws_connect(ws_url, timeout=3) as ws:
                    await ws.close()
                await session.close()
            except Exception:
                _LOGGER.warning("Could not connect to EnergyFace at %s:81 during setup test, but creating entry anyway.", host)

            return self.async_create_entry(title=f"EnergyFace ({host})", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
