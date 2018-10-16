#!/bin/bash
FROM_ADDR={{errmail_from_addr|quote}}
TO_ADDR={{errmail_to_addr|quote}}

### TODO: Store the username & password somewhere secure instead of in this file

curl -sS \
    --user {{mailgun_smtp_username|quote}}:{{mailgun_smtp_password|quote}} \
    --mail-from "$FROM_ADDR" \
    --mail-rcpt "$TO_ADDR" \
    --ssl-reqd \
    -T- \
    smtps://smtp.mailgun.org:465 <<EOT
To: $TO_ADDR
From: $FROM_ADDR
Subject: Systemd task $1 on $HOSTNAME failed

$(systemctl status --full "$1")
EOT
