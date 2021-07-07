#!/bin/bash
PWD=$(pwd)
ucc-gen
cd output/
tar -cvzf TA-dhl-mq.tgz TA-dhl-mq
cd "$PWD"
exit 0
