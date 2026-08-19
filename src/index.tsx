/**
 * SteamView plugin entry point.
 *
 * Two responsibilities, and both are wrapped so that neither can take
 * Steam down with it:
 *
 * 1. Register the preview overlay as a Decky *global component*. This is
 *    a supported API that renders our element alongside Steam's UI --
 *    not a patch spliced into Valve's React tree. If the registration
 *    fails, the plugin still loads with settings intact and the overlay
 *    simply absent.
 *
 * 2. Load persisted settings from the backend.
 *
 * The risky work -- finding the highlighted game -- lives in
 * `steam/focus.ts` and is started by the overlay itself, so its failure
 * mode is scoped to the overlay.
 */

import { definePlugin, staticClasses } from "@decky/ui";
import { routerHook } from "@decky/api";
import { FaPhotoVideo } from "react-icons/fa";

import { PreviewOverlay } from "./components/PreviewOverlay";
import { SettingsPanel } from "./components/SettingsPanel";
import { initI18n, t } from "./i18n";
import { loadSettings, setFocusStatus } from "./store";

/** Decky identifies global components by name; must be unique. */
const OVERLAY_COMPONENT_NAME = "SteamViewPreviewOverlay";

export default definePlugin(() => {
  initI18n();

  // Fire and forget: the panel and overlay both render sensible defaults
  // until this resolves.
  void loadSettings();

  let overlayRegistered = false;
  try {
    routerHook.addGlobalComponent(OVERLAY_COMPONENT_NAME, PreviewOverlay);
    overlayRegistered = true;
  } catch (error) {
    console.error(
      "[SteamView] could not register the preview overlay; " +
        "settings still work and your library is unaffected:",
      error,
    );
    setFocusStatus({ ok: false, reason: "overlay-registration-failed" });
  }

  return {
    name: t("plugin.name"),
    titleView: <div className={staticClasses.Title}>{t("plugin.name")}</div>,
    content: <SettingsPanel />,
    icon: <FaPhotoVideo />,
    onDismount() {
      if (!overlayRegistered) return;
      try {
        routerHook.removeGlobalComponent(OVERLAY_COMPONENT_NAME);
      } catch (error) {
        console.warn("[SteamView] failed to remove the preview overlay:", error);
      }
    },
  };
});
