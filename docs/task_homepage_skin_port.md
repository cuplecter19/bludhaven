# 작업 지시서 — retro2_main_skin → bludhaven core 이식 및 개선

> **대상 repo:** `cuplecter19/bludhaven` (master 브랜치)  
> **참조 repo:** `cuplecter19/retro2_main_skin`  
> **작성일:** 2026-05-13

---

## 0. 개요

PHP 5.6 / 그누보드5 기반의 `retro2_main_skin`이 가진 아래 기능들을 Django + PostgreSQL 환경으로 이식하면서, 세 가지 UX 개선사항을 함께 반영한다.

### 이식 대상 기능

| 기능 | 설명 |
|------|------|
| 패럴랙스 배경 이미지 | 스크롤에 반응하는 배경 이미지 레이어 |
| 이미지 배치 (스티커) | 화면 위에 자유롭게 놓이는 이미지 오브젝트 (위치·크기·회전·z-index 포함) |
| 텍스트 블록 배치 | 화면 위 지정 좌표에 텍스트를 배치하는 위젯 |
| 시계 위젯 | 실시간 날짜·시각 표시 (이미 index.html에 존재 → 위치 편집 기능 추가) |
| 관리 패널 | 로그인한 superuser에게만 보이는 편집 UI |

### 제외 기능

- 배너 (banner)
- 최신글 윈도우 (recent posts window)

### UX 개선사항 (신규 구현)

1. **드래그 가능한 관리 패널** — 패널 자체를 화면 어디서든 드래그하여 위치 변경 가능
2. **실시간 미리보기** — 관리 패널에서 이미지·텍스트 위치 값을 변경하면 페이지에서 즉시 반영되어 미리보기
3. **WebP 자동 변환** — 이미지 업로드 시 원본을 저장하지 않고 WebP로 변환 후 저장하여 용량 최소화

---

## 1. 현재 bludhaven 상태 파악

작업 전 에이전트는 반드시 아래 파일들을 직접 읽어 최신 상태를 확인한다.

- `config/settings.py`
- `config/urls.py`
- `core/models.py`
- `core/views.py`
- `core/admin.py`
- `core/templates/core/index.html`
- `core/static/core/css/` (디렉토리 내 파일 전체)
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`

---

## 2. 환경 제약

| 항목 | 값 |
|------|----|
| Python | 3.12 |
| Django | 5.2.x (현재 5.2.14) |
| DB | PostgreSQL 16 (docker-compose) |
| 이미지 처리 | Pillow (이미 requirements.txt에 포함) |
| 컨테이너 OS | Ubuntu 24.04 (OCIR) |
| 스태틱/미디어 서빙 | 개발: django `runserver` + `MEDIA_URL` / 운영: nginx |

> **중요:** `libwebp` 관련 OS 의존성 없이 순수 Pillow (`Image.save(..., format='WEBP')`)만으로 WebP 변환이 가능하므로 Dockerfile 수정 불필요.  
> Pillow가 이미 설치돼 있으므로 requirements.txt에 패키지 추가는 불필요하다.

---

## 3. 데이터 모델 변경 (`core/models.py`)

현재 모델(`IndexImage`, `TextBlock`)을 **하위 호환 확장**한다. 기존 migration 파일을 삭제하지 말고 새 migration을 생성한다.

### 3-1. `IndexImage` 확장

```python
class IndexImage(models.Model):
    LAYER_BACKGROUND = 'background'
    LAYER_MAIN = 'main'
    LAYER_STICKER = 'sticker'          # 신규: 스티커 레이어
    LAYER_CHOICES = [
        (LAYER_BACKGROUND, 'Background (Parallax)'),
        (LAYER_MAIN, 'Main'),
        (LAYER_STICKER, 'Sticker'),
    ]

    title      = models.CharField(max_length=100, blank=True)
    image      = models.ImageField(upload_to='core/images/')
    layer      = models.CharField(max_length=20, choices=LAYER_CHOICES, default=LAYER_MAIN)
    order      = models.PositiveIntegerField(default=0)
    is_active  = models.BooleanField(default=True)

    # 스티커 전용 배치 필드 (다른 layer에서는 무시됨)
    pos_left   = models.CharField(max_length=20, default='50%')   # CSS left (px 또는 %)
    pos_top    = models.CharField(max_length=20, default='50%')   # CSS top
    width      = models.CharField(max_length=20, default='160px') # CSS width
    height     = models.CharField(max_length=20, default='auto')  # CSS height
    rotate     = models.IntegerField(default=0)                   # 회전각 (deg)
    z_index    = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['layer', 'order', 'z_index']
