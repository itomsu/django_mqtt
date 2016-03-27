from django_mqtt.publisher.signals import *
from django_mqtt.models import *
from django_mqtt.protocol import MQTT_QoS0, MQTT_QoS1, MQTT_QoS2

from datetime import timedelta

from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.conf import settings
from django.db import models

SESSION_TIMEOUT = 5
if hasattr(settings, 'MQTT_SESSION_TIMEOUT'):
    SESSION_TIMEOUT = settings.MQTT_SESSION_TIMEOUT

PROTO_MQTT_QoS = (
    (MQTT_QoS0, _('QoS 0: Delivered at most once')),
    (MQTT_QoS1, _('QoS 1: Always delivered at least once')),
    (MQTT_QoS2, _('QoS 2: Always delivered exactly once')),
)


class Channel(models.Model):
    qos = models.IntegerField(choices=PROTO_MQTT_QoS, default=0)
    topic = models.ForeignKey(Topic)

    class Meta:
        unique_together = ('qos', 'topic')

    def __unicode__(self):
        return unicode('QoS%(qos)s - %(topic)s' % {'qos': self.qos, 'topic': self.topic})

    def __str__(self):
        return str('QoS%(qos)s - %(topic)s' % {'qos': self.qos, 'topic': self.topic})


class Session(models.Model):
    client_id = models.OneToOneField(ClientId)
    user = models.ForeignKey(User, blank=True, null=True)

    active = models.BooleanField(default=True)
    init_conn = models.DateTimeField(auto_now_add=True, editable=False)
    last_conn = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now_add=True)

    keep_alive = models.IntegerField(default=0)

    subscriptions = models.ManyToManyField(Channel)
    unsubscriptions = models.ManyToManyField(Topic)

    def ping(self):
        self.active = True
        self.last_update = timezone.now()
        self.objects.filter(pk=self.pk).update(last_update=self.last_update)
        self.objects.filter(pk=self.pk, active=False).update(active=self.active)

    def is_alive(self):
        if self.active:
            keep_until = self.last_update + timedelta(seconds=self.keep_alive)
            if keep_until > timezone.now():
                self.active = False
                self.objects.filter(pk=self.pk, active=True).update(active=self.active)
        return self.active

    def __unicode__(self):
        return unicode('%(client_id)s - %(user)s' % {'client_id': self.client_id, 'user': self.user})

    def __str__(self):
        return str('%(client_id)s - %(user)s' % {'client_id': self.client_id, 'user': self.user})

    def is4me(self, topic, qos):
        if topic in self.unsubscriptions:
            return False
        acl = ACL.get_acl(topic, PROTO_MQTT_ACC_SUS)
        if acl and not acl.has_permission(self.user):
            return False
        for channel in self.subscriptions.filter(qos__gte=qos):
            if topic in channel.topic:
                return True


class Publication(models.Model):
    channel = models.ForeignKey(Channel)
    remain = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now=True)
    message = models.BinaryField(blank=True, null=True)
    packet_id = models.IntegerField(default=-1)

    class Meta:
        unique_together = ('channel', 'remain')

    def __unicode__(self):
        return unicode('%(date)s: %(channel)s' % {'channel': self.channel, 'date': self.date})

    def __str__(self):
        return str('%(date)s: %(channel)s' % {'channel': self.channel, 'date': self.date})
