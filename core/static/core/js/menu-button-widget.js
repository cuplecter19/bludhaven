function hexToRgba(hex, opacity) {
  const clean = hex.replace('#', '');
  const full  = clean.length === 3
    ? clean.split('').map(c => c + c).join('')
    : clean;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

export function createMenuButtonLayer(layer) {
  const settings = layer.settings_json || {};
  const link = document.createElement('a');
  link.href = settings.url || '#';
  link.target = settings.target || '_self';
  link.textContent = settings.label || settings.text || 'MENU';
  link.setAttribute('aria-label', settings.aria_label || settings.label || settings.text || 'menu button');
  
  link.classList.add('bh-menu-link');
  if (settings.bg_color) {
    const opacity = settings.bg_color_opacity ?? 1;
    const highlight = hexToRgba(settings.bg_color, opacity);
    link.style.setProperty('--menu-highlight-color', highlight);
  }

  link.style.border = 'none';
  link.style.padding = '0';
  link.style.margin = '0';
  link.style.display = 'inline';
  link.style.textDecoration = settings.text_decoration || 'none';
  if (settings.font_family) link.style.fontFamily = settings.font_family;
  if (settings.font_weight) link.style.fontWeight = String(settings.font_weight);
  if (settings.font_style) link.style.fontStyle = settings.font_style;
  if (settings.text_color || settings.color) link.style.color = settings.text_color || settings.color;
  if (settings.font_size && settings.size_mode !== 'box') link.style.fontSize = settings.font_size;
  if (settings.letter_spacing) link.style.letterSpacing = settings.letter_spacing;
  if (settings.line_height) link.style.lineHeight = String(settings.line_height);

  if (settings.icon) {
    const icon = document.createElement('span');
    icon.textContent = settings.icon;
    link.prepend(icon);
  }
  return link;
}
