/**
 * The Quick Access Menu panel.
 *
 * Every control here writes straight through to the Python backend,
 * which validates and persists. The panel keeps working even when the
 * focus hook has failed -- in that case it says so, plainly, at the top,
 * so a broken preview is diagnosable rather than mysterious.
 */

import {
  ButtonItem,
  DropdownItem,
  Field,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { cacheStats, clearCache } from "../api";
import { t } from "../i18n";
import { AUTO, LANGUAGES } from "../languages";
import { updateSettings, usePluginState } from "../store";
import type { CacheStats, OverlayPosition, OverlaySize, PreviewMode } from "../types";

const PREVIEW_MODE_OPTIONS: { data: PreviewMode; label: string }[] = [
  { data: "trailer", label: "settings.previewModeTrailer" },
  { data: "screenshots", label: "settings.previewModeScreenshots" },
  { data: "off", label: "settings.previewModeOff" },
];

const POSITION_OPTIONS: { data: OverlayPosition; label: string }[] = [
  { data: "top-left", label: "settings.positionTopLeft" },
  { data: "top-right", label: "settings.positionTopRight" },
  { data: "bottom-left", label: "settings.positionBottomLeft" },
  { data: "bottom-right", label: "settings.positionBottomRight" },
];

const SIZE_OPTIONS: { data: OverlaySize; label: string }[] = [
  { data: "s", label: "settings.sizeSmall" },
  { data: "m", label: "settings.sizeMedium" },
  { data: "l", label: "settings.sizeLarge" },
];

/**
 * "Match Steam" first, then Valve's languages by English name. The codes
 * are Steam's own, so whatever the user picks can go straight to the
 * store API.
 */
const LANGUAGE_OPTIONS: { data: string; label: string }[] = [
  { data: AUTO, label: "settings.languageAuto" },
  ...LANGUAGES.map(({ code, label }) => ({ data: code, label })),
];

/** English name for a Steam language code, or the code itself. */
function languageLabel(code: string): string {
  return LANGUAGES.find((language) => language.code === code)?.label ?? code;
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SettingsPanel() {
  const { settings, focus, loading, clientLanguage } = usePluginState();
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [clearing, setClearing] = useState(false);
  const [cleared, setCleared] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    void cacheStats().then((result) => {
      if (!cancelled) setStats(result);
    });
    return () => {
      cancelled = true;
    };
  }, [cleared]);

  const onClearCache = async () => {
    setClearing(true);
    try {
      setCleared(await clearCache());
    } finally {
      setClearing(false);
    }
  };

  // Video-only controls are meaningless in these modes, so they are
  // disabled rather than silently ignored.
  const videoDisabled = settings.preview_mode !== "trailer" || settings.data_saver;

  return (
    <>
      {!focus.ok ? (
        <PanelSection title={t("status.section")}>
          <PanelSectionRow>
            <Field
              label={t("status.focusUnavailable")}
              description={
                focus.reason
                  ? `${t("status.focusUnavailableBody")} ${t("status.reason", {
                      reason: focus.reason,
                    })}`
                  : t("status.focusUnavailableBody")
              }
              focusable={true}
              bottomSeparator="none"
            />
          </PanelSectionRow>
        </PanelSection>
      ) : null}

      <PanelSection title={t("settings.section")}>
        <PanelSectionRow>
          <ToggleField
            label={t("settings.enabled")}
            description={t("settings.enabledDescription")}
            checked={settings.enabled}
            disabled={loading}
            onChange={(enabled) => void updateSettings({ enabled })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <DropdownItem
            label={t("settings.previewMode")}
            rgOptions={PREVIEW_MODE_OPTIONS.map(({ data, label }) => ({
              data,
              label: t(label),
            }))}
            selectedOption={settings.preview_mode}
            disabled={loading || !settings.enabled}
            onChange={(option) => void updateSettings({ preview_mode: option.data as PreviewMode })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <SliderField
            label={t("settings.previewDelay")}
            description={t("settings.previewDelayDescription")}
            value={settings.preview_delay_ms}
            min={0}
            max={3000}
            step={50}
            notchTicksVisible={false}
            showValue={true}
            valueSuffix=" ms"
            disabled={loading || !settings.enabled}
            onChange={(preview_delay_ms) => void updateSettings({ preview_delay_ms })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <SliderField
            label={t("settings.autoplayDelay")}
            description={t("settings.autoplayDelayDescription")}
            value={settings.autoplay_delay_ms}
            min={0}
            max={3000}
            step={100}
            notchTicksVisible={false}
            showValue={true}
            valueSuffix=" ms"
            disabled={loading || !settings.enabled || videoDisabled}
            onChange={(autoplay_delay_ms) => void updateSettings({ autoplay_delay_ms })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label={t("settings.muted")}
            description={t("settings.mutedDescription")}
            checked={settings.muted}
            disabled={loading || !settings.enabled || videoDisabled}
            onChange={(muted) => void updateSettings({ muted })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label={t("settings.loop")}
            description={t("settings.loopDescription")}
            checked={settings.loop}
            disabled={loading || !settings.enabled || videoDisabled}
            onChange={(loop) => void updateSettings({ loop })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <DropdownItem
            label={t("settings.position")}
            rgOptions={POSITION_OPTIONS.map(({ data, label }) => ({ data, label: t(label) }))}
            selectedOption={settings.position}
            disabled={loading || !settings.enabled}
            onChange={(option) => void updateSettings({ position: option.data as OverlayPosition })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label={t("settings.dynamicPosition")}
            description={t("settings.dynamicPositionDescription")}
            checked={settings.dynamic_position}
            disabled={loading || !settings.enabled}
            onChange={(dynamic_position) => void updateSettings({ dynamic_position })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <DropdownItem
            label={t("settings.size")}
            rgOptions={SIZE_OPTIONS.map(({ data, label }) => ({ data, label: t(label) }))}
            selectedOption={settings.size}
            disabled={loading || !settings.enabled}
            onChange={(option) => void updateSettings({ size: option.data as OverlaySize })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label={t("settings.dataSaver")}
            description={t("settings.dataSaverDescription")}
            checked={settings.data_saver}
            disabled={loading || !settings.enabled}
            onChange={(data_saver) => void updateSettings({ data_saver })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <DropdownItem
            label={t("settings.language")}
            description={
              settings.language === AUTO
                ? clientLanguage
                  ? t("settings.languageAutoDetected", {
                      language: languageLabel(clientLanguage),
                    })
                  : t("settings.languageAutoUnknown")
                : t("settings.languageDescription")
            }
            rgOptions={LANGUAGE_OPTIONS.map(({ data, label }) => ({
              data,
              // Valve's own language names are already in English and
              // are not ours to translate; only "Match Steam" is a key.
              label: data === AUTO ? t(label) : label,
            }))}
            selectedOption={settings.language}
            disabled={loading || !settings.enabled}
            onChange={(option) => void updateSettings({ language: String(option.data) })}
          />
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title={t("settings.cacheSection")}>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={clearing}
            description={
              cleared !== null
                ? t("settings.cacheCleared", { count: cleared })
                : stats
                  ? `${t("settings.cacheEntries", {
                      count: stats.entries,
                      size: formatBytes(stats.bytes),
                    })} — ${t("settings.clearCacheDescription")}`
                  : t("settings.clearCacheDescription")
            }
            onClick={() => void onClearCache()}
          >
            {clearing ? t("settings.clearing") : t("settings.clearCache")}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}
