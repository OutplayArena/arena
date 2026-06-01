import { Routes, Route, Navigate } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { Footer } from "./components/Footer";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GamePlayPage } from "./pages/GamePlayPage";
import { HistoryPage } from "./pages/HistoryPage";
import { KeysPage } from "./pages/KeysPage";
import { ProtectedRoute } from "./components/ProtectedRoute";

export default function App() {
  return (
    <div className="flex flex-col min-h-dvh">
      <NavBar />
      <main className="flex-1 flex flex-col min-h-0">
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
                <Navigate to="/play/blotto" replace />
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
            path="/keys"
            element={
              <ProtectedRoute>
                <KeysPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
