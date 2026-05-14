export async function createUserProfileWidget(layer) {
  const s = layer.settings_json || {};
  const wrapper = document.createElement('div');
  wrapper.className = 'user-profile-widget';
  wrapper.style.cssText = `
    display:flex; flex-direction:column; align-items:center; gap:4px; box-sizing:border-box;
    ${s.font_family ? `font-family:${s.font_family};` : ''}
    ${s.font_weight ? `font-weight:${s.font_weight};` : ''}
    ${s.font_style ? `font-style:${s.font_style};` : ''}
    ${s.text_decoration ? `text-decoration:${s.text_decoration};` : ''}
    ${s.text_color || s.color ? `color:${s.text_color || s.color};` : ''}
    ${s.font_size && s.size_mode !== 'box' ? `font-size:${s.font_size};` : ''}
    ${s.letter_spacing ? `letter-spacing:${s.letter_spacing};` : ''}
    ${s.line_height ? `line-height:${s.line_height};` : ''}
    ${s.border_width ? `border:${s.border_width}px ${s.border_style || 'solid'} ${s.border_color || '#000'};` : ''}
  `;

  let profileData = null;
  try {
    const res = await fetch('/api/user/profile/', { credentials: 'same-origin' });
    if (res.ok) {
      const j = await res.json();
      if (j.ok) profileData = j.data;
    }
  } catch {}

  if (!profileData) {
    wrapper.textContent = s.guest_text || '로그인이 필요합니다';
    return wrapper;
  }

  const imgWrapper = document.createElement('div');
  imgWrapper.style.cssText = 'width:64px;height:64px;border-radius:50%;overflow:hidden;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.08);';
  if (profileData.profile_image_url) {
    const img = document.createElement('img');
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
    img.src = profileData.profile_image_url;
    img.alt = profileData.nickname;
    imgWrapper.appendChild(img);
  } else {
    imgWrapper.textContent = '👤';
  }

  const nick = document.createElement('div');
  nick.className = 'user-profile-widget__nickname';
  nick.textContent = profileData.nickname;

  const pts = document.createElement('div');
  pts.className = 'user-profile-widget__points';
  pts.textContent = `${profileData.points.toLocaleString('ko-KR')} pts`;

  wrapper.append(imgWrapper, nick, pts);
  return wrapper;
}
