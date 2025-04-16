from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from .models import Lobby, Participant, ChatMessage
from django.views.decorators.csrf import csrf_exempt
import subprocess
import os
import tempfile
from django.utils import timezone
import json
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .forms import CreateUserForm
from django.contrib.auth import logout as django_logout
import datetime

@login_required
def create_lobby(request):
    if request.method == 'POST':
        host_name = request.POST.get('host_name')
        lobby = Lobby.objects.create(host_name=host_name, created_at=timezone.now())
        lobby.members.append(host_name)
        lobby.save()
        request.session['user_name'] = host_name
        return redirect('host_view', user_id=request.user.id, code=lobby.code)
    return render(request, 'create_lobby.html')

@login_required
def join_lobby(request):
    if request.method == "POST":
        code = request.POST.get("code").upper()
        try:
            lobby = Lobby.objects.get(code=code)
            # Check if lobby is expired
            if is_lobby_expired(lobby):
                close_lobby_internal(lobby)
                messages.error(request, "The lobby has expired.")
                return redirect('afterlogin')
            user_id = request.user.id
            user_name = request.user.username

            if user_id not in lobby.members:
                lobby.members.append(user_id)
                Participant.objects.get_or_create(lobby=lobby, username=user_name)
                lobby.save()

            request.session['user_id'] = user_id
            return redirect('participant_view', user_id=user_id, code=code)
        except Lobby.DoesNotExist:
            messages.error(request, "No lobby exists with the provided code.")
            return render(request, 'join_lobby.html')
    return render(request, 'join_lobby.html')

@login_required
def host_view(request, user_id, code):
    if request.user.id != user_id:
        return HttpResponseForbidden("You are not authorized to view this lobby.")
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return redirect('afterlogin')
    participants = Participant.objects.filter(lobby=lobby)
    return render(request, 'host_view.html', {
        'lobby': lobby,
        'name': lobby.host_name,
        'code': lobby.host_code,
        'lang': lobby.host_lang,
        'output': '',
        'participants': participants,
        'created_at': lobby.created_at.isoformat()
    })

@login_required
def participant_view(request, user_id, code):
    if request.user.id != user_id:
        return HttpResponseForbidden("You are not authorized to join this lobby.")
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return redirect('afterlogin')
    user_name = request.user.username
    participants = Participant.objects.filter(lobby=lobby)
    return render(request, 'participant_view.html', {
        'lobby': lobby,
        'name': user_name,
        'lang': 'python',
        'output': '',
        'participants': participants,
        'created_at': lobby.created_at.isoformat()
    })

