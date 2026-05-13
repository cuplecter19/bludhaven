export function createMenuButtonLayer(layer) {
  const settings = layer.settings_json || {};
  const link = document.createElement('a');
  link.href = settings.url || '#';
  link.target = settings.target || '_self';
  link.textContent = settings.label || 'MENU';
  link.setAttribute('aria-label', settings.aria_label || settings.label || 'menu button');

  if (settings.icon) {
    const icon = document.createElement('span');
    icon.textContent = settings.icon;
    link.prepend(icon);
  }
  return link;
}
