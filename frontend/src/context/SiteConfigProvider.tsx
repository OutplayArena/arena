import { useEffect, useState } from "react";
import type { SiteConfig } from "../types";
import { SiteConfigContext } from "./SiteConfigContext";
import { getSiteConfig } from "../api";

export function SiteConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<SiteConfig>({
    github_url: "",
    docs_url: "",
    privacy_notice_url: "",
    about_text: "",
    footer: { copyright: "", tagline: "" },
  });

  useEffect(() => {
    getSiteConfig().then(setConfig).catch(() => {});
  }, []);

  return (
    <SiteConfigContext.Provider value={config}>
      {children}
    </SiteConfigContext.Provider>
  );
}