@csrf_exempt
def run_code(request):
    if request.method == "POST":
        code = request.POST.get("code", "")
        lang = request.POST.get("language", "python")
        input_data = request.POST.get("input", "")
        code = code.replace('\r\n', '\n')
        is_host = request.POST.get("is_host") == "1"
        lobby_code = request.POST.get("lobby_code", "")

        if is_host and lobby_code:
            lobby = get_object_or_404(Lobby, code=lobby_code)
            lobby.host_code = code
            lobby.host_lang = lang
            lobby.save()

        try:
            extension = {'python': '.py', 'c': '.c', 'cpp': '.cpp', 'java': '.java'}
            with tempfile.NamedTemporaryFile(mode='w', suffix=extension.get(lang, '.txt'), delete=False) as f:
                f.write(code)
                temp_file = f.name

            output = ""
            error = ""

            if lang == "python":
                process = subprocess.run(
                    ["python3", temp_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = process.stdout
                error = process.stderr
            elif lang == "c":
                output_file = temp_file.replace('.c', '')
                subprocess.run(["gcc", temp_file, "-o", output_file], check=True, capture_output=True, text=True)
                process = subprocess.run(
                    [output_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = process.stdout
                error = process.stderr
                os.remove(output_file)
            elif lang == "cpp":
                output_file = temp_file.replace('.cpp', '')
                subprocess.run(["g++", temp_file, "-o", output_file], check=True, capture_output=True, text=True)
                process = subprocess.run(
                    [output_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = process.stdout
                error = process.stderr
                os.remove(output_file)
            elif lang == "java":
                class_name = "Main"
                subprocess.run(["javac", temp_file], check=True, capture_output=True, text=True)
                process = subprocess.run(
                    ["java", "-cp", os.path.dirname(temp_file), class_name],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = process.stdout
                error = process.stderr
                os.remove(temp_file.replace('.java', '.class'))
            else:
                output = "Unsupported language."

            os.remove(temp_file)
            final_output = output + error

            if is_host and lobby_code:
                lobby.host_output = final_output
                lobby.save()

            return JsonResponse({"output": final_output})

        except subprocess.TimeoutExpired:
            return JsonResponse({"output": "Error: Code execution timed out"})
        except subprocess.CalledProcessError as e:
            return JsonResponse({"output": f"Error: {e.stderr}"})
        except Exception as e:
            return JsonResponse({"output": f"Error: {str(e)}"})

    return JsonResponse({"output": "Invalid request"}, status=400)

def get_host_code(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
    return JsonResponse({
        "code": lobby.host_code,
        "lang": lobby.host_lang,
        "output": lobby.host_output
    })

@csrf_exempt
def send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        code = data.get('code')
        sender = data.get('sender')
        message = data.get('message')

        lobby = get_object_or_404(Lobby, code=code)
        if is_lobby_expired(lobby):
            close_lobby_internal(lobby)
            return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
        ChatMessage.objects.create(lobby=lobby, sender=sender, message=message, timestamp=timezone.now())
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

def get_messages(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
    messages = ChatMessage.objects.filter(lobby=lobby).order_by('timestamp')
    return JsonResponse({
        'messages': [
            {'sender': m.sender, 'message': m.message, 'timestamp': m.timestamp.strftime("%H:%M:%S")}
            for m in messages
        ]
    })

@csrf_exempt
def update_host_code(request):
    if request.method == 'POST':
        code = request.POST.get("code", "")
        lang = request.POST.get("language", "python")
        lobby_code = request.POST.get("lobby_code", "")

        if not lobby_code:
            return JsonResponse({"status": "error", "message": "Missing lobby code"}, status=400)

        lobby = get_object_or_404(Lobby, code=lobby_code)
        if is_lobby_expired(lobby):
            close_lobby_internal(lobby)
            return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
        lobby.host_code = code
        lobby.host_lang = lang
        lobby.save()
        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

def register_view(request):
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = CreateUserForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    # If user is already authenticated, redirect to afterlogin
    if request.user.is_authenticated:
        return redirect('afterlogin')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Check for 'next' parameter to redirect to intended page
            next_url = request.POST.get('next', request.GET.get('next', 'afterlogin'))
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'loginpage.html')

@login_required
def close_lobby(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    close_lobby_internal(lobby)
    messages.success(request, f"Lobby {code} has been closed successfully.")
    return redirect('afterlogin')

def close_lobby_internal(lobby):
    ChatMessage.objects.filter(lobby=lobby).delete()
    Participant.objects.filter(lobby=lobby).delete()
    lobby.delete()

@login_required
def afterlogin(request):
    return render(request, 'afterlogin.html')

@login_required
def logout(request):
    django_logout(request)
    return redirect('login')

def get_participant_code(request, code, participant_id):
    try:
        participant = Participant.objects.get(id=participant_id, lobby__code=code)
        lobby = get_object_or_404(Lobby, code=code)
        if is_lobby_expired(lobby):
            close_lobby_internal(lobby)
            return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
        return JsonResponse({
            'status': 'success',
            'code': participant.code,
            'output': participant.output,
            'language': participant.language,
            'username': participant.username
        })
    except Participant.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Participant not found'}, status=404)

def get_participants(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
    participants = Participant.objects.filter(lobby=lobby)
    data = [
        {
            'id': participant.id,
            'username': participant.username,
            'language': participant.language
        } for participant in participants
    ]
    return JsonResponse({'status': 'success', 'participants': data})

def check_lobby_status(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    if is_lobby_expired(lobby):
        close_lobby_internal(lobby)
        return JsonResponse({"status": "expired", "redirect": "/afterlogin"})
    return JsonResponse({"status": "active"})

def is_lobby_expired(lobby):
    time_elapsed = timezone.now() - lobby.created_at
    three_hours = datetime.timedelta(hours=3)
    return time_elapsed > three_hours

def home(request):
    return render(request, 'mainpage.html')