```

### 3-2. `TextBlock` 확장

```python
class TextBlock(models.Model):
    # 기존 choices는 그대로 유지하되, position을 unique 제약 없이 변경
    # (위치가 좌표로 자유화되므로 unique 제약 제거)
    position   = models.CharField(max_length=20, choices=POSITION_CHOICES, default=POSITION_BLOCK1)
    content    = models.TextField()
    is_active  = models.BooleanField(default=True)

    # 신규: 절대 좌표 배치
    pos_left   = models.CharField(max_length=20, default='5%')
    pos_top    = models.CharField(max_length=20, default='5%')
    font_size  = models.CharField(max_length=20, default='1rem')
    color      = models.CharField(max_length=20, default='#ffffff')
    z_index    = models.PositiveIntegerField(default=20)
```

> **주의:** `TextBlock.position`의 `unique=True` 제약은 제거한다. 기존 데이터가 있는 경우를 고려해 `RemoveConstraint` migration 또는 field 재정의 방식으로 처리한다.

### 3-3. `ParallaxConfig` (신규 모델)

```python
class ParallaxConfig(models.Model):
    """패럴랙스 배경 이미지 레이어별 설정값 (단일 레코드 운용)"""
    speed       = models.FloatField(default=0.4)   # 0.0~1.0, 작을수록 느리게
    blur_px     = models.IntegerField(default=0)   # 배경 blur (px)
    overlay_opacity = models.FloatField(default=0.3)

    class Meta:
        verbose_name = 'Parallax Config'

    def __str__(self):
        return f'ParallaxConfig (speed={self.speed})'
```

### 3-4. `StickerClockWidget` (신규 모델)

```python
class ClockWidgetConfig(models.Model):
    """시계 위젯 위치/스타일 설정 (단일 레코드)"""
    is_active  = models.BooleanField(default=True)
    pos_left   = models.CharField(max_length=20, default='2%')
    pos_top    = models.CharField(max_length=20, default='2%')
    font_size  = models.CharField(max_length=20, default='1rem')
    color      = models.CharField(max_length=20, default='#ffffff')
    z_index    = models.PositiveIntegerField(default=30)
```

---

## 4. 이미지 업로드 시 WebP 자동 변환

`core/utils.py` (새 파일)에 아래 함수를 구현한다.

```python
# core/utils.py
import io
from pathlib import Path
from PIL import Image
from django.core.files.base import ContentFile


def convert_to_webp(image_field_file, quality: int = 82) -> ContentFile:
    """
    Django ImageField 파일 객체를 WebP ContentFile로 변환하여 반환한다.
    원본 확장자는 .webp로 교체된다.
    """
    img = Image.open(image_field_file)
    # RGBA 모드가 아닌 경우 투명도 보존을 위해 변환
    if img.mode not in ('RGBA', 'RGB'):
        img = img.convert('RGBA')
    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=quality, method=6)
    buf.seek(0)
    stem = Path(image_field_file.name).stem
    return ContentFile(buf.read(), name=f'{stem}.webp')
