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


from datetime import datetime

from django.utils import timezone
from django.db import models
import requests
from django.utils.html import linebreaks



class Channel(models.Model):
    channel_name = models.CharField(max_length=127, unique=True)
    bot_name = models.CharField(max_length=127, unique=True)
    bot_username = models.CharField(max_length=127, unique=True)
    bot_api_token = models.CharField(max_length=127, unique=True)
    bot_webhook_token = models.CharField(max_length=127, null=True, blank=True)
    last_update_id = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.channel_name


class Message(models.Model):
    message_id = models.IntegerField(unique=True)
    html = models.TextField()
    ts = models.DateTimeField(default=timezone.now)

    def __unicode__(self):
        return self.html[:200]


def process_message(message):
    if 'text' in message:
        message_id = message['message_id']
        text = linebreaks(message['text'])
        ts = datetime.fromtimestamp(message['date'])
        m, created = Message.objects.get_or_create(
            message_id=message_id,
            defaults={
                'html': text,
                'ts': ts,
            }
        )
        if not created:
            m.html = text
            m.ts = ts
            m.save()


def poll(channel=None):
    if channel is None:
        channel = Channel.objects.all()[0]

    url = 'https://api.telegram.org/bot{}/getUpdates'.format(channel.bot_api_token)
    offset = 0 if not channel.last_update_id else channel.last_update_id + 1

    while True:
        params = {'offset': offset, 'timeout': 10}
        print("Long polling...")
        response = requests.get(url, params=params)
        print(response)
        print(response.json())
        updates = response.json().get('result', [])
        print(updates)

        for u in updates:
            m = None
            if 'channel_post' in u:
                m = u['channel_post']
            elif 'edited_channel_post' in u:
                m = u['edited_channel_post']
            if m is not None:
                process_message(m)

            offset = max(offset, u['update_id'] + 1)

        channel.last_update_id = offset - 1
        channel.save()


def set_webhook(site_prefix, channel=None):
    """
    Set a Telegram webhook

    Make sure that this app urls are bound to /telegram_channel/
    `site_prefix` shall not include a trailing slash
    """
    if channel is None:
        channel = Channel.objects.all()[0]

    webhook_url = "{}/telegram_channel/webhook/{}".format(site_prefix, channel.channel_name)
    url = 'https://api.telegram.org/bot{}/setWebhook'.format(channel.bot_api_token)
    params = {'url': webhook_url, 'secret_token': channel.bot_webhook_token}
    response = requests.get(url, params=params)
    print(response)
