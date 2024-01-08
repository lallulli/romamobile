# coding: utf-8

#
#    Copyright 2024-2024 Luca Allulli
#
#    This file is part of Roma mobile.
#
#    Roma mobile is free software: you can redistribute it
#    and/or modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, version 2.
#
#    Roma mobile is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#    for more details.
#
#    You should have received a copy of the GNU General Public License along with
#    Roma mobile. If not, see http://www.gnu.org/licenses/.
#

import json

from django.views.decorators.csrf import csrf_exempt

from .models import Channel, process_message


@csrf_exempt
def webhook(request, channel_name):
    c = Channel.objects.get(channel_name=channel_name)
    assert request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN') == c.bot_webhook_token
    u = json.loads(request.body)
    m = None
    if 'channel_post' in u:
        m = u['channel_post']
    elif 'edited_channel_post' in u:
        m = u['edited_channel_post']
    if m is not None:
        process_message(m)

    c.last_update_id = max(c.last_update_id, u['update_id'])
    c.save()
