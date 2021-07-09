
import import_declare_test

from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    MultipleModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging

util.remove_http_proxy_env_vars()


fields_logging = [
    field.RestField(
        'loglevel',
        required=False,
        encrypted=False,
        default='INFO',
        validator=None
    )
]
model_logging = RestModel(fields_logging, name='logging')


fields_advanced_configuration = [
    field.RestField(
        'python_bin_path',
        required=True,
        encrypted=False,
        default='/usr/bin/python3',
        validator=None
    ), 
    field.RestField(
        'mqclient_bin_path',
        required=True,
        encrypted=False,
        default='/opt/mqm',
        validator=None
    ), 
    field.RestField(
        'mqpassthrough',
        required=True,
        encrypted=False,
        default='disabled',
        validator=None
    )
]
model_advanced_configuration = RestModel(fields_advanced_configuration, name='advanced_configuration')


endpoint = MultipleModel(
    'ta_dhl_mq_settings',
    models=[
        model_logging, 
        model_advanced_configuration
    ],
)


if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
