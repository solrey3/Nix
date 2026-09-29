{ ... }:

{
  programs.firefox = {
    enable = true;

    policies = {
      DisableFirefoxStudies = true;
      DisablePocket = true;
      DisableTelemetry = true;
      DontCheckDefaultBrowser = true;
      NoDefaultBookmarks = true;
      OfferToSaveLogins = false;
      ExtensionSettings = {
        "uBlock0@raymondhill.net" = {
          installation_mode = "force_installed";
          install_url = "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi";
        };
        "{d634138d-c276-4fc8-924b-40a0ea21d284}" = {
          installation_mode = "force_installed";
          install_url = "https://addons.mozilla.org/firefox/downloads/latest/1password-x-password-manager/latest.xpi";
        };
      };
    };

    # Betterfox-inspired Fastfox/Peskyfox/Securefox preferences for a cleaner,
    # more private browser without taking ownership of the user's profile.
    preferencesStatus = "default";
    preferences = {
      "app.shield.optoutstudies.enabled" = false;
      "browser.aboutConfig.showWarning" = false;
      "browser.contentblocking.category" = "strict";
      "browser.discovery.enabled" = false;
      "browser.newtabpage.activity-stream.default.sites" = "";
      "browser.newtabpage.activity-stream.feeds.section.highlights" = false;
      "browser.newtabpage.activity-stream.feeds.snippets" = false;
      "browser.newtabpage.activity-stream.feeds.topsites" = false;
      "browser.newtabpage.activity-stream.section.highlights.includePocket" = false;
      "browser.newtabpage.activity-stream.showSponsored" = false;
      "browser.newtabpage.activity-stream.showSponsoredTopSites" = false;
      "browser.newtabpage.enabled" = false;
      "browser.shopping.experience2023.enabled" = false;
      "browser.startup.homepage" = "about:blank";
      "browser.tabs.firefox-view" = false;
      "browser.urlbar.quicksuggest.enabled" = false;
      "browser.urlbar.suggest.quicksuggest.nonsponsored" = false;
      "browser.urlbar.suggest.quicksuggest.sponsored" = false;
      "datareporting.healthreport.uploadEnabled" = false;
      "datareporting.policy.dataSubmissionEnabled" = false;
      "dom.private-attribution.submission.enabled" = false;
      "dom.security.https_only_mode" = true;
      "extensions.formautofill.addresses.enabled" = false;
      "extensions.formautofill.creditCards.enabled" = false;
      "extensions.pocket.enabled" = false;
      "geo.enabled" = false;
      "media.peerconnection.ice.default_address_only" = true;
      "network.cookie.cookieBehavior" = 5;
      "privacy.globalprivacycontrol.enabled" = true;
      "privacy.query_stripping.enabled" = true;
      "privacy.query_stripping.enabled.pbmode" = true;
      "privacy.trackingprotection.enabled" = true;
      "privacy.trackingprotection.socialtracking.enabled" = true;
      "signon.rememberSignons" = false;
      "toolkit.telemetry.archive.enabled" = false;
      "toolkit.telemetry.enabled" = false;
      "toolkit.telemetry.server" = "data:,";
      "toolkit.telemetry.unified" = false;
      # Hyprland's portal may not expose the desktop color-scheme preference
      # early enough for Firefox's System theme. Explicitly advertise the
      # configured dark system appearance to Firefox and web content.
      "ui.systemUsesDarkTheme" = 1;
    };
  };
}
