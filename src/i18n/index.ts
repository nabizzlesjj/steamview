/**
 * Translation scaffolding.
 *
 * Only English exists today. The point of wiring i18next up now is that
 * adding a locale later is dropping in a JSON file and one line here,
 * rather than hunting hardcoded strings out of the components.
 */

import i18next from "i18next";

import en from "./locales/en.json";

export const FALLBACK_LANGUAGE = "en";

export const resources = {
  en: { translation: en },
} as const;

/**
 * Steam exposes the client's language on the localisation manager. If it
 * is missing or unrecognised we fall back to English, which is the only
 * complete locale anyway.
 */
function detectLanguage(): string {
  try {
    const locales = (window as any).LocalizationManager?.m_rgLocalesToUse;
    if (Array.isArray(locales)) {
      for (const locale of locales) {
        const language = String(locale ?? "").split("-")[0];
        if (language && language in resources) return language;
      }
    }
  } catch {
    // Not worth reporting; English is a fine answer.
  }
  return FALLBACK_LANGUAGE;
}

export function initI18n(): void {
  if (i18next.isInitialized) return;
  i18next
    .init({
      lng: detectLanguage(),
      fallbackLng: FALLBACK_LANGUAGE,
      resources,
      interpolation: { escapeValue: false },
      returnNull: false,
    })
    .catch((error) => {
      console.warn("[SteamView] i18n init failed; falling back to raw keys:", error);
    });
}

/** Translate a key. Never throws -- returns the key itself on failure. */
export function t(key: string, options?: Record<string, unknown>): string {
  try {
    return i18next.t(key, options) as string;
  } catch {
    return key;
  }
}
