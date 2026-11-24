(() => {
  const websiteOrigins = new Set([
    'https://theironchapter.com',
    'https://rebrand-review.iron-chapter-site.pages.dev'
  ]);
  const formsOrigin = 'https://forms.theironchapter.com';
  const siteKey = '0x4AAAAAAGB56iQ19L5gjMCO';
  const verificationUnavailable = 'Verification is unavailable. Please try again.';
  let turnstileLoading;

  function loadTurnstile() {
    if (window.turnstile?.render) return Promise.resolve(window.turnstile);
    if (!turnstileLoading) {
      turnstileLoading = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        const deadline = setTimeout(fail, 10000);

        function fail() {
          clearTimeout(deadline);
          script.remove();
          reject(new Error(verificationUnavailable));
        }

        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.addEventListener('error', fail, { once: true });
        script.addEventListener('load', () => {
          if (!window.turnstile?.render) {
            fail();
            return;
          }
          clearTimeout(deadline);
          resolve(window.turnstile);
        }, { once: true });
        document.head.append(script);
      }).catch(error => {
        turnstileLoading = undefined;
        throw error;
      });
    }
    return turnstileLoading;
  }

  async function getToken(container, action) {
    const turnstile = await loadTurnstile();
    let widgetId;
    let deadline;
    container.hidden = false;
    try {
      return await new Promise((resolve, reject) => {
        const expire = () => reject(new Error('Verification expired. Please submit the form again.'));
        const unavailable = () => reject(new Error(verificationUnavailable));
        deadline = setTimeout(expire, 120000);
        try {
          widgetId = turnstile.render(container, {
            sitekey: siteKey,
            action,
            execution: 'execute',
            appearance: 'interaction-only',
            theme: 'dark',
            size: 'compact',
            retry: 'never',
            'refresh-expired': 'never',
            'refresh-timeout': 'never',
            'response-field': false,
            callback: token => typeof token === 'string' && token ? resolve(token) : unavailable(),
            'error-callback': () => {
              unavailable();
              return true;
            },
            'expired-callback': expire,
            'timeout-callback': expire,
            'unsupported-callback': unavailable
          });
          turnstile.execute(container);
        } catch {
          unavailable();
        }
      });
    } finally {
      clearTimeout(deadline);
      container.hidden = true;
      if (widgetId) turnstile.remove(widgetId);
    }
  }

  async function send(action, fields, turnstileToken) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 15000);
    let response;
    let result;

    try {
      response = await fetch(`${formsOrigin}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ ...fields, turnstileToken }),
        signal: controller.signal
      });
      result = await response.json();
    } catch {
      throw new Error('We could not confirm your submission. Please check your connection and try again.');
    } finally {
      clearTimeout(deadline);
    }

    if (response.ok && result?.success === true) return;
    if (response.status === 429) throw new Error('Too many attempts. Please wait a minute and try again.');
    if (response.status === 422) throw new Error('Please check your details and try again.');
    if (response.status === 403 && result?.error === 'verification_failed') {
      throw new Error('Verification expired or failed. Please submit the form again.');
    }
    throw new Error('We could not accept your submission. Please try again.');
  }

  const copy = {
    support: { sending: 'Sending…', success: 'contactSuccess' },
    waitlist: { sending: 'Joining…', success: 'formSuccess' }
  };
  const publicAliasOrigin = 'https://iron-chapter-site.pages.dev';
  const canonicalForms = {
    support: { href: 'https://theironchapter.com/support#contactForm', label: 'Open the support form on theironchapter.com' },
    waitlist: { href: 'https://theironchapter.com/#waitlist', label: 'Join the waitlist on theironchapter.com' }
  };

  for (const form of document.querySelectorAll('form[data-website-form]')) {
    const action = form.dataset.websiteForm;
    const button = form.querySelector('button[type="submit"]');
    const challenge = document.getElementById(`${form.id}Challenge`);
    const status = document.getElementById(`${form.id}Status`);
    if (!websiteOrigins.has(window.location.origin)) {
      const canonical = window.location.origin === publicAliasOrigin ? canonicalForms[action] : undefined;
      if (canonical) {
        const link = document.createElement('a');
        link.href = canonical.href;
        link.textContent = canonical.label;
        link.style.color = 'inherit';
        link.style.textDecoration = 'underline';
        status.replaceChildren('This form is unavailable here. ', link, ' or email support@theironchapter.com.');
        continue;
      }
      status.textContent = 'This form is unavailable here. You can email support@theironchapter.com.';
      continue;
    }
    const success = document.getElementById(copy[action].success);
    const waitlistNote = action === 'waitlist' ? document.querySelector('.waitlist-microcopy') : null;
    const buttonLabel = button.textContent;
    let pending = false;

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (pending) return;
      pending = true;
      button.disabled = true;
      status.textContent = '';
      form.setAttribute('aria-busy', 'true');

      try {
        button.textContent = 'Verifying…';
        const fields = Object.fromEntries(new FormData(form));
        const token = await getToken(challenge, action);
        button.textContent = copy[action].sending;
        await send(action, fields, token);
        form.style.display = 'none';
        if (waitlistNote) waitlistNote.style.display = 'none';
        success.style.display = 'block';
        success.focus();
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : 'Something went wrong. Please try again.';
      } finally {
        button.textContent = buttonLabel;
        button.disabled = false;
        form.removeAttribute('aria-busy');
        pending = false;
      }
    });

    button.disabled = false;
  }
})();
