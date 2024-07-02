#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating object storage to a charmed application."""

import logging
from typing import List, Optional

import ops
import ops.charm
import ops.framework
import ops.lib
import ops.main
import ops.model
from charms.data_platform_libs.v0.object_storage import (
    AzureStorageProvides,
    CredentialRequestedEvent,
)
from ops.charm import ActionEvent, ConfigChangedEvent, StartEvent
from ops.model import ActiveStatus, BlockedStatus

from constants import AZURE_MANDATORY_OPTIONS, AZURE_OPTIONS, AZURE_RELATION_NAME

logger = logging.getLogger(__name__)


class ObjectStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for object storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.azure_provider = AzureStorageProvides(self, AZURE_RELATION_NAME)

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        self.framework.observe(self.on.secret_changed, self._on_secret_changed)
        # self.framework.observe(self.on.secret_changed, self._on_secret_removed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.framework.observe(
            self.azure_provider.on.credentials_requested, self._on_azure_credentials_requested
        )

        # actions
        self.framework.observe(
            self.on.get_azure_connection_info_action, self.on_get_connection_info_action
        )

    def get_missing_parameters(self) -> List[str]:
        """Returns the missing mandatory parameters that are not stored in the config."""
        missing_options = []
        for config_option in AZURE_MANDATORY_OPTIONS:
            if not self.config.get(config_option):
                missing_options.append(config_option)
        return missing_options

    def check_and_set_status(self, set_active_if_passed=False) -> bool:
        """Check for missing parameters and set status of the unit.

        If set_active_if_passed is True, the unit status will be set to Active once
        it is found there are no missing parameters.
        """
        missing_options = self.get_missing_parameters()
        if missing_options:
            logger.warning(f"Missing parameters: {missing_options}")
            self.unit.status = BlockedStatus(f"Missing parameters: {missing_options}")
            return
        try:
            self.decode_secret_key(self.config.get("credentials"))
        except Exception as e:
            logger.warning(f"Error in decoding secret: {e}")
            self.unit.status = BlockedStatus(str(e))
            return

        if set_active_if_passed:
            self.unit.status = ActiveStatus()

    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        self.check_and_set_status()

    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        self.check_and_set_status(set_active_if_passed=True)

    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Handle the secret changed event.

        When a secret is changed, it is first checked that whether this particular secret
        is used in the charm's config. If yes, the secret is decoded and relation databag
        is updated.
        """
        secret = event.secret

        if not self.config.get("credentials"):
            return
        if self.config.get("credentials") != secret.id:
            return

        try:
            secret_key = self.decode_secret_key(secret.id)
        except Exception:
            secret_key = ""

        if len(self.azure_provider.relations) > 0:
            for relation in self.azure_provider.relations:
                self.azure_provider.update_relation_data(relation.id, {"secret-key": secret_key})

        self.check_and_set_status(set_active_if_passed=True)

    # def _on_secret_removed(self, event: ops.SecretRemoveEvent):
    #     logger.info(f"Secret {event.secret.id} has been removed.")
    #     secret = event.secret

    #     if not self.config.get("credentials"):
    #         return
    #     if self.config.get("credentials") != secret.id:
    #         return

    #     if len(self.azure_provider.relations) > 0:
    #         for relation in self.azure_provider.relations:
    #             self.azure_provider.update_relation_data(relation.id, {"secret-key": ""})

    #     self.check_and_set_status(set_active_if_passed=True)

    def decode_secret_key(self, secret_id: str) -> Optional[str]:
        """Decode the secret with given secret_id and return the secret-key in plaintext value.

        Args:
            secret_id (str): The ID (URI) of the secret that contains the secret key

        Raises:
            ops.model.SecretNotFoundError: When either the secret does not exist or the secret
                does not have the secret-key in its content.
            ops.model.ModelError: When the permission to access the secret has not been granted
                yet.

        Returns:
            Optional[str]: The secret-key in plain text.
        """
        try:
            secret_content = self.model.get_secret(id=secret_id).get_content(refresh=True)

            if not secret_content.get("secret-key"):
                raise ValueError(
                    f"The field 'secret-key' was not found in the secret '{secret_id}'."
                )
            return secret_content["secret-key"]
        except ops.model.SecretNotFoundError:
            raise ops.model.SecretNotFoundError(f"The secret '{secret_id}' does not exist.")
        except ValueError as ve:
            raise ops.model.SecretNotFoundError(ve)
        except ops.model.ModelError as me:
            if "permission denied" in str(me):
                raise ops.model.ModelError(
                    f"Permission for secret '{secret_id}' has not been granted."
                )
            raise

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Event handler for configuration changed events."""
        # Only execute in the unit leader
        if not self.unit.is_leader():
            return

        logger.debug(f"Config changed... Current configuration: {self.config}")

        # store updates from config and apply them.
        update_config = {}

        # iterate over the option and check for updates
        for option in AZURE_OPTIONS:

            # option possibly removed from the config
            # (e.g. 'juju config --reset <option>' or 'juju config <option>=""')
            if option not in self.config or self.config[option] == "":

                # skip in case of default value
                continue

            if option == "credentials":
                try:
                    secret_key = self.decode_secret_key(self.config.get(option))
                    update_config["secret-key"] = secret_key
                except Exception as e:
                    logger.warning(f"Error in decoding secret: {e}")
                    continue
            else:
                update_config[option] = str(self.config.get(option))

        if len(self.azure_provider.relations) > 0:
            for relation in self.azure_provider.relations:
                self.azure_provider.update_relation_data(relation.id, update_config)

        self.check_and_set_status(set_active_if_passed=True)

    def _on_azure_credentials_requested(self, event: CredentialRequestedEvent):
        """Handle the `credential-requested` event."""
        if not self.unit.is_leader():
            return

        container_name = self.config.get("container")
        assert container_name is not None

        desired_configuration = {}
        # collect all configuration options
        for option in AZURE_OPTIONS:
            if self.config.get(option):
                if option == "credentials":
                    try:
                        secret_key = self.decode_secret_key(self.config.get(option))
                        desired_configuration["secret-key"] = secret_key
                    except Exception as e:
                        logger.warning(f"Error in decoding secret: {e}")
                        continue
                else:
                    desired_configuration[option] = self.config.get(option)

        # update connection parameters in the relation data bag
        self.azure_provider.update_relation_data(event.relation.id, desired_configuration)

    def on_get_connection_info_action(self, event: ActionEvent):
        """Handle the action `get_connection_info`."""
        current_configuration = {}
        for option in AZURE_OPTIONS:
            if self.config.get(option):
                current_configuration[option] = self.config.get(option)

        # emit event fail if no option is set in the charm
        if len(current_configuration) == 0:
            event.fail("Credentials are not set!")
            return

        event.set_results(current_configuration)


if __name__ == "__main__":
    ops.main.main(ObjectStorageIntegratorCharm)
