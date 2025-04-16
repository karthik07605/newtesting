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

        # Add the channel to the lobby group
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        await self.accept()

        # Add participant if user joins
        user = self.scope.get('user')
        if user and user.is_authenticated:
            await self.add_participant(user.username)
            await self.send_participants_list()

    async def disconnect(self, close_code):
        # Remove participant on disconnect
        user = self.scope.get('user')
        if user and user.is_authenticated:
            await self.remove_participant(user.username)
            await self.send_participants_list()

        # Remove the channel from the lobby group
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'join':
                user = data.get('user')
                if user:
                    await self.add_participant(user)
                    await self.send_participants_list()

            message = data.get('message')
            sender = data.get('sender')

            if message and sender:
                await self.save_message(self.code, sender, message)
                await self.channel_layer.group_send(
                    self.lobby_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'sender': sender
                    }
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format.'
            }))

    async def chat_message(self, event):
        # Send chat message to WebSocket clients
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    async def notify_kicked(self, event):
        # Notify a specific participant that they have been kicked
        await self.send(text_data=json.dumps({
            'type': 'kicked',
            'user': event['user']
        }))

    async def update_participants(self, event):
        # Send updated participant list to WebSocket clients
        await self.send(text_data=json.dumps({
            'type': 'participants',
            'participants': event['participants']
        }))

    @database_sync_to_async
    def save_message(self, code, sender, message):
        from idea.models import Lobby, ChatMessage
        try:
            lobby = Lobby.objects.get(code=code)
            ChatMessage.objects.create(lobby=lobby, sender=sender, message=message)
        except Lobby.DoesNotExist:
            pass

    @database_sync_to_async
    def add_participant(self, username):
        from idea.models import Lobby, Participant
        try:
            lobby = Lobby.objects.get(code=self.code)
            Participant.objects.get_or_create(lobby=lobby, username=username)
        except Lobby.DoesNotExist:
            pass

    @database_sync_to_async
    def remove_participant(self, username):
        from idea.models import Participant
        Participant.objects.filter(lobby__code=self.code, username=username).delete()

    @database_sync_to_async
    def get_participants(self):
        from idea.models import Participant
        return list(Participant.objects.filter(lobby__code=self.code).values('id', 'username'))

    async def send_participants_list(self):
        participants = await self.get_participants()
        await self.channel_layer.group_send(
            self.lobby_group_name,
            {
                'type': 'update_participants',
                'participants': participants
            }
        )


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
                return result.stdout + result.stderr

            elif language in ['c', 'cpp']:
                with tempfile.NamedTemporaryFile(suffix='.c' if language == 'c' else '.cpp', delete=False) as source_file:
                    source_file.write(code.encode())
                    source_path = source_file.name

                output_path = source_path.replace('.c', '').replace('.cpp', '')

                compile_cmd = ['gcc', source_path, '-o', output_path] if language == 'c' else ['g++', source_path, '-o', output_path]
                compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)

                if compile_result.returncode == 0:
                    run_result = subprocess.run([output_path], capture_output=True, text=True, timeout=5)
                    output = run_result.stdout + run_result.stderr
                else:
                    output = compile_result.stdout + compile_result.stderr

                try:
                    os.remove(source_path)
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except:
                    pass

                return output

            elif language == 'java':
                with tempfile.NamedTemporaryFile(suffix='.java', delete=False) as source_file:
                    class_name = "TempProgram"
                    java_code = code
                    source_file.write(java_code.encode())
                    source_path = source_file.name

                compile_result = subprocess.run(['javac', source_path], capture_output=True, text=True)
                
                if compile_result.returncode == 0:
                    class_dir = os.path.dirname(source_path)
                    run_result = subprocess.run(['java', '-cp', class_dir, class_name], 
                                                capture_output=True, text=True, timeout=5)
                    output = run_result.stdout + run_result.stderr
                else:
                    output = compile_result.stdout + compile_result.stderr

                try:
                    os.remove(source_path)
                    class_file = source_path.replace('.java', '.class')
                    if os.path.exists(class_file):
                        os.remove(class_file)
                except:
                    pass

                return output

            else:
                return "Unsupported language"

        except subprocess.TimeoutExpired:
            return "Code execution timed out. Please check for infinite loops or long-running operations."
        except Exception as e:
            return f"Error: {str(e)}"


class HostCodeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lobby_code = self.scope['url_route']['kwargs']['lobby_code']
        self.host_code_group_name = f"lobby_{self.lobby_code}_host_code"

        await self.channel_layer.group_add(
            self.host_code_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.host_code_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        code = data['code']
        language = data['language']

        await self.save_host_code(self.lobby_code, code, language)

        await self.channel_layer.group_send(
            self.host_code_group_name,
            {
                'type': 'update_host_code',
                'code': code,
                'language': language
            }
        )

    async def update_host_code(self, event):
        await self.send(text_data=json.dumps({
            'code': event['code'],
            'language': event['language']
        }))

    @database_sync_to_async
    def save_host_code(self, lobby_code, code, language):
        from idea.models import Lobby
        lobby = Lobby.objects.get(code=lobby_code)
        lobby.host_code = code
        lobby.host_lang = language
        lobby.save()