export async function createAuthButtonsWidget(layer) {
  const s = layer.settings_json || {};
  const wrapper = document.createElement('div');
  wrapper.className = 'auth-buttons-widget';
  wrapper.style.cssText = [
    'display:flex;flex-direction:row;align-items:center;flex-wrap:wrap;box-sizing:border-box;',
    s.gap ? `gap:${s.gap};` : 'gap:8px;',
    s.font_family ? `font-family:${s.font_family};` : '',
    s.font_weight ? `font-weight:${s.font_weight};` : '',
    s.font_style ? `font-style:${s.font_style};` : '',
    s.text_decoration ? `text-decoration:${s.text_decoration};` : '',
    s.font_size && s.size_mode !== 'box' ? `font-size:${s.font_size};` : '',
    s.letter_spacing ? `letter-spacing:${s.letter_spacing};` : '',
    s.line_height ? `line-height:${s.line_height};` : '',
  ].join('');

  let isLoggedIn = false;
  try {
    const res = await fetch('/api/user/profile/', { credentials: 'same-origin' });
    if (res.ok) {
      const j = await res.json();
      if (j.ok) isLoggedIn = true;
    }
  } catch {}

  function makeLink(text, href, color) {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = text;
    a.className = 'auth-buttons-widget__btn';
    if (color) a.style.color = color;
    return a;
  }

  if (isLoggedIn) {
    wrapper.appendChild(
      makeLink(s.logout_label || 'Logout', '/accounts/logout/', s.logout_color || s.text_color || s.color || ''),
    );
  } else {
    wrapper.appendChild(
      makeLink(s.login_label || 'Login', '/accounts/login/', s.login_color || s.text_color || s.color || ''),
    );
    wrapper.appendChild(
      makeLink(s.signup_label || 'Sign Up', '/accounts/signup/', s.signup_color || s.text_color || s.color || ''),
    );
  }

  return wrapper;
}
