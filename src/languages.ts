/**
 * Steam's store API language codes.
 *
 * Mirrors `py_modules/steamview/languages.py` -- the backend validates
 * independently, because it is the side that builds the URL, but the
 * settings dropdown needs the same list to offer.
 *
 * These are Valve's own short names, not ISO codes: `brazilian` rather
 * than `pt-BR`, `koreana` rather than `ko`. The happy accident that makes
 * this feature small is that Steam's client speaks the same vocabulary --
 * `SteamClient.Settings.GetCurrentLanguage()` returns one of these exact
 * strings, so "match Steam" needs no mapping table, only validation.
 */

/** Sentinel meaning "whatever Steam itself is set to". */
export const AUTO = "auto";

/** Fallback whenever detection or validation comes up empty. */
export const DEFAULT_LANGUAGE = "english";

/** Every code Steam's store API accepts, English name for the dropdown. */
export const LANGUAGES: readonly { code: string; label: string }[] = [
  { code: "english", label: "English" },
  { code: "arabic", label: "Arabic" },
  { code: "bulgarian", label: "Bulgarian" },
  { code: "schinese", label: "Chinese (Simplified)" },
  { code: "tchinese", label: "Chinese (Traditional)" },
  { code: "czech", label: "Czech" },
  { code: "danish", label: "Danish" },
  { code: "dutch", label: "Dutch" },
  { code: "finnish", label: "Finnish" },
  { code: "french", label: "French" },
  { code: "german", label: "German" },
  { code: "greek", label: "Greek" },
  { code: "hungarian", label: "Hungarian" },
  { code: "italian", label: "Italian" },
  { code: "japanese", label: "Japanese" },
  { code: "koreana", label: "Korean" },
  { code: "norwegian", label: "Norwegian" },
  { code: "polish", label: "Polish" },
  { code: "portuguese", label: "Portuguese" },
  { code: "brazilian", label: "Portuguese (Brazil)" },
  { code: "romanian", label: "Romanian" },
  { code: "russian", label: "Russian" },
  { code: "spanish", label: "Spanish (Spain)" },
  { code: "latam", label: "Spanish (Latin America)" },
  { code: "swedish", label: "Swedish" },
  { code: "thai", label: "Thai" },
  { code: "turkish", label: "Turkish" },
  { code: "ukrainian", label: "Ukrainian" },
  { code: "vietnamese", label: "Vietnamese" },
];

const CODES = new Set(LANGUAGES.map((language) => language.code));

/** `value` as a known Steam language code, or null. Never `auto`. */
export function normaliseLanguage(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const code = value.trim().toLowerCase();
  return CODES.has(code) ? code : null;
}

/**
 * The code to actually send with a lookup.
 *
 * `setting` is what the user chose; `detected` is what Steam reported.
 * A concrete setting always wins -- someone who picked a language meant
 * it, even if Steam's UI is in another one.
 */
export function effectiveLanguage(setting: unknown, detected: unknown): string {
  if (setting !== AUTO) {
    const chosen = normaliseLanguage(setting);
    if (chosen) return chosen;
  }
  return normaliseLanguage(detected) ?? DEFAULT_LANGUAGE;
}
