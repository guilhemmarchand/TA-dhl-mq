
import import_declare_test

from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    SingleModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        'mqmanager',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'mqhost',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'mqport',
        required=False,
        encrypted=False,
        default='1414',
        validator=None
    ), 
    field.RestField(
        'mqssl',
        required=True,
        encrypted=False,
        default='no',
        validator=None
    ), 
    field.RestField(
        'ssl_cipher_spec',
        required=False,
        encrypted=False,
        default='TLS_RSA_WITH_AES_256_CBC_SHA',
        validator=None
    ), 
    field.RestField(
        'key_repo_location',
        required=False,
        encrypted=False,
        default='/var/mqm/ssl-db/client/KeyringClient',
        validator=None
    ), 
    field.RestField(
        'username',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'password',
        required=False,
        encrypted=True,
        default=None,
        validator=None
    ), 
    field.RestField(
        'client_id',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'client_secret',
        required=False,
        encrypted=True,
        default=None,
        validator=None
    ), 
    field.RestField(
        'redirect_url',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'access_token',
        required=False,
        encrypted=True,
        default=None,
        validator=None
    ), 
    field.RestField(
        'refresh_token',
        required=False,
        encrypted=True,
        default=None,
        validator=None
    ), 
    field.RestField(
        'instance_url',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ), 
    field.RestField(
        'auth_type',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    )
]
model = RestModel(fields, name=None)


endpoint = SingleModel(
    'ta_dhl_mq_account',
    model,
    config_name='account'
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