```

`IndexImage` 모델의 `save()` 메서드를 오버라이드하여, `layer`가 `background` 또는 `sticker`인 경우 자동으로 WebP로 변환·저장한다.  
`layer == 'main'`인 경우도 WebP 변환을 적용한다 (모든 업로드 이미지 대상).

```python
# core/models.py 내 IndexImage.save() 오버라이드
def save(self, *args, **kwargs):
    if self.pk:
        # 기존 레코드: 이미지가 교체됐을 때만 변환
        try:
            old = IndexImage.objects.get(pk=self.pk)
            if old.image != self.image:
                self._convert_image()
        except IndexImage.DoesNotExist:
            self._convert_image()
    else:
        self._convert_image()
    super().save(*args, **kwargs)

def _convert_image(self):
    from .utils import convert_to_webp
    if self.image and not str(self.image.name).endswith('.webp'):
        webp_file = convert_to_webp(self.image)
        self.image.save(webp_file.name, webp_file, save=False)
```

---

## 5. Django Admin 확장 (`core/admin.py`)

```python
@admin.register(IndexImage)
class IndexImageAdmin(admin.ModelAdmin):
    list_display  = ('title', 'layer', 'order', 'z_index', 'is_active')
    list_editable = ('order', 'z_index', 'is_active')
    list_filter   = ('layer', 'is_active')
    fieldsets = (
        (None, {'fields': ('title', 'image', 'layer', 'order', 'is_active')}),
        ('배치 (스티커 전용)', {
            'classes': ('collapse',),
            'fields': ('pos_left', 'pos_top', 'width', 'height', 'rotate', 'z_index'),
        }),
    )

@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display  = ('position', 'is_active', 'pos_left', 'pos_top')
    list_editable = ('is_active',)
    fieldsets = (
        (None, {'fields': ('position', 'content', 'is_active')}),
        ('배치', {'fields': ('pos_left', 'pos_top', 'font_size', 'color', 'z_index')}),
    )

@admin.register(ParallaxConfig)
class ParallaxConfigAdmin(admin.ModelAdmin):
    list_display = ('speed', 'blur_px', 'overlay_opacity')

@admin.register(ClockWidgetConfig)
class ClockWidgetConfigAdmin(admin.ModelAdmin):
    list_display = ('is_active', 'pos_left', 'pos_top', 'font_size')
```

---

## 6. REST API 엔드포인트 (`core/urls.py`, `core/views.py`)

관리 패널의 실시간 미리보기를 위해 AJAX API를 구현한다.  
모든 API는 `@login_required` + `user.is_superuser` 체크를 반드시 수행한다.

### 6-1. URL 패턴 (`core/urls.py` 신규 생성)

```
GET/POST  /core/api/sticker/<int:pk>/move/     — 스티커 위치 업데이트
GET/POST  /core/api/sticker/<int:pk>/update/   — 스티커 속성 업데이트
DELETE    /core/api/sticker/<int:pk>/delete/   — 스티커 삭제
POST      /core/api/sticker/add/               — 스티커 추가 (이미지 업로드 포함)
GET/POST  /core/api/textblock/<int:pk>/update/ — 텍스트블록 업데이트
GET/POST  /core/api/clock/update/              — 시계 위젯 설정 업데이트
GET/POST  /core/api/parallax/update/           — 패럴랙스 설정 업데이트
GET       /core/api/state/                     — 전체 레이아웃 상태 반환 (JSON)
```

`config/urls.py`에 `path('core/', include('core.urls'))` 추가.

### 6-2. View 구현 원칙

- DRF `APIView` 또는 `@api_view` 데코레이터 사용 (이미 requirements.txt에 DRF 포함)
- 모든 write API는 `IsAdminUser` 퍼미션 적용
- 응답 형식: `{"ok": true, "data": {...}}` 또는 `{"ok": false, "error": "..."}`
- `add_sticker` API: 업로드된 파일을 WebP 변환 후 저장, `IndexImage` 레코드 생성

---

## 7. 프론트엔드 구현

### 7-1. 파일 구조

```
core/static/core/
  css/
    index.css         (기존 — 수정)
    admin_panel.css   (신규)
  js/
    index.js          (신규 — 메인 페이지 JS)
    admin_panel.js    (신규 — 관리 패널 로직)
