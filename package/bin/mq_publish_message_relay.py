
# encoding = utf-8
# Always put this line at the beginning of this file
import import_declare_test

import os
import sys

from splunktaucclib.alert_actions_base import ModularAlertBase
import modalert_mq_publish_message_relay_helper

class AlertActionWorkermq_publish_message_relay(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkermq_publish_message_relay, self).__init__(ta_name, alert_name)

    def validate_params(self):

        if not self.get_param("key"):
            self.log_error('key is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("appname"):
            self.log_error('appname is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("region"):
            self.log_error('region is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("account"):
            self.log_error('account is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("mqchannel"):
            self.log_error('mqchannel is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("mqqueuedest"):
            self.log_error('mqqueuedest is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("message"):
            self.log_error('message is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("no_max_retry"):
            self.log_error('no_max_retry is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("no_attempts"):
            self.log_error('no_attempts is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("ctime"):
            self.log_error('ctime is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("mtime"):
            self.log_error('mtime is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("status"):
            self.log_error('status is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("user"):
            self.log_error('user is a mandatory parameter, but its value is None.')
            return False
        return True

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            if not self.validate_params():
                return 3
            status = modalert_mq_publish_message_relay_helper.process_event(self, *args, **kwargs)
        except (AttributeError, TypeError) as ae:
            self.log_error("Error: {}. Please double check spelling and also verify that a compatible version of Splunk_SA_CIM is installed.".format(str(ae)))#ae.message replaced with str(ae)
            return 4
        except Exception as e:
            msg = "Unexpected error: {}."
            if str(e):
                self.log_error(msg.format(str(e)))#e.message replaced with str(ae)
            else:
                import traceback
                self.log_error(msg.format(traceback.format_exc()))
            return 5
        return status

if __name__ == "__main__":
    exitcode = AlertActionWorkermq_publish_message_relay("TA-dhl-mq", "mq_publish_message_relay").run(sys.argv)
    sys.exit(exitcode)
