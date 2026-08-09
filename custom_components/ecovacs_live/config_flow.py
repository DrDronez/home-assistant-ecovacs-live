"""Config flow for ECOVACS Live View."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.exceptions import (
    AuthenticationError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
)
from deebot_client.util import md5

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import async_get_global_device_list

from .const import (
    CONF_ACCOUNT,
    CONF_AUTO_STOP_MINUTES,
    CONF_CLIENT_ID,
    CONF_COUNTRY,
    CONF_LIVE_VIEW_PIN,
    CONF_PASSWORD,
    DEFAULT_AUTO_STOP_MINUTES,
    DEFAULT_COUNTRY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EcovacsLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ECOVACS Live View."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return EcovacsLiveOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._pending_data: dict[str, Any] = {}
        self._authenticator: Authenticator | None = None
        self._rest_config: Any | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            account = str(user_input[CONF_ACCOUNT]).strip()
            password = str(user_input[CONF_PASSWORD])
            country = str(user_input[CONF_COUNTRY]).strip().upper()
            live_view_pin = str(user_input[CONF_LIVE_VIEW_PIN]).strip()

            if len(country) != 2:
                errors["base"] = "invalid_country"
            elif not live_view_pin:
                errors["base"] = "invalid_pin"
            else:
                client_id = md5(str(uuid.uuid4()))
                self._pending_data = {
                    CONF_ACCOUNT: account,
                    CONF_PASSWORD: password,
                    CONF_COUNTRY: country,
                    CONF_LIVE_VIEW_PIN: live_view_pin,
                    CONF_CLIENT_ID: client_id,
                }

                await self.async_set_unique_id(f"{country}:{account.lower()}")
                self._abort_if_unique_id_configured()

                session = async_get_clientsession(self.hass)
                rest_config = create_rest_config(
                    session,
                    device_id=client_id,
                    alpha_2_country=country,
                )
                self._rest_config = rest_config
                self._authenticator = Authenticator(
                    rest_config,
                    account,
                    md5(password),
                )
                try:
                    await self._authenticator.authenticate()
                except DeviceVerificationRequiredError:
                    try:
                        await self._authenticator.request_device_verification_code()
                    except Exception:
                        _LOGGER.exception("Failed to request verification code")
                        errors["base"] = "verification_request_failed"
                    else:
                        return await self.async_step_verify()
                except InvalidAuthenticationError:
                    errors["base"] = "invalid_auth"
                except AuthenticationError:
                    errors["base"] = "auth_error"
                except Exception:
                    _LOGGER.exception("Unexpected ECOVACS login failure")
                    errors["base"] = "cannot_connect"
                else:
                    return await self._finish_setup()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
                    vol.Required(CONF_LIVE_VIEW_PIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_verify(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if self._authenticator is None:
            return self.async_abort(reason="verification_session_lost")

        if user_input is not None:
            code = str(user_input["verification_code"]).strip()
            try:
                await self._authenticator.verify_device(code)
            except InvalidVerificationCodeError:
                errors["base"] = "invalid_verification_code"
            except AuthenticationError:
                errors["base"] = "verification_failed"
            except Exception:
                _LOGGER.exception("Unexpected verification failure")
                errors["base"] = "verification_failed"
            else:
                try:
                    await self._authenticator.authenticate()
                except Exception:
                    _LOGGER.exception("Login retry after verification failed")
                    errors["base"] = "auth_error"
                else:
                    return await self._finish_setup()

        return self.async_show_form(
            step_id="verify",
            data_schema=vol.Schema({vol.Required("verification_code"): str}),
            errors=errors,
            description_placeholders={
                "account": str(self._pending_data.get(CONF_ACCOUNT, ""))
            },
        )

    async def _finish_setup(self) -> FlowResult:
        if self._authenticator is None or self._rest_config is None:
            return self.async_abort(reason="auth_session_lost")

        try:
            credentials = await self._authenticator.authenticate()
            rest_config = self._rest_config
            session = async_get_clientsession(self.hass)
            devices = await async_get_global_device_list(
                session,
                rest_config=rest_config,
                credentials=credentials,
                login_client_id=str(self._pending_data[CONF_CLIENT_ID]),
            )
            if not devices:
                return self.async_abort(reason="device_query_failed")
        except Exception:
            _LOGGER.exception("ECOVACS raw device query failed")
            return self.async_abort(reason="device_query_failed")

        account = str(self._pending_data[CONF_ACCOUNT])
        return self.async_create_entry(
            title=f"ECOVACS Live View ({account})",
            data=dict(self._pending_data),
        )



class EcovacsLiveOptionsFlow(config_entries.OptionsFlow):
    """Handle ECOVACS Live View options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_timeout = int(
            self._config_entry.options.get(
                CONF_AUTO_STOP_MINUTES,
                DEFAULT_AUTO_STOP_MINUTES,
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_STOP_MINUTES,
                        default=current_timeout,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
                }
            ),
        )