```

### 7-2. `core/templates/core/index.html` 전면 개편

#### 레이어 구조

```
Layer -2: .layer-parallax-bg     — 패럴랙스 배경 이미지 (CSS transform translateY 방식)
Layer -1: .layer-bg-text         — 배경 워터마크 텍스트 (기존 유지)
Layer  0: .layer-main-images     — 메인 이미지 슬롯 (기존 유지, 개수 제한 없음으로 확장)
Layer  1: .layer-stickers        — 스티커 레이어 (id="sticker-{pk}")
Layer  2: .layer-text-blocks     — 텍스트 블록 (id="textblock-{pk}")
Layer  3: .layer-clock           — 시계 위젯
Layer  4: .layer-menu            — 메뉴 (기존 유지)
Layer  5: .layer-admin-panel     — 관리 패널 (superuser만 렌더링)
```

#### 패럴랙스 구현

- CSS `position: fixed` + JavaScript `scroll` 이벤트 방식 사용
- `transform: translateY(scrollY * speed)` 공식 적용
- `speed` 값은 `ParallaxConfig` DB에서 읽어 Django template `data-parallax-speed` 속성으로 전달
- IntersectionObserver 또는 `requestAnimationFrame`으로 성능 최적화

```javascript
// index.js 패럴랙스 핵심 로직
const parallaxBg = document.querySelector('.layer-parallax-bg');
const speed = parseFloat(parallaxBg?.dataset.parallaxSpeed ?? 0.4);

function onScroll() {
    if (!parallaxBg) return;
    requestAnimationFrame(() => {
        parallaxBg.style.transform = `translateY(${window.scrollY * speed}px)`;
    });
}
window.addEventListener('scroll', onScroll, { passive: true });
```

#### 스티커 렌더링

```html
{% for sticker in stickers %}
<div class="sticker-item {% if is_admin %}sticker-item--editable{% endif %}"
     id="sticker-{{ sticker.pk }}"
     data-pk="{{ sticker.pk }}"
     style="left:{{ sticker.pos_left }};top:{{ sticker.pos_top }};
            width:{{ sticker.width }};height:{{ sticker.height }};
            transform:rotate({{ sticker.rotate }}deg);
            z-index:{{ sticker.z_index }};">
    <img src="{{ sticker.image.url }}" alt="{{ sticker.title }}" draggable="false">
    {% if is_admin %}
    <div class="sticker-handle" title="드래그하여 이동">⠿</div>
    {% endif %}
</div>
{% endfor %}
```

#### 텍스트 블록 렌더링

```html
{% for tb in text_blocks %}
<div class="text-block-item {% if is_admin %}text-block-item--editable{% endif %}"
     id="textblock-{{ tb.pk }}"
     data-pk="{{ tb.pk }}"
     style="left:{{ tb.pos_left }};top:{{ tb.pos_top }};
            font-size:{{ tb.font_size }};color:{{ tb.color }};
            z-index:{{ tb.z_index }};">
    {{ tb.content }}
