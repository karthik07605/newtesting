import json
import os
import subprocess
import tempfile

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.code = self.scope['url_route']['kwargs']['code']
        self.lobby_group_name = f"lobby_{self.code}"

        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender = data['sender']

        await self.save_message(self.code, sender, message)

        await self.channel_layer.group_send(
            self.lobby_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    @database_sync_to_async
    def save_message(self, code, sender, message):
        from idea.models import Lobby, ChatMessage
        lobby = Lobby.objects.get(code=code)
        ChatMessage.objects.create(lobby=lobby, sender=sender, message=message)


class OutputConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lobby_code = self.scope['url_route']['kwargs']['lobby_code']
        self.output_group_name = f"lobby_{self.lobby_code}_output"

        await self.channel_layer.group_add(
            self.output_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.output_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        code = data['code']
        language = data['language']

        output = await self.execute_code(code, language)

        await self.channel_layer.group_send(
            self.output_group_name,
            {
                'type': 'send_output',
                'output': output
            }
        )

    async def send_output(self, event):
        await self.send(text_data=json.dumps({
            'output': event['output']
        }))

    async def execute_code(self, code, language):
        try:
            if language == 'python':
                result = subprocess.run(['python3', '-c', code], capture_output=True, text=True, timeout=10)

            elif language in ['c', 'cpp']:
                with tempfile.NamedTemporaryFile(suffix='.c' if language == 'c' else '.cpp', delete=False) as source_file:
                    source_file.write(code.encode())
                    source_path = source_file.name

                output_path = source_path.replace('.c', '').replace('.cpp', '')

                compile_cmd = ['gcc', source_path, '-o', output_path] if language == 'c' else ['g++', source_path, '-o', output_path]
                compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)

                if compile_result.returncode == 0:
                    run_result = subprocess.run([output_path], capture_output=True, text=True, timeout=5)
                    return run_result.stdout + run_result.stderr
                else:
                    return compile_result.stdout + compile_result.stderr

            elif language == 'java':
                with open('TempProgram.java', 'w') as f:
                    f.write(code)

                compile_result = subprocess.run(['javac', 'TempProgram.java'], capture_output=True, text=True)
                if compile_result.returncode == 0:
                    run_result = subprocess.run(['java', 'TempProgram'], capture_output=True, text=True, timeout=5)
                    return run_result.stdout + run_result.stderr
                else:
                    return compile_result.stdout + compile_result.stderr

            else:
                return "Unsupported language"

            return result.stdout + result.stderr

        except Exception as e:
            return f"Error: {str(e)}"


