from django.db import models
import uuid
from django.utils import timezone
import string
import random

def generate_lobby_code():
    return uuid.uuid4().hex[:6].upper()  # Generates a unique 6-character code

class Lobby(models.Model):
    code = models.CharField(max_length=6, unique=True, default=generate_lobby_code)  # Adjusted max_length to 6
    host_name = models.CharField(max_length=100)
    members = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    host_code = models.TextField(blank=True, default="")
    host_output = models.TextField(blank=True, default='')
    host_lang = models.CharField(max_length=20, default="python")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Lobby {self.code} hosted by {self.host_name}"

class ChatMessage(models.Model):
    lobby = models.ForeignKey(Lobby, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"

class Participant(models.Model):
    lobby = models.ForeignKey('Lobby', on_delete=models.CASCADE, related_name='participants')
    username = models.CharField(max_length=100)
    code = models.TextField(blank=True, default="")
    output = models.TextField(blank=True, default="")
    language = models.CharField(max_length=20, default="python")

    def __str__(self):
        return self.username
