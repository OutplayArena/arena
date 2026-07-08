import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { Footer } from "./components/Footer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GamePlayPage } from "./pages/GamePlayPage";
import { HistoryPage } from "./pages/HistoryPage";
import { KeysPage } from "./pages/KeysPage";
import { SettingsPage } from "./pages/SettingsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { GamesPage } from "./pages/GamesPage";
import { PapersPage } from "./pages/PapersPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { AgentDetailPage } from "./pages/AgentDetailPage";
import { DocsPage } from "./pages/DocsPage";
import { GettingStartedPage } from "./pages/GettingStartedPage";
import { AdminPage } from "./pages/AdminPage";
import { LobbyPage } from "./pages/LobbyPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminRoute } from "./components/AdminRoute";
import { PrivacyGate } from "./components/PrivacyGate";

export default function App() {
  // Hide the React chrome on /docs/* so the user gets the mkdocs Material
  // experience (header + sidebar + content) without a duplicate navbar/footer
  // wrapping the iframe. The iframe's internal navigation does not change
  // the parent's pathname, so this stays stable across in-iframe page changes.
  const location = useLocation();
  const isDocs =
    location.pathname === "/docs" || location.pathname.startsWith("/docs/");

  return (
    <div className="flex flex-col min-h-screen min-h-dvh">
      <PrivacyGate />
      {!isDocs && <NavBar />}
      <main className="flex-1 flex flex-col min-h-0">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/play"
              element={
                <ProtectedRoute>
                  <Navigate to="/dashboard" replace />
                </ProtectedRoute>
              }
            />
            <Route
              path="/play/:gameSlug"
              element={
                <ProtectedRoute>
                  <GamePlayPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/play/:gameSlug/:sessionId"
              element={
                <ProtectedRoute>
                  <GamePlayPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedRoute>
                  <HistoryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/keys"
              element={
                <ProtectedRoute>
                  <KeysPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <AdminPage />
                </AdminRoute>
              }
            />
            <Route path="/getting-started" element={<GettingStartedPage />} />
            <Route
              path="/lobby"
              element={
                <ProtectedRoute>
                  <LobbyPage />
                </ProtectedRoute>
              }
            />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/leaderboard/:agentId" element={<AgentDetailPage />} />
            <Route path="/docs/*" element={<DocsPage />} />
            <Route path="/games" element={<GamesPage />} />
            <Route path="/papers" element={<PapersPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
      {!isDocs && <Footer />}
    </div>
  );
}