</div>
{% endfor %}
```

### 7-3. 관리 패널 (`admin_panel.js`, `admin_panel.css`)

관리 패널은 superuser 로그인 시에만 렌더링된다. Django template에서 `{% if request.user.is_superuser %}` 로 감싼다.

#### 드래그 가능한 패널

```javascript
// admin_panel.js — 패널 드래그
function makeDraggable(el, handleEl) {
    let startX, startY, startLeft, startTop;
    handleEl.addEventListener('pointerdown', e => {
        e.preventDefault();
        startX = e.clientX;
        startY = e.clientY;
        const rect = el.getBoundingClientRect();
        startLeft = rect.left;
        startTop  = rect.top;
        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp, { once: true });
    });
    function onMove(e) {
        el.style.left = `${startLeft + e.clientX - startX}px`;
        el.style.top  = `${startTop  + e.clientY - startY}px`;
    }
    function onUp() {
        document.removeEventListener('pointermove', onMove);
    }
}
```

#### 스티커 드래그 이동 + 미리보기

- 관리 패널에서 스티커를 선택하면 해당 스티커에 `.is-selected` 클래스 추가
- 스티커 DOM 요소를 마우스로 드래그할 수 있도록 구현 (pointerdown/pointermove/pointerup)
- 드래그 중에는 `style.left` / `style.top` 실시간 갱신 (미리보기)
- 드래그 완료(pointerup) 시 `/core/api/sticker/<pk>/move/` PATCH 호출하여 DB 저장

#### 텍스트 블록 위치 미리보기

- 관리 패널 내 `<input>` 값 변경 시 `input` 이벤트 리스너에서 대상 DOM의 `style.left/top` 즉시 갱신
- `blur` 또는 별도 "저장" 버튼 클릭 시 API 호출

#### 패럴랙스 설정 슬라이더

- `speed` (range 0.0–1.0), `overlay_opacity` (range 0.0–0.8) 슬라이더
- 값 변경 시 CSS variable(`--parallax-speed`, `--overlay-opacity`)을 `document.documentElement.style.setProperty`로 즉시 반영
- "저장" 버튼 클릭 시 `/core/api/parallax/update/` 호출

---

## 8. `core/views.py` 변경

```python
from django.shortcuts import render
from .models import IndexImage, TextBlock, ParallaxConfig, ClockWidgetConfig


def index(request):
    bg_image = IndexImage.objects.filter(
        layer=IndexImage.LAYER_BACKGROUND, is_active=True
    ).first()
    main_images = IndexImage.objects.filter(
        layer=IndexImage.LAYER_MAIN, is_active=True
    )
    stickers = IndexImage.objects.filter(
        layer=IndexImage.LAYER_STICKER, is_active=True
    ).order_by('z_index')
    text_blocks = TextBlock.objects.filter(is_active=True)

    # 단일 설정 레코드 — 없으면 기본값 사용
    parallax_cfg = ParallaxConfig.objects.first() or ParallaxConfig()
    clock_cfg    = ClockWidgetConfig.objects.first() or ClockWidgetConfig()

    context = {
        'bg_image':     bg_image,
        'main_images':  main_images,
        'stickers':     stickers,
        'text_blocks':  text_blocks,
        'parallax_cfg': parallax_cfg,
        'clock_cfg':    clock_cfg,
        'is_admin':     request.user.is_superuser,
    }
    return render(request, 'core/index.html', context)
