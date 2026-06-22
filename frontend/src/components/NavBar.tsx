import { memo, useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import { useAuth } from "../hooks/useAuth";
import { useSiteConfig } from "../hooks/useSiteConfig";

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
    </svg>
  );
}

const navLink = ({ isActive }: { isActive: boolean }) =>
  "px-3 py-1.5 text-sm font-medium transition-colors duration-150 rounded-[var(--radius-chip)] " +
  (isActive ? "text-ink bg-surface-container" : "text-muted hover:text-ink hover:bg-surface-container");

export const NavBar = memo(function NavBar() {
  const { theme, toggle } = useTheme();
  const { user, hasProviders, logout } = useAuth();
  const { github_url, docs_url } = useSiteConfig();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <nav className="sticky top-0 z-50 h-12 flex items-center justify-between px-5 border-b border-line bg-surface/80 backdrop-blur-md">
      {/* Logo */}
      <NavLink to="/" className="flex items-center gap-2 no-underline shrink-0">
        <img src="/img/logo_only_outplaylabs_arena.png" alt="OutplayLabs Arena" className="h-7 w-auto" />
        <span className="text-sm font-bold text-ink tracking-tight">OutplayLabs</span>
      </NavLink>

      {/* Center nav */}
      <div className="hidden md:flex items-center gap-0.5">
        <NavLink to="/" end className={navLink}>Home</NavLink>
        {(user || !hasProviders) && (
          <NavLink to="/dashboard" className={navLink}>Dashboard</NavLink>
        )}
        {docs_url && (
          <a href={docs_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-container rounded-[var(--radius-chip)] transition-colors duration-150">
            Docs
          </a>
        )}
        {github_url && (
          <a href={github_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-container rounded-[var(--radius-chip)] transition-colors duration-150 flex items-center gap-1.5">
            <GithubIcon /> GitHub
          </a>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={toggle}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          className="w-8 h-8 flex items-center justify-center rounded-[var(--radius-chip)] text-muted hover:text-ink hover:bg-surface-container transition-colors duration-150"
        >
          {theme === "light" ? <MoonIcon /> : <SunIcon />}
        </button>

        {hasProviders && !user && (
          <NavLink
            to="/login"
            className="ml-1 inline-flex items-center h-7 px-3 rounded-[var(--radius-button)] bg-accent text-white text-xs font-semibold transition-opacity duration-150 hover:opacity-90"
          >
            Sign in
          </NavLink>
        )}

        {(user || !hasProviders) && (
          <div className="relative ml-1" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="w-8 h-8 flex items-center justify-center rounded-[var(--radius-chip)] hover:bg-surface-container transition-colors duration-150"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt={user.name} className="w-6 h-6 rounded-full" referrerPolicy="no-referrer" />
              ) : user ? (
                <span className="text-xs font-bold text-accent w-6 h-6 rounded-full bg-accent-soft flex items-center justify-center">
                  {user.name.charAt(0).toUpperCase()}
                </span>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              )}
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 top-full mt-1.5 w-52 rounded-[var(--radius-card)] border border-line bg-surface shadow-elevation-4 py-1 z-50"
                role="menu"
              >
                <div className="px-3 py-2.5">
                  <p className="text-xs font-semibold text-ink truncate">{user ? user.name : "Local"}</p>
                  {user && <p className="text-xs text-muted truncate mt-0.5">{user.email}</p>}
                </div>
                <div className="border-t border-line mx-0 my-1" />
                <NavLink
                  to="/keys"
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2 text-xs text-ink hover:bg-surface-container transition-colors no-underline"
                  role="menuitem"
                >
                  API Keys
                </NavLink>
                {user && (
                  <>
                    <div className="border-t border-line mx-0 my-1" />
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); logout(); }}
                      className="w-full text-left px-3 py-2 text-xs text-muted hover:text-ink hover:bg-surface-container transition-colors"
                      role="menuitem"
                    >
                      Log out
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  );
});
