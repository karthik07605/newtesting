from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
import subprocess
import os
from django.utils import timezone
import json
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .forms import CreateUserForm
from django.contrib.auth import logout as django_logout

@login_required
def create_lobby(request):
    if request.method == 'POST':
        host_name = request.POST.get('host_name')
        lobby = Lobby.objects.create(host_name=host_name)
        lobby.members.append(host_name)
        lobby.save()
        request.session['user_name'] = host_name
        return redirect('host_view', user_id=request.user.id, code=lobby.code)
    return render(request, 'create_lobby.html')


@login_required
def join_lobby(request):
    if request.method == "POST":
        code = request.POST.get("code").upper()
        
        # Get the lobby object using the lobby code
        lobby = get_object_or_404(Lobby, code=code)
        
        # Get the current logged-in user's ID
        user_id = request.user.id

        # Check if the user has already joined the lobby
        if user_id in lobby.members:
            # If the user is already in the lobby, just redirect them to the lobby page
            return redirect('participant_view', user_id=user_id, code=code)

        # Add the participant's user ID to the lobby if it's not already in the members list
        lobby.members.append(user_id)
        lobby.save()

        # Store the user ID in the session to track the user
        request.session['user_id'] = user_id

        return redirect('participant_view', user_id=user_id, code=code)

    return render(request, 'join_lobby.html')

@login_required
def host_view(request, user_id, code):
    if request.user.id != user_id:
        return HttpResponseForbidden("You are not authorized to view this lobby.")
    lobby = get_object_or_404(Lobby, code=code)
    return render(request, 'host_view.html', {
        'lobby': lobby,
        'name': lobby.host_name,
        'code': lobby.host_code,
        'lang': lobby.host_lang,
        'output': ''
    })

@login_required
def participant_view(request, user_id, code):
    if request.user.id != user_id:
        return HttpResponseForbidden("You are not authorized to join this lobby.")
    lobby = get_object_or_404(Lobby, code=code)
    user_name = request.user.username
    return render(request, 'participant_view.html', {
        'lobby': lobby,
        'name': user_name,
        'lang': 'python',
        'output': '',
    })
    
    
@csrf_exempt
def run_code(request):
    output = ""
    code = ""
    lang = "python"

    if request.method == "POST":
        code = request.POST.get("code", "")
        lang = request.POST.get("language", "python")
        code = code.replace('\r\n', '\n')  # normalize line endings

        if request.POST.get("is_host") == "1":
            code = request.POST.get("code")
            lobby_code = request.POST.get("lobby_code")
            lobby = get_object_or_404(Lobby, code=lobby_code)
            lobby.host_code = code
            lobby.host_lang = lang
            lobby.save()

        try:
            if lang == "python":
                result = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=5)
                output = result.stdout + result.stderr
            elif lang == "c":
                with open("main.c", "w") as f: f.write(code)
                subprocess.run(["gcc", "main.c", "-o", "main"], check=True)
                result = subprocess.run(["./main"], capture_output=True, text=True, timeout=5)
                output = result.stdout + result.stderr
                os.remove("main.c")
                os.remove("main")
            elif lang == "cpp":
                with open("main.cpp", "w") as f: f.write(code)
                subprocess.run(["g++", "main.cpp", "-o", "main"], check=True)
                result = subprocess.run(["./main"], capture_output=True, text=True, timeout=5)
                output = result.stdout + result.stderr
                os.remove("main.cpp")
                os.remove("main")
            elif lang == "java":
                with open("Main.java", "w") as f: f.write(code)
                subprocess.run(["javac", "Main.java"], check=True)
                result = subprocess.run(["java", "Main"], capture_output=True, text=True, timeout=5)
                output = result.stdout + result.stderr
                os.remove("Main.java")
                os.remove("Main.class")
            else:
                output = "Unsupported language."
        except Exception as e:
            output = str(e)

    return JsonResponse({"output": output})

def get_host_code(request, code):
    lobby = get_object_or_404(Lobby, code=code)
    return JsonResponse({"code": lobby.host_code, "lang": lobby.host_lang})

@csrf_exempt
def send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        code = data.get('code')
        sender = data.get('sender')
        message = data.get('message')

        lobby = get_object_or_404(Lobby, code=code)
        ChatMessage.objects.create(lobby=lobby, sender=sender, message=message, timestamp=timezone.now())
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

def get_messages(request, code):
    lobby = get_object_or_404(Lobby, code=code)
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
        lobby.host_code = code
        lobby.host_lang = lang
        lobby.save()
        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)



def register_view(request):
    if request.method == 'POST':
        form = CreateUserForm(request.POST)  # Use your custom form
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = CreateUserForm()
    return render(request, 'register.html', {'form': form})


# Login View


def login_view(request):
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('afterlogin')  # Redirect to home after login (update this URL as needed)
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'loginpage.html')

@login_required
def close_lobby(request, code):
    # Get the lobby object by code
    lobby = get_object_or_404(Lobby, code=code)

    # Delete all messages related to this lobby
    ChatMessage.objects.filter(lobby=lobby).delete()

    # Delete the lobby itself
    lobby.delete()

    # Optionally, add a success message or redirect
    messages.success(request, f"Lobby {code} has been closed successfully.")

    return JsonResponse({"status": "ok", "message": f"Lobby {code} has been closed."})


@login_required
def afterlogin(request):
    return render(request,'afterlogin.html')

@login_required
def logout(request):
    django_logout(request)
    return redirect('login')