```

---

## 9. Migration 순서

1. `core/models.py` 수정 완료 후: `python manage.py makemigrations core`
2. 생성된 migration 파일을 검토하여 오류 없는지 확인
3. 특히 `TextBlock.position`의 `unique` 제약 제거가 migration에 포함됐는지 확인
4. `python manage.py migrate` (실제 실행은 에이전트가 하지 않으며, 코드만 생성)

---

## 10. 검토 체크리스트 (에이전트 필수 수행)

에이전트는 아래 항목을 코드 작성 후 **각 항목별로 명시적으로 검토**하고, 문제가 있으면 수정 후 재검토한다.

### 10-1. Python / Django 문법 오류

- [ ] 모든 `.py` 파일의 import 경로가 올바른지 확인 (상대/절대 import 혼용 금지)
- [ ] `models.py`에서 새 필드 추가 후 `default` 값이 모두 지정됐는지 확인
- [ ] `TextBlock.position` unique 제약이 확실히 제거됐는지 확인
- [ ] `core/urls.py` 신규 생성 후 `config/urls.py`에 `include` 추가됐는지 확인
- [ ] `views.py`의 모든 모델 임포트가 일치하는지 확인

### 10-2. WebP 변환 로직

- [ ] `IndexImage.save()` 내 `_convert_image()` 호출 시 이미 `.webp` 확장자인 경우 재변환하지 않는지 확인
- [ ] `image` 필드가 None/빈 값인 경우에 대한 guard 확인
- [ ] `convert_to_webp` 함수에서 RGBA/RGB 외 모드(`P`, `L` 등) 처리 확인

### 10-3. REST API

- [ ] 모든 write API에 `IsAdminUser` 퍼미션이 적용됐는지 확인
- [ ] CSRF 처리: Django의 세션 인증을 사용하므로 DRF `SessionAuthentication` + CSRF enforced 확인
- [ ] `add_sticker` API에서 파일 업로드 후 WebP 변환 흐름 확인 (`InMemoryUploadedFile` 처리)
- [ ] 모든 API가 `{"ok": true/false, ...}` 형식을 일관되게 반환하는지 확인

### 10-4. 프론트엔드

- [ ] `admin_panel.js`가 `is_admin` 컨텍스트가 False일 때 로드되지 않는지 확인 (template 조건)
- [ ] 드래그 중 `pointer-events` 충돌이 없는지 확인 (이미지 위 sticker-handle 분리)
- [ ] 패럴랙스 스크롤 이벤트에 `{ passive: true }` 옵션이 적용됐는지 확인
- [ ] 모든 AJAX 호출에 CSRF 토큰(`getCookie('csrftoken')`)이 포함됐는지 확인
- [ ] 관리 패널 내 저장 API 실패 시 사용자에게 에러 메시지를 표시하는지 확인

### 10-5. 기존 기능 호환성

- [ ] 기존 `IndexImage` (LAYER_BACKGROUND, LAYER_MAIN), `TextBlock` 데이터 구조가 migration 후에도 정상 동작하는지 확인
- [ ] `config/urls.py`의 기존 URL 패턴 (`accounts`, `leitner`, `shop`, `scheduler`)이 그대로 유지되는지 확인
- [ ] `core/templates/core/index.html`에서 기존 `accounts:login`, `accounts:logout`, `accounts:signup`, `accounts:profile_update` 등 URL 참조가 유지되는지 확인

### 10-6. 마이그레이션 파일

- [ ] `makemigrations` 결과로 생성될 migration이 기존 `0001_initial.py` 이후의 번호로 생성되는지 확인 (기존 파일 삭제 금지)
- [ ] `dependencies`가 올바른 이전 migration을 참조하는지 확인

---

## 11. 작업 순서 권장

1. `core/utils.py` 생성 (WebP 변환 유틸)
2. `core/models.py` 수정 (필드 추가, 새 모델 추가, `save()` 오버라이드)
3. migration 파일 생성 (`core/migrations/000X_...py`)
4. `core/admin.py` 수정
5. `core/urls.py` 신규 생성 (API 라우팅)
6. `core/views.py` 수정 (index view 확장 + API views 추가)
7. `config/urls.py` 수정 (`core/` include 추가)
8. `core/static/core/js/index.js` 신규 생성
9. `core/static/core/js/admin_panel.js` 신규 생성
10. `core/static/core/css/admin_panel.css` 신규 생성
11. `core/static/core/css/index.css` 수정 (패럴랙스, 스티커, 텍스트블록 스타일 추가)
12. `core/templates/core/index.html` 전면 개편
13. 10절 체크리스트 전 항목 검토 및 수정

---

## 12. 참조 파일 (retro2_main_skin)

에이전트는 아래 원본 PHP 파일들을 직접 읽어 로직을 참조한다.

| 파일 | 내용 |
|------|------|
| `main.skin.php` | 전체 HTML 구조, 레이아웃 |
| `main.lib.php` | 헬퍼 함수 (이미지 업로드, 스티커 정규화, JSON 응답 등) |
| `main.js` | 프론트엔드 로직 (관리 패널, 드래그, 패럴랙스) |
| `main.css` | 스타일시트 |
| `sticker_update.php` | 스티커 CRUD API 로직 |
| `config_update.php` | 이미지/텍스트/패럴랙스 설정 저장 로직 |

> PHP 로직을 그대로 복사하지 말고, **Django 방식으로 재구현**한다.  
> 특히 PHP의 파일 기반 설정 저장(`json_encode` → 파일 쓰기)은 **PostgreSQL DB 저장**으로 대체한다.
