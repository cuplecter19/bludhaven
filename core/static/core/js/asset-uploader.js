export async function uploadAsset(file, kind) {
  const form = new FormData();
  form.append('file', file);
  form.append('kind', kind);

  const response = await fetch('/api/assets/upload', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': getCsrfToken() },
    body: form,
  });
  return response.json();
}

export async function uploadAssetFromUrl(url, kind) {
  const response = await fetch('/api/assets/upload-url', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url, kind }),
  });
  return response.json();
}

function getCsrfToken() {
  const match = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
  return match ? match.pop() : '';
}
