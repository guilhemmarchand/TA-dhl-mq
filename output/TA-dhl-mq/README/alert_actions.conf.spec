
[mq_publish_message]
param._cam = <json> Active response parameters.
param.account = <list> Select Queue Manager Account. It's a required parameter.
param.region = <string> Region. It's a required parameter. It's default value is $result.region$.
param.mqchannel = <string> MQ Channel. It's a required parameter.
param.mqqueuedest = <string> Queue name destination. It's a required parameter.
param.mqmsgfield = <string> Message field name. It's a required parameter. It's default value is message.

[mq_publish_message_replay]
param._cam = <json> Active response parameters.
param.key = <string> key. It's a required parameter. It's default value is $result.key$.
param.region = <string> Region. It's a required parameter. It's default value is $result.region$.
param.account = <string> account. It's a required parameter. It's default value is $result.manager$.
param.mqchannel = <string> MQ Channel. It's a required parameter. It's default value is $result.channel$.
param.mqqueuedest = <string> Queue name destination. It's a required parameter. It's default value is $result.queue$.
param.message = <string> Message. It's a required parameter. It's default value is $result.message$.
param.no_max_retry = <string> max number of attempts. It's a required parameter. It's default value is $result.no_max_retry$.
param.no_attempts = <string> current number of attempts. It's a required parameter. It's default value is $result.no_attempts$.
param.ctime = <string> ctime. It's a required parameter. It's default value is $result.ctimes$.
param.mtime = <string> mtime. It's a required parameter. It's default value is $result.mtime$.

