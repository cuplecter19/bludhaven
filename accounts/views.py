from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from .models import User

@login_required
def profile_update(request):
    user = request.user
    if request.method == "POST":
        nickname = request.POST.get('nickname')
        theme_preference = request.POST.get('theme_preference')
        delete_image = request.POST.get('delete_image')

        # 닉네임 중복 체크 (자신 제외)
        if User.objects.filter(nickname=nickname).exclude(id=user.id).exists():
            messages.error(request, "이미 존재하는 닉네임입니다.")
            return render(request, 'accounts/profile_update.html', {'user': user})

        if delete_image == 'on' and user.profile_image:
            user.profile_image.delete(save=False)  # 파일 삭제
            user.profile_image = None  # 필드 초기화

        # 파일이 있으면 이미지를 담고, 없으면 None을 담습니다.
        image = request.FILES.get('profile_image')

        if image: # 만약 None이 아니라면 (파일이 들어있다면)
            user.profile_image = image

        user.nickname = nickname
        user.theme_preference = theme_preference
        user.save()
        
        messages.success(request, "프로필이 업데이트되었습니다!")
        return redirect('accounts:profile_update')
    
    return render(request, 'accounts/profile_update.html', {'user': user})

def signup(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        nickname = request.POST.get('nickname')

        if User.objects.filter(username=username).exists():
            messages.error(request, "이미 존재하는 ID입니다.")
            return render(request, 'accounts/signup.html')

        # 2. 닉네임 중복 체크
        if User.objects.filter(nickname=nickname).exists():
            messages.error(request, "이미 존재하는 닉네임입니다.")
            return render(request, 'accounts/signup.html')
        
        # 유저 생성 (가입 즉시 환영 포인트 100점 증정!)
        user = User.objects.create_user(username=username, password=password)
        user.nickname = nickname
        user.points = 100 
        user.save()
        
        messages.success(request, f"{nickname}님, 블러드헤이븐에 오신 것을 환영합니다!")
        return redirect('index')
        
    return render(request, 'accounts/signup.html')

def logout_view(request):
    logout(request)
    messages.success(request, "성공적으로 로그아웃되었습니다.")
    return redirect('index')

def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"{user.nickname}님, 환영합니다!")
            return redirect('index')
        else:
            messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
            return render(request, 'accounts/login.html')

    return render(request, 'accounts/login.html')