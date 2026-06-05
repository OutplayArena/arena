import { createContext } from "react";
import type { SiteConfig } from "../types";

export const SiteConfigContext = createContext<SiteConfig>({
  github_url: "",
  docs_url: "",
  privacy_notice_url: "",
  about_text: "",
  footer: { copyright: "", tagline: "" },
});
