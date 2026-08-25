/**
 * Steam store language codes.
 *
 * The point of the allowlist is that this value is interpolated into a
 * URL sent to Steam, and that a wrong code fails *silently* by returning
 * English. So the tests care most about what is rejected.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTO,
  DEFAULT_LANGUAGE,
  LANGUAGES,
  effectiveLanguage,
  normaliseLanguage,
} from "../../.tsbuild/src/languages.js";

test("the code list is well formed and has no duplicates", () => {
  const codes = LANGUAGES.map((language) => language.code);
  assert.equal(new Set(codes).size, codes.length);
  assert.ok(codes.includes(DEFAULT_LANGUAGE));
  for (const { code, label } of LANGUAGES) {
    assert.match(code, /^[a-z]+$/, `${code} is not a bare lowercase code`);
    assert.ok(label.length > 0);
  }
});

test("Valve's own spellings are the ones accepted", () => {
  // These are the codes that differ from any ISO intuition, and are
  // exactly the ones a mapping written from memory gets wrong.
  assert.equal(normaliseLanguage("brazilian"), "brazilian");
  assert.equal(normaliseLanguage("koreana"), "koreana");
  assert.equal(normaliseLanguage("schinese"), "schinese");
  assert.equal(normaliseLanguage("tchinese"), "tchinese");
  assert.equal(normaliseLanguage("latam"), "latam");
});

test("ISO codes are rejected rather than guessed at", () => {
  for (const value of ["pt-BR", "pt", "ko", "zh-Hans", "zh-CN", "es-419", "en-US"]) {
    assert.equal(normaliseLanguage(value), null, `${value} should not be accepted`);
  }
});

test("junk is rejected, including the auto sentinel", () => {
  for (const value of [AUTO, "", "  ", "klingon", null, undefined, 42, {}, []]) {
    assert.equal(normaliseLanguage(value), null);
  }
});

test("case and surrounding space are tolerated", () => {
  assert.equal(normaliseLanguage("  BRAZILIAN "), "brazilian");
  assert.equal(normaliseLanguage("English"), "english");
});

test("an explicit choice beats what Steam reports", () => {
  assert.equal(effectiveLanguage("brazilian", "english"), "brazilian");
  assert.equal(effectiveLanguage("french", null), "french");
});

test("auto follows Steam, and falls back to English when Steam is silent", () => {
  assert.equal(effectiveLanguage(AUTO, "brazilian"), "brazilian");
  assert.equal(effectiveLanguage(AUTO, null), DEFAULT_LANGUAGE);
  assert.equal(effectiveLanguage(AUTO, "klingon"), DEFAULT_LANGUAGE);
});

test("a corrupt setting falls back rather than reaching a URL", () => {
  assert.equal(effectiveLanguage("klingon", "brazilian"), "brazilian");
  assert.equal(effectiveLanguage("klingon", null), DEFAULT_LANGUAGE);
  assert.equal(effectiveLanguage(undefined, null), DEFAULT_LANGUAGE);
